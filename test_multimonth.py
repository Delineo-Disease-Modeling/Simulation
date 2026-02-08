#!/usr/bin/env python3
"""
Test script for multi-month simulation.

Creates synthetic patterns.json files for January and February with distinct
characteristics to verify month transitions work correctly.

Test period: Jan 20, 2019 to Feb 10, 2019
- January (Jan 20-31): 12 days
- February (Feb 1-10): 10 days

The test creates pattern files where:
- January: Everyone visits Place "1" (Andy's Hamburgers)
- February: Everyone visits Place "2" (Ascension Health)

This makes it obvious when patterns switch by watching which place gets visits.
The simulation logs will show which pattern file is being used.
"""

import os
import sys
import json
import requests
from datetime import datetime

# Test configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DATA_DIR = os.path.join(SCRIPT_DIR, 'test_data')
START_DATE = '2019-01-20'
END_DATE = '2019-02-10'


def create_test_directories():
    """Create test data directories."""
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    print(f"[TEST] Created test directory: {TEST_DATA_DIR}")


def load_barnsdall_papdata():
    """Load the barnsdall papdata to get place info."""
    papdata_path = os.path.join(SCRIPT_DIR, 'simulator/barnsdall/papdata.json')
    with open(papdata_path, 'r') as f:
        papdata = json.load(f)
    
    people = papdata.get('people', {})
    places = papdata.get('places', {})
    homes = papdata.get('homes', {})
    
    print(f"[TEST] Loaded barnsdall: {len(people)} people, {len(homes)} homes, {len(places)} places")
    
    # Show first few places
    print("[TEST] Sample places:")
    for pid, pinfo in list(places.items())[:5]:
        print(f"  Place {pid}: {pinfo.get('label', 'Unknown')}")
    
    return papdata


def create_patterns_json_for_month(output_path: str, papdata: dict, month_tag: str, 
                                    primary_place: str, duration_hours: int):
    """
    Create a patterns.json file for a specific month.
    
    Format: {"60": {"homes": {...}, "places": {...}}, "120": {...}, ...}
    Keys are minutes from simulation start.
    
    For testing, we'll make everyone go to the primary_place during business hours.
    """
    people = papdata.get('people', {})
    places = papdata.get('places', {})
    
    print(f"[TEST] Creating {month_tag} patterns: primary_place={primary_place}")
    print(f"[TEST]   Place name: {places.get(primary_place, {}).get('label', 'Unknown')}")
    print(f"[TEST]   Duration: {duration_hours} hours")
    
    patterns = {}
    
    # Generate patterns every 60 minutes
    for hour in range(duration_hours):
        minute_key = str((hour + 1) * 60)  # "60", "120", etc.
        
        homes_pattern = {}
        places_pattern = {}
        
        # Get hour of day (0-23)
        hour_of_day = hour % 24
        
        # Business hours: 8am-6pm = hours 8-17
        is_business_hours = 8 <= hour_of_day <= 17
        
        for pid, pinfo in people.items():
            home_id = str(pinfo.get('home', '0'))
            
            if is_business_hours:
                # During business hours, 50% of people go to primary_place
                if int(pid) % 2 == 0:  # Even IDs go out
                    if primary_place not in places_pattern:
                        places_pattern[primary_place] = []
                    places_pattern[primary_place].append(pid)
                else:
                    # Odd IDs stay home
                    if home_id not in homes_pattern:
                        homes_pattern[home_id] = []
                    homes_pattern[home_id].append(pid)
            else:
                # Outside business hours, everyone home
                if home_id not in homes_pattern:
                    homes_pattern[home_id] = []
                homes_pattern[home_id].append(pid)
        
        patterns[minute_key] = {
            "homes": homes_pattern,
            "places": places_pattern
        }
    
    # Write patterns file
    with open(output_path, 'w') as f:
        json.dump(patterns, f)
    
    # Verify
    total_timesteps = len(patterns)
    sample_key = "540"  # 9am (9*60)
    if sample_key in patterns:
        place_visitors = len(patterns[sample_key].get('places', {}).get(primary_place, []))
        print(f"[TEST]   Wrote {total_timesteps} timesteps")
        print(f"[TEST]   Sample (9am): {place_visitors} people at place {primary_place}")
    
    print(f"[TEST] Created: {output_path}")
    return patterns


def create_test_pattern_files():
    """Create January and February test pattern files."""
    papdata = load_barnsdall_papdata()
    
    # January: 12 days (Jan 20-31), everyone goes to Place "1" (Andy's Hamburgers)
    jan_path = os.path.join(TEST_DATA_DIR, 'patterns_january.json')
    jan_patterns = create_patterns_json_for_month(
        jan_path, papdata, 'JANUARY', 
        primary_place="1",  # Andy's Hamburgers
        duration_hours=12 * 24  # 12 days
    )
    
    # February: 10 days (Feb 1-10), everyone goes to Place "2" (Ascension Health)
    feb_path = os.path.join(TEST_DATA_DIR, 'patterns_february.json')
    feb_patterns = create_patterns_json_for_month(
        feb_path, papdata, 'FEBRUARY',
        primary_place="2",  # Ascension Health  
        duration_hours=10 * 24  # 10 days
    )
    
    # Also save a copy of papdata for completeness
    papdata_path = os.path.join(TEST_DATA_DIR, 'papdata.json')
    with open(papdata_path, 'w') as f:
        json.dump(papdata, f)
    print(f"[TEST] Copied papdata to: {papdata_path}")
    
    return papdata, jan_patterns, feb_patterns


def verify_patterns_differ(jan_patterns: dict, feb_patterns: dict):
    """Verify that January and February patterns are different."""
    print("\n[VERIFY] Checking pattern differences...")
    
    # Check 9am (hour 9 = minute 540)
    jan_9am = jan_patterns.get("540", {}).get("places", {})
    feb_9am = feb_patterns.get("540", {}).get("places", {})
    
    print(f"[VERIFY] January 9am places: {list(jan_9am.keys())}")
    print(f"[VERIFY] February 9am places: {list(feb_9am.keys())}")
    
    jan_place_1 = len(jan_9am.get("1", []))
    jan_place_2 = len(jan_9am.get("2", []))
    feb_place_1 = len(feb_9am.get("1", []))
    feb_place_2 = len(feb_9am.get("2", []))
    
    print(f"[VERIFY] January: Place 1 has {jan_place_1} visitors, Place 2 has {jan_place_2} visitors")
    print(f"[VERIFY] February: Place 1 has {feb_place_1} visitors, Place 2 has {feb_place_2} visitors")
    
    if jan_place_1 > jan_place_2 and feb_place_2 > feb_place_1:
        print("[VERIFY] ✓ Patterns are correctly different between months!")
        return True
    else:
        print("[VERIFY] ✗ WARNING: Patterns may not be sufficiently different")
        return False


def print_test_instructions():
    """Print instructions for manual testing."""
    print("\n" + "=" * 60)
    print("TEST FILES CREATED")
    print("=" * 60)
    print(f"""
The test created synthetic patterns files in:
  {TEST_DATA_DIR}/

Files:
  - patterns_january.json (Place "1" is popular)
  - patterns_february.json (Place "2" is popular)
  - papdata.json (copy of barnsdall data)

These files simulate different movement patterns between months.

To test multi-month simulation manually:

1. First, verify the simulation server is running:
   curl http://localhost:1870/

2. The current multi-month endpoint expects SafeGraph CSVs, not pre-made 
   patterns.json files. To properly test, you have two options:

   OPTION A: Use the existing OK data (real SafeGraph CSVs):
   
   curl -X POST http://localhost:1870/simulation/ \\
     -H "Content-Type: application/json" \\
     -d '{{
       "start_date": "2019-01-20",
       "end_date": "2019-02-10", 
       "state": "OK",
       "location": "barnsdall",
       "initial_infected_count": 3
     }}'

   OPTION B: Modify the simulation to accept pre-made patterns.json files.
   This would require code changes to app.py.

3. Watch the logs for month switching:
   tail -f .logs/simulation.log | grep -E "(MONTH|patterns)"

   Look for:
   [SIMULATION] MONTH: 2019-01
   [SIMULATION] Patterns CSV file: .../2019-01-OK.csv
   ...
   [SIMULATION] MONTH: 2019-02
   [SIMULATION] Patterns CSV file: .../2019-02-OK.csv

The key verification is that the simulation uses different pattern files
for each month and that state (infections) persists across the month boundary.
""")


def main():
    print("=" * 60)
    print("MULTI-MONTH SIMULATION TEST")
    print(f"Test period: {START_DATE} to {END_DATE}")
    print("=" * 60)
    print()
    
    # Step 1: Create test directories
    create_test_directories()
    
    # Step 2: Create synthetic pattern files
    print("\n[STEP 1] Creating synthetic pattern files...")
    papdata, jan_patterns, feb_patterns = create_test_pattern_files()
    
    # Step 3: Verify patterns are different
    print("\n[STEP 2] Verifying patterns differ...")
    verify_patterns_differ(jan_patterns, feb_patterns)
    
    # Step 4: Print instructions
    print_test_instructions()


if __name__ == '__main__':
    main()
