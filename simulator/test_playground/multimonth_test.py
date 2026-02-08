"""
Multi-Month Test Script

Creates test data for multi-month simulation testing:
- 2 places (Place A for month 1, Place B for month 2)
- 2 patterns CSV files where visitors exclusively go to one place per month

Usage:
    python multimonth_test.py              # Generate test CSVs
    python multimonth_test.py --run        # Generate and run multi-month simulation
"""

import json
from pathlib import Path
from datetime import datetime
from patterns_csv_generator import (
    TestPatternsScenario,
    TestPlace,
    PlaceType,
    PLACE_TYPES,
    generate_patterns_csv,
    generate_placekey,
)

OUTPUT_DIR = Path(__file__).parent


# =============================================================================
# CUSTOM PLACE TYPES FOR TESTING
# =============================================================================

# Place A - very popular in all hours (so everyone goes there)
PLACE_A_TYPE = PlaceType(
    name="Test Place A",
    top_category="Testing",
    sub_category="Test Location A",
    median_dwell=60,
    typical_hours=list(range(24)),  # All hours
    weekend_factor=1.0
)

# Place B - same configuration
PLACE_B_TYPE = PlaceType(
    name="Test Place B",
    top_category="Testing",
    sub_category="Test Location B",
    median_dwell=60,
    typical_hours=list(range(24)),
    weekend_factor=1.0
)


# =============================================================================
# TEST DATA GENERATION
# =============================================================================

def create_month1_scenario() -> TestPatternsScenario:
    """
    Month 1: Only Place A has visitors.
    Place B exists but has zero popularity.
    """
    scenario = TestPatternsScenario(
        name="multimonth_month1",
        cbg="000000000001",
        date_range_start="2019-01-01T00:00:00-05:00",
        date_range_end="2019-02-01T00:00:00-05:00",
    )
    
    # Place A - HIGH popularity (everyone goes here in month 1)
    scenario.places = [
        TestPlace(
            placekey="aaa-111@test-month-one",
            name="Place A (Month 1 Destination)",
            place_type=PLACE_A_TYPE,
            cbg=scenario.cbg,
            latitude=39.0,
            longitude=-76.5,
            raw_visitor_counts=500,  # High visitor count
            raw_visit_counts=1000,
        ),
        # Place B exists but with ZERO visitors in month 1
        TestPlace(
            placekey="bbb-222@test-month-two",
            name="Place B (Closed in Month 1)",
            place_type=PlaceType(
                name="Test Place B (Closed)",
                top_category="Testing",
                sub_category="Test Location B",
                median_dwell=60,
                typical_hours=[],  # No busy hours = no visits
                weekend_factor=0.0
            ),
            cbg=scenario.cbg,
            latitude=39.01,
            longitude=-76.51,
            raw_visitor_counts=0,  # No visitors
            raw_visit_counts=0,
        ),
    ]
    
    return scenario


def create_month2_scenario() -> TestPatternsScenario:
    """
    Month 2: Only Place B has visitors.
    Place A exists but has zero popularity.
    """
    scenario = TestPatternsScenario(
        name="multimonth_month2",
        cbg="000000000001",
        date_range_start="2019-02-01T00:00:00-05:00",
        date_range_end="2019-03-01T00:00:00-05:00",
    )
    
    # Place A - ZERO visitors in month 2
    scenario.places = [
        TestPlace(
            placekey="aaa-111@test-month-one",
            name="Place A (Closed in Month 2)",
            place_type=PlaceType(
                name="Test Place A (Closed)",
                top_category="Testing",
                sub_category="Test Location A",
                median_dwell=60,
                typical_hours=[],  # No busy hours
                weekend_factor=0.0
            ),
            cbg=scenario.cbg,
            latitude=39.0,
            longitude=-76.5,
            raw_visitor_counts=0,
            raw_visit_counts=0,
        ),
        # Place B - HIGH popularity (everyone goes here in month 2)
        TestPlace(
            placekey="bbb-222@test-month-two",
            name="Place B (Month 2 Destination)",
            place_type=PLACE_B_TYPE,
            cbg=scenario.cbg,
            latitude=39.01,
            longitude=-76.51,
            raw_visitor_counts=500,
            raw_visit_counts=1000,
        ),
    ]
    
    return scenario


def generate_multimonth_csvs(output_dir: Path = OUTPUT_DIR) -> tuple:
    """Generate both month CSV files."""
    
    # Create output directory
    test_dir = output_dir / "MULTIMONTH"
    test_dir.mkdir(exist_ok=True)
    
    # Generate Month 1 CSV
    month1_scenario = create_month1_scenario()
    month1_path = test_dir / "2019-01-MULTIMONTH.csv"
    generate_patterns_csv(month1_scenario, month1_path)
    print(f"✓ Generated Month 1 CSV: {month1_path}")
    print(f"  - Place A: 500 visitors (active)")
    print(f"  - Place B: 0 visitors (closed)")
    
    # Generate Month 2 CSV
    month2_scenario = create_month2_scenario()
    month2_path = test_dir / "2019-02-MULTIMONTH.csv"
    generate_patterns_csv(month2_scenario, month2_path)
    print(f"✓ Generated Month 2 CSV: {month2_path}")
    print(f"  - Place A: 0 visitors (closed)")
    print(f"  - Place B: 500 visitors (active)")
    
    # Save metadata
    meta = {
        "description": "Multi-month test: Place A active in month 1, Place B active in month 2",
        "cbg": "000000000001",
        "places": {
            "place_a": {
                "placekey": "aaa-111@test-month-one",
                "name": "Place A",
                "active_month": "2019-01",
            },
            "place_b": {
                "placekey": "bbb-222@test-month-two",
                "name": "Place B",
                "active_month": "2019-02",
            }
        },
        "files": {
            "month1": str(month1_path),
            "month2": str(month2_path),
        }
    }
    meta_path = test_dir / "multimonth-meta.json"
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    print(f"✓ Metadata: {meta_path}")
    
    return month1_path, month2_path


def generate_test_papdata(output_dir: Path = OUTPUT_DIR) -> Path:
    """
    Generate minimal papdata.json for multi-month testing.
    5 people, 2 homes, 2 places (matching the patterns CSVs).
    """
    test_dir = output_dir / "MULTIMONTH"
    test_dir.mkdir(exist_ok=True)
    
    papdata = {
        "people": {
            "0": {"sex": 0, "age": 30, "home": "0"},
            "1": {"sex": 1, "age": 28, "home": "0"},
            "2": {"sex": 0, "age": 35, "home": "1"},
            "3": {"sex": 1, "age": 33, "home": "1"},
            "4": {"sex": 0, "age": 25, "home": "1"},
        },
        "homes": {
            "0": {"cbg": "000000000001", "members": 2},
            "1": {"cbg": "000000000001", "members": 3},
        },
        "places": {
            # Place A - uses the placekey from month 1 patterns
            # Using "Restaurants and Other Eating Places" for a recognizable icon 🍽️
            "0": {
                "placekey": "aaa-111@test-month-one",
                "label": "Place A (Restaurant)",
                "cbg": "-1",
                "latitude": 39.0,
                "longitude": -76.5,
                "capacity": 100,
                "top_category": "Restaurants and Other Eating Places"
            },
            # Place B - uses the placekey from month 2 patterns
            # Using "Grocery Stores" for a recognizable icon 🛒
            "1": {
                "placekey": "bbb-222@test-month-two",
                "label": "Place B (Grocery)",
                "cbg": "-1",
                "latitude": 39.01,
                "longitude": -76.51,
                "capacity": 100,
                "top_category": "Grocery Stores"
            },
        }
    }
    
    papdata_path = test_dir / "papdata.json"
    with open(papdata_path, 'w') as f:
        json.dump(papdata, f, indent=2)
    
    print(f"✓ Generated papdata: {papdata_path}")
    print(f"  - 5 people in 2 homes")
    print(f"  - 2 places (Place A, Place B)")
    
    return papdata_path


def run_multimonth_simulation():
    """Run a multi-month simulation using the generated test data."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from datetime import datetime, timedelta
    
    test_dir = OUTPUT_DIR / "MULTIMONTH"
    
    # Load papdata
    papdata_path = test_dir / "papdata.json"
    with open(papdata_path) as f:
        papdata = json.load(f)
    
    print("\n" + "="*60)
    print("MULTI-MONTH SIMULATION TEST")
    print("="*60)
    print(f"People: {len(papdata['people'])}")
    print(f"Homes: {len(papdata['homes'])}")
    print(f"Places: {len(papdata['places'])}")
    
    # Import the patterns generator from Algorithms
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "Algorithms" / "server"))
    
    try:
        from patterns import gen_patterns
        
        # Generate patterns for Month 1
        print("\n--- Month 1 (January 2019) ---")
        start_time_m1 = datetime(2019, 1, 15)  # Mid-January
        patterns_m1 = gen_patterns(
            papdata,
            start_time_m1,
            duration=168,  # 1 week
            patterns_file=str(test_dir / "2019-01-MULTIMONTH.csv")
        )
        
        # Analyze month 1 patterns
        place_visits_m1 = {"0": 0, "1": 0}  # Place A = 0, Place B = 1
        for ts, data in patterns_m1.items():
            for place_id, visitors in data.get("places", {}).items():
                if place_id in place_visits_m1:
                    place_visits_m1[place_id] += len(visitors)
        
        print(f"Place A visits: {place_visits_m1['0']}")
        print(f"Place B visits: {place_visits_m1['1']}")
        
        # Generate patterns for Month 2
        print("\n--- Month 2 (February 2019) ---")
        start_time_m2 = datetime(2019, 2, 15)  # Mid-February
        patterns_m2 = gen_patterns(
            papdata,
            start_time_m2,
            duration=168,  # 1 week
            patterns_file=str(test_dir / "2019-02-MULTIMONTH.csv")
        )
        
        # Analyze month 2 patterns
        place_visits_m2 = {"0": 0, "1": 0}
        for ts, data in patterns_m2.items():
            for place_id, visitors in data.get("places", {}).items():
                if place_id in place_visits_m2:
                    place_visits_m2[place_id] += len(visitors)
        
        print(f"Place A visits: {place_visits_m2['0']}")
        print(f"Place B visits: {place_visits_m2['1']}")
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Month 1: Place A={place_visits_m1['0']} visits, Place B={place_visits_m1['1']} visits")
        print(f"Month 2: Place A={place_visits_m2['0']} visits, Place B={place_visits_m2['1']} visits")
        
        if place_visits_m1['0'] > place_visits_m1['1'] and place_visits_m2['1'] > place_visits_m2['0']:
            print("\n✓ SUCCESS: Movement patterns correctly switched between months!")
        else:
            print("\n✗ UNEXPECTED: Movement patterns did not switch as expected")
        
        # Save patterns for inspection
        with open(test_dir / "patterns_month1.json", 'w') as f:
            json.dump(patterns_m1, f, indent=2)
        with open(test_dir / "patterns_month2.json", 'w') as f:
            json.dump(patterns_m2, f, indent=2)
        print(f"\nPatterns saved to {test_dir}/patterns_month*.json")
        
    except ImportError as e:
        print(f"\nCould not import patterns module: {e}")
        print("Make sure Algorithms/server is accessible")
        print("\nGenerated files can still be used manually:")
        print(f"  - {test_dir / '2019-01-MULTIMONTH.csv'}")
        print(f"  - {test_dir / '2019-02-MULTIMONTH.csv'}")
        print(f"  - {test_dir / 'papdata.json'}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Month Test Generator")
    parser.add_argument("--run", "-r", action="store_true",
                       help="Generate test data and run simulation")
    
    args = parser.parse_args()
    
    # Always generate the CSV files and papdata
    print("Generating multi-month test data...\n")
    generate_multimonth_csvs()
    print()
    generate_test_papdata()
    
    if args.run:
        run_multimonth_simulation()
    else:
        print("\nRun with --run to test pattern generation")


if __name__ == "__main__":
    main()
