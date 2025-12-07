import logging
from typing import Optional
import os
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
URL_HISTORY_DIR = "url_history"
POLLING_INTERVAL_MINUTES = 15


def fetch_and_parse_plist(url: str) -> Optional[dict]:
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return plistlib.loads(response.content)
    except requests.RequestException as e:
        logging.error(f"Error fetching data: {e}")
        return None
    except plistlib.InvalidFileException as e:
        logging.error(f"Error parsing plist data: {e}")
        return None

def find_latest_version_node(data: dict) -> Optional[dict]:
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
    logging.info(f"Updating RSS feed at {rss_path}...")
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

    # 清空现有的所有条目
    for item in channel.findall('item'):
        channel.remove(item)
    
    # 添加所有新发现的固件更新条目
    for device in updated_devices:
        item = ET.Element('item')
        ET.SubElement(item, 'title').text = f'{device.hardware_code} - {device.product_version} ({device.build_version})'
        ET.SubElement(item, 'link').text = device.firmware_url
        ET.SubElement(item, 'guid').text = device.firmware_url
        ET.SubElement(item, 'pubDate').text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        ET.SubElement(item, 'description').text = f"Build: {device.build_version}, SHA1: {device.firmware_sha1}"
        channel.append(item)  # 直接添加到频道末尾

    ET.indent(tree, space="  ", level=0)
    tree.write(rss_path, encoding='utf-8', xml_declaration=True)
    logging.info(f"RSS feed updated with {len(updated_devices)} new firmware entries.")

def save_firmware_urls(updated_devices: list[AppleDevice], history_dir: str):
    """Saves the URLs of updated firmware to a text file in the history directory."""
    if not os.path.exists(history_dir):
        os.makedirs(history_dir)
        logging.info(f"Created directory: {history_dir}")

    url_filename = os.path.join(history_dir, f"{datetime.now().strftime('%Y-%m-%d')}_updates.txt")
    logging.info(f"Saving updated firmware URLs to {url_filename}...")
    
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
    logging.info("URLs saved.")

def main():
    """Main function to run a single firmware check and update local files."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("firmware_checker.log"),
            logging.StreamHandler()
        ]
    )

    logging.info("Initializing firmware checker...")
    init_db(DB_FILE)
    
    logging.info("Running check...")
    local_firmware = get_existing_firmware(DB_FILE)
    plist_data = fetch_and_parse_plist(PLIST_URL)
    if not plist_data:
        logging.error("Fetch failed. Exiting.")
        return
    
    remote_devices = extract_firmware_info(plist_data)
    if not remote_devices:
        logging.error("Could not extract remote device info. Exiting.")
        return

    updated_devices = [d for d in remote_devices if d.firmware_sha1 != local_firmware.get(d.hardware_code)]
    
    if updated_devices:
        logging.info("--- !!! FIRMWARE UPDATES DETECTED !!! ---")
        logging.info(f"Found {len(updated_devices)} new or updated firmwares:")
        print("-"*50)
        for device in updated_devices:
            print(device)
            print()
        
        update_database(DB_FILE, remote_devices)
        logging.info("Database has been updated.")
        
        save_firmware_urls(updated_devices, URL_HISTORY_DIR)

        update_rss_feed(RSS_FILE, updated_devices)
    else:
        logging.info("No updates found.")

    logging.info("Check complete.")

if __name__ == "__main__":
    main()
