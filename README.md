# Apple Firmware Checker
A tool for automatically monitoring URLs for Apple Product firmware.

## Feature
* Support iPhone / iPad / iPod / HomePod mini
* Automatic polling with a 15-minute interval
* Uses SQLite to store firmware information, including Device Code / URL / SHA1
* Automatically generates RSS feeds for easy subscription and download via Download Tools.

## Structure 
* Script Structure
```
apple_firmware_checker/
├── firmware_checker.py     # main script
├── device.py               # custom class
├── requirements.txt        
├── firmware.db            # SQLite database
├── firmware_rss.xml       # RSS feed
├── *.txt                  # URL history
└── .github/workflows/     # GitHub Actions
    ├── firmware_check.yml
    └── purge_jsdelivr_cache.yml
```

* Database Structure
```
CREATE TABLE firmware (
    hardware_code TEXT PRIMARY KEY,
    product_version TEXT,
    build_version TEXT,
    firmware_sha1 TEXT,
    firmware_url TEXT,
    last_checked TIMESTAMP
);
```
