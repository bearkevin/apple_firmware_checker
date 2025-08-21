import plistlib
import requests
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from device import AppleDevice

# --- Constants ---
PLIST_URL = "https://s.mzstatic.com/version"
DB_FILE = "firmware.db"
RSS_FILE = "firmware_rss.xml"
POLLING_INTERVAL_MINUTES = 15
MAX_RSS_ITEMS = 50


def fetch_and_parse_plist(url: str) -> dict | None:
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return plistlib.loads(response.content)
    except requests.RequestException as e:
        print(f"[{datetime.now()}] Error fetching data: {e}")
        return None
    except plistlib.InvalidFileException as e:
        print(f"[{datetime.now()}] Error parsing plist data: {e}")
        return None

def find_latest_version_node(data: dict) -> dict | None:
    numeric_keys = [int(k) for k in data.keys() if k.isdigit()]
    if not numeric_keys:
        return None
    return data.get(str(max(numeric_keys)))

def extract_firmware_info(full_data: dict) -> list[AppleDevice]:
    devices = []
    by_version_node = full_data.get("MobileDeviceSoftwareVersionsByVersion")
    if not by_version_node:
        return []
    latest_version_node = find_latest_version_node(by_version_node)
    if not latest_version_node:
        return []
    versions = latest_version_node.get("MobileDeviceSoftwareVersions")
    if not versions:
        return []

    for code, info in versions.items():
        if code.startswith("AppleTV"):
            continue
        try:
            restore_info = info["Unknown"]["Universal"]["Restore"]
            devices.append(AppleDevice(
                hardware_code=code,
                build_version=restore_info.get("BuildVersion"),
                firmware_sha1=restore_info.get("FirmwareSHA1"),
                firmware_url=restore_info.get("FirmwareURL"),
                product_version=restore_info.get("ProductVersion"),
            ))
        except KeyError:
            pass
    return devices

# --- Database & RSS Functions ---

def init_db(db_path: str):
    """Initializes the database and creates the firmware table if it doesn't exist."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS firmware (
                hardware_code TEXT PRIMARY KEY,
                product_version TEXT,
                build_version TEXT,
                firmware_sha1 TEXT,
                firmware_url TEXT,
                last_checked TIMESTAMP
            )
        ''')
        # Clean up any old AppleTV entries on initialization
        cursor.execute("DELETE FROM firmware WHERE hardware_code LIKE 'AppleTV%'")
        conn.commit()

def get_existing_firmware(db_path: str) -> dict[str, str]:
    """Gets a dictionary of existing firmware SHA1s from the database."""
    existing = {}
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT hardware_code, firmware_sha1 FROM firmware")
            for row in cursor.fetchall():
                existing[row["hardware_code"]] = row["firmware_sha1"]
    except sqlite3.OperationalError:
        pass
    return existing

def update_database(db_path: str, devices: list[AppleDevice]):
    """Inserts or replaces device firmware information in the database."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for device in devices:
            cursor.execute('''
                INSERT OR REPLACE INTO firmware (
                    hardware_code, product_version, build_version, 
                    firmware_sha1, firmware_url, last_checked
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                device.hardware_code, device.product_version, device.build_version,
                device.firmware_sha1, device.firmware_url, datetime.now()
            ))
        conn.commit()

def update_rss_feed(rss_path: str, updated_devices: list[AppleDevice]):
    """Creates or updates a local RSS feed file with the latest firmware."""
    print(f"Updating RSS feed at {rss_path}...")
    try:
        tree = ET.parse(rss_path)
        channel = tree.find('channel')
    except (FileNotFoundError, ET.ParseError):
        root = ET.Element('rss', version='2.0')
        tree = ET.ElementTree(root)
        channel = ET.SubElement(root, 'channel')
        ET.SubElement(channel, 'title').text = 'Apple Firmware Updates'
        ET.SubElement(channel, 'link').text = 'https://www.apple.com'
        ET.SubElement(channel, 'description').text = 'Latest Apple firmware updates found by checker script.'

    for device in reversed(updated_devices): # Add newest first
        item = ET.Element('item')
        ET.SubElement(item, 'title').text = f'{device.hardware_code} - {device.product_version} ({device.build_version})'
        ET.SubElement(item, 'link').text = device.firmware_url
        ET.SubElement(item, 'guid').text = device.firmware_url
        ET.SubElement(item, 'pubDate').text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        ET.SubElement(item, 'description').text = f"Build: {device.build_version}, SHA1: {device.firmware_sha1}"
        channel.insert(3, item) # Insert after title, link, description

    # Trim old items
    items = channel.findall('item')
    if len(items) > MAX_RSS_ITEMS:
        for old_item in items[MAX_RSS_ITEMS:]:
            channel.remove(old_item)

    ET.indent(tree, space="  ", level=0)
    tree.write(rss_path, encoding='utf-8', xml_declaration=True)
    print("RSS feed updated.")

def main():
    """Main function to run a single firmware check and update local files."""
    print("Initializing firmware checker...")
    init_db(DB_FILE)
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running check...")
    local_firmware = get_existing_firmware(DB_FILE)
    plist_data = fetch_and_parse_plist(PLIST_URL)
    if not plist_data:
        print("Fetch failed. Exiting.")
        return
    
    remote_devices = extract_firmware_info(plist_data)
    if not remote_devices:
        print("Could not extract remote device info. Exiting.")
        return

    updated_devices = [d for d in remote_devices if d.firmware_sha1 != local_firmware.get(d.hardware_code)]
    
    if updated_devices:
        print(f"\n--- !!! FIRMWARE UPDATES DETECTED !!! ---")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Found {len(updated_devices)} new or updated firmwares:")
        print("-"*50)
        for device in updated_devices:
            print(device)
            print()
        
        update_database(DB_FILE, remote_devices)
        print("Database has been updated.")
        
        url_filename = f"{datetime.now().strftime('%Y-%m-%d')}_updates.txt"
        print(f"Saving updated firmware URLs to {url_filename}...")
        new_urls = sorted(list(set(d.firmware_url for d in updated_devices)))
        try:
            with open(url_filename, 'r') as f:
                existing_urls = [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            existing_urls = []
        all_urls = sorted(list(set(existing_urls + new_urls)))
        with open(url_filename, 'w') as f:
            for url in all_urls:
                f.write(url + '\n')
        print("URLs saved.")

        update_rss_feed(RSS_FILE, updated_devices)
    else:
        print("No updates found.")

    print(f"Check complete.")

if __name__ == "__main__":
    main()
