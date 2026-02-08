"""
Multi-Month Test: UI Integration

This explains how to run the multi-month test through the UI.

## Option 1: Local Location (Quick - No Database)

The simulation server automatically loads data from `simulator/{location}/` folders.
Just create the location folder with the required files:

```bash
# The multimonth_test.py already creates MULTIMONTH/ with:
# - papdata.json
# - 2019-01-MULTIMONTH.csv
# - 2019-02-MULTIMONTH.csv

# To use it, copy/symlink to simulator/ directory:
cd /Users/ryad/Code/delineo/Simulation/simulator
ln -s test_playground/MULTIMONTH MULTIMONTH
```

Then call the API with `location: "MULTIMONTH"`.

## Option 2: Create Convenience Zone in Database (Full UI Integration)

To use the full UI with ConvenienceZone selection:

1. Start the Fullstack server: `cd Fullstack/server && pnpm dev`
2. Create a CZ via API or use the script below

## Files in this folder:
- multimonth_test.py      - Generates test patterns CSVs
- setup_local_location.py - Sets up local location folder with patterns.json
- create_cz_for_test.py   - Creates a ConvenienceZone in the database
"""

import json
import shutil
import os
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
SIMULATOR_DIR = SCRIPT_DIR.parent
MULTIMONTH_DIR = SCRIPT_DIR / "MULTIMONTH"


def setup_local_location():
    """
    Set up MULTIMONTH as a local simulator location.
    This allows using location="MULTIMONTH" in API calls.
    """
    target_dir = SIMULATOR_DIR / "MULTIMONTH"
    
    # Create target directory
    target_dir.mkdir(exist_ok=True)
    
    # Copy papdata.json
    src_papdata = MULTIMONTH_DIR / "papdata.json"
    dst_papdata = target_dir / "papdata.json"
    if src_papdata.exists():
        shutil.copy(src_papdata, dst_papdata)
        print(f"✓ Copied papdata.json to {dst_papdata}")
    
    # We need to generate patterns.json from the CSV files
    # The simulation expects patterns.json, not raw CSVs
    # The CSVs are SafeGraph format for the Algorithms server
    
    # For now, create a simple patterns.json that matches the papdata
    # This is a simplified version - real patterns come from gen_patterns()
    patterns = generate_simple_patterns()
    
    patterns_path = target_dir / "patterns.json"
    with open(patterns_path, 'w') as f:
        json.dump(patterns, f, indent=2)
    print(f"✓ Generated patterns.json at {patterns_path}")
    
    print(f"\n✓ Location 'MULTIMONTH' is now available!")
    print(f"  Test with: curl -X POST http://localhost:1870/simulation/ \\")
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"location": "MULTIMONTH", "length": 24}}\'')


def generate_simple_patterns():
    """
    Generate simple patterns for testing.
    Month 1: Everyone goes to Place A (place "0")
    Month 2: Everyone goes to Place B (place "1")
    """
    patterns = {}
    
    # Load papdata to get people IDs
    papdata_path = MULTIMONTH_DIR / "papdata.json"
    with open(papdata_path) as f:
        papdata = json.load(f)
    
    people_ids = list(papdata["people"].keys())
    
    # Simulation runs in minutes, patterns are keyed by minute
    # Generate patterns for 2 weeks (20160 minutes) per "month"
    
    # MONTH 1: Days 0-13 - Everyone at Place A during day hours
    for day in range(14):
        # Morning: everyone at home
        minute = day * 1440  # Start of day
        patterns[str(minute)] = {
            "homes": {"0": ["0", "1"], "1": ["2", "3", "4"]},
            "places": {}
        }
        
        # Daytime (8am-6pm): everyone at Place A
        for hour in range(8, 18):
            minute = day * 1440 + hour * 60
            patterns[str(minute)] = {
                "homes": {},
                "places": {"0": people_ids.copy()}  # All at Place A
            }
        
        # Evening: everyone back home
        minute = day * 1440 + 18 * 60
        patterns[str(minute)] = {
            "homes": {"0": ["0", "1"], "1": ["2", "3", "4"]},
            "places": {}
        }
    
    # MONTH 2: Days 14-27 - Everyone at Place B during day hours
    for day in range(14, 28):
        # Morning: everyone at home
        minute = day * 1440
        patterns[str(minute)] = {
            "homes": {"0": ["0", "1"], "1": ["2", "3", "4"]},
            "places": {}
        }
        
        # Daytime (8am-6pm): everyone at Place B
        for hour in range(8, 18):
            minute = day * 1440 + hour * 60
            patterns[str(minute)] = {
                "homes": {},
                "places": {"1": people_ids.copy()}  # All at Place B
            }
        
        # Evening: everyone back home
        minute = day * 1440 + 18 * 60
        patterns[str(minute)] = {
            "homes": {"0": ["0", "1"], "1": ["2", "3", "4"]},
            "places": {}
        }
    
    return patterns


def create_cz_in_database():
    """
    Create a ConvenienceZone in the database with the test data.
    Requires the Fullstack server to be running.
    """
    import requests
    
    # First check if server is running
    try:
        response = requests.get("http://localhost:1890/convenience-zones", timeout=5)
    except requests.exceptions.ConnectionError:
        print("❌ Fullstack server not running. Start with: cd Fullstack/server && pnpm dev")
        return None
    
    # Load papdata
    papdata_path = MULTIMONTH_DIR / "papdata.json"
    with open(papdata_path) as f:
        papdata = json.load(f)
    
    # Create the CZ
    cz_data = {
        "name": "Multi-Month Test",
        "description": "MULTIMONTH",  # Used for location lookup
        "latitude": 39.0,
        "longitude": -76.5,
        "cbg_list": ["000000000001"],
        "size": len(papdata["people"]),
        "length": 672,  # 28 days in hours
        "start_date": "2019-01-01"
    }
    
    # You'll need to be authenticated - this is a simplified example
    print("\nTo create a CZ in the database:")
    print("1. Log in to the UI at http://localhost:5173")
    print("2. Create a new Convenience Zone with these settings:")
    print(f"   - Name: {cz_data['name']}")
    print(f"   - Description: {cz_data['description']}")
    print(f"   - CBG: {cz_data['cbg_list'][0]}")
    print("\nOr use the local location method (easier for testing)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Set up multi-month test for UI")
    parser.add_argument("--local", "-l", action="store_true",
                       help="Set up as local location (recommended)")
    parser.add_argument("--database", "-d", action="store_true",
                       help="Show instructions for database CZ")
    
    args = parser.parse_args()
    
    if args.database:
        create_cz_in_database()
    else:
        # Default to local setup
        setup_local_location()
