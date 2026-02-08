"""
Test Patterns CSV Generator for Delineo Simulation

Generates small SafeGraph-style patterns CSV files for testing.
These can be used with the Algorithms server for CZ generation testing.

Usage:
    python patterns_csv_generator.py                    # Generate with defaults
    python patterns_csv_generator.py --places 5         # 5 places
    python patterns_csv_generator.py --scenario office  # Office scenario
"""

import csv
import json
import random
import string
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

OUTPUT_DIR = Path(__file__).parent


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PlaceType:
    """Predefined place type with typical dwell times and hours."""
    name: str
    top_category: str
    sub_category: str
    median_dwell: int  # minutes
    typical_hours: List[int]  # hours when busy (0-23)
    weekend_factor: float = 0.5  # multiplier for weekend popularity


# Common place types with realistic parameters
PLACE_TYPES = {
    "grocery": PlaceType(
        name="Grocery Store",
        top_category="Shopping",
        sub_category="Grocery Store",
        median_dwell=35,
        typical_hours=[8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
        weekend_factor=1.2
    ),
    "restaurant": PlaceType(
        name="Restaurant",
        top_category="Food",
        sub_category="Restaurant",
        median_dwell=60,
        typical_hours=[11, 12, 13, 17, 18, 19, 20, 21],
        weekend_factor=1.5
    ),
    "cafe": PlaceType(
        name="Coffee Shop",
        top_category="Food",
        sub_category="Coffee Shop",
        median_dwell=30,
        typical_hours=[6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        weekend_factor=1.3
    ),
    "office": PlaceType(
        name="Office Building",
        top_category="Business",
        sub_category="Office Building",
        median_dwell=480,  # 8 hours
        typical_hours=[8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
        weekend_factor=0.1
    ),
    "gym": PlaceType(
        name="Fitness Center",
        top_category="Recreation",
        sub_category="Gym",
        median_dwell=75,
        typical_hours=[6, 7, 8, 9, 17, 18, 19, 20],
        weekend_factor=0.8
    ),
    "church": PlaceType(
        name="Church",
        top_category="Religious",
        sub_category="Church",
        median_dwell=90,
        typical_hours=[9, 10, 11, 18, 19],
        weekend_factor=3.0  # Much busier on Sunday
    ),
    "school": PlaceType(
        name="School",
        top_category="Education",
        sub_category="School",
        median_dwell=420,  # 7 hours
        typical_hours=[8, 9, 10, 11, 12, 13, 14, 15],
        weekend_factor=0.0
    ),
    "pharmacy": PlaceType(
        name="Pharmacy",
        top_category="Health",
        sub_category="Pharmacy",
        median_dwell=20,
        typical_hours=[8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
        weekend_factor=0.6
    ),
    "bar": PlaceType(
        name="Bar",
        top_category="Food",
        sub_category="Bar",
        median_dwell=120,
        typical_hours=[17, 18, 19, 20, 21, 22, 23],
        weekend_factor=2.0
    ),
    "bank": PlaceType(
        name="Bank",
        top_category="Finance",
        sub_category="Bank",
        median_dwell=25,
        typical_hours=[9, 10, 11, 12, 13, 14, 15, 16],
        weekend_factor=0.0
    ),
}


@dataclass
class TestPlace:
    """A place to include in the test patterns CSV."""
    placekey: str
    name: str
    place_type: PlaceType
    cbg: str
    latitude: float
    longitude: float
    postal_code: str = "00000"
    raw_visitor_counts: int = 100
    raw_visit_counts: int = 150


@dataclass
class TestPatternsScenario:
    """A complete test scenario with places."""
    name: str
    cbg: str = "000000000001"
    state_code: str = "00"
    date_range_start: str = "2019-01-01T00:00:00-05:00"
    date_range_end: str = "2019-02-01T00:00:00-05:00"
    places: List[TestPlace] = field(default_factory=list)


# =============================================================================
# PLACEKEY GENERATION
# =============================================================================

def generate_placekey(index: int = 0) -> str:
    """
    Generate a placekey-like identifier.
    Format: xxx-xxx@yyy-yyy-yyy
    """
    def rand_chars(n: int) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))
    
    # Use index to make deterministic but unique
    random.seed(42 + index)
    what = f"{rand_chars(3)}-{rand_chars(3)}"
    where = f"{rand_chars(3)}-{rand_chars(3)}-{rand_chars(3)}"
    return f"{what}@{where}"


# =============================================================================
# POPULARITY GENERATION
# =============================================================================

def generate_popularity_by_hour(place_type: PlaceType, noise: float = 0.2) -> List[int]:
    """
    Generate a 24-element array of hourly popularity.
    Based on typical_hours with some noise.
    """
    popularity = [0] * 24
    base_value = 100
    
    for hour in range(24):
        if hour in place_type.typical_hours:
            # Peak hours get higher values
            value = base_value + random.randint(50, 150)
        else:
            # Off-peak hours get lower values
            value = random.randint(0, 30)
        
        # Add noise
        value = max(0, int(value * (1 + random.uniform(-noise, noise))))
        popularity[hour] = value
    
    return popularity


def generate_popularity_by_day(place_type: PlaceType, noise: float = 0.2) -> Dict[str, int]:
    """
    Generate popularity by day of week.
    """
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    base_value = 100
    
    popularity = {}
    for i, day in enumerate(weekdays):
        if i < 5:  # Weekday
            value = base_value + random.randint(-20, 20)
        else:  # Weekend
            value = int(base_value * place_type.weekend_factor) + random.randint(-10, 10)
        
        value = max(0, int(value * (1 + random.uniform(-noise, noise))))
        popularity[day] = value
    
    return popularity


def generate_visitor_home_cbgs(home_cbg: str, num_visitors: int = 50) -> Dict[str, int]:
    """
    Generate visitor_home_cbgs - which CBGs visitors come from.
    Most visitors come from the same CBG, some from nearby (simulated).
    """
    cbgs = {}
    
    # Most visitors from the same CBG
    local_visitors = int(num_visitors * 0.6)
    cbgs[home_cbg] = local_visitors
    
    # Generate some "nearby" CBGs (just increment the last digit)
    remaining = num_visitors - local_visitors
    for i in range(min(5, remaining)):
        # Create a nearby CBG by modifying the last few digits
        nearby_cbg = home_cbg[:-1] + str((int(home_cbg[-1]) + i + 1) % 10)
        cbgs[nearby_cbg] = max(4, remaining // 5)
    
    return cbgs


# =============================================================================
# CSV GENERATION
# =============================================================================

def place_to_csv_row(place: TestPlace, scenario: TestPatternsScenario) -> Dict[str, Any]:
    """Convert a TestPlace to a CSV row dict."""
    
    popularity_by_hour = generate_popularity_by_hour(place.place_type)
    popularity_by_day = generate_popularity_by_day(place.place_type)
    visitor_home_cbgs = generate_visitor_home_cbgs(place.cbg, place.raw_visitor_counts)
    
    return {
        "brands": "",
        "bucketed_dwell_times": json.dumps({"<5": 10, "5-20": 30, "21-60": 40, "61-240": 15, ">240": 5}),
        "category_tags": place.place_type.sub_category,
        "city": "Test City",
        "closed_on": "",
        "date_range_end": scenario.date_range_end,
        "date_range_start": scenario.date_range_start,
        "device_type": json.dumps({"android": 50, "ios": 50}),
        "distance_from_home": "5000.0",
        "enclosed": "True",
        "geometry_type": "POLYGON",
        "includes_parking_lot": "False",
        "iso_country_code": "US",
        "is_synthetic": "False",
        "latitude": place.latitude,
        "location_name": place.name,
        "longitude": place.longitude,
        "median_dwell": place.place_type.median_dwell,
        "naics_code": "000000",
        "normalized_visits_by_region_naics_visitors": "0.1",
        "normalized_visits_by_region_naics_visits": "0.1",
        "normalized_visits_by_state_scaling": "1000.0",
        "normalized_visits_by_total_visitors": "0.001",
        "normalized_visits_by_total_visits": "0.001",
        "opened_on": "",
        "open_hours": "",
        "parent_placekey": "",
        "phone_number": "",
        "placekey": place.placekey,
        "poi_cbg": f"{place.cbg}.0",  # SafeGraph format includes .0
        "polygon_class": "OWNED_POLYGON",
        "polygon_wkt": f"POLYGON (({place.longitude} {place.latitude}, {place.longitude+0.001} {place.latitude}, {place.longitude+0.001} {place.latitude+0.001}, {place.longitude} {place.latitude+0.001}, {place.longitude} {place.latitude}))",
        "popularity_by_day": json.dumps(popularity_by_day),
        "popularity_by_hour": json.dumps(popularity_by_hour),
        "postal_code": place.postal_code,
        "raw_visitor_counts": place.raw_visitor_counts,
        "raw_visit_counts": place.raw_visit_counts,
        "related_same_day_brand": "",
        "related_same_month_brand": "",
        "safegraph_brand_ids": "",
        "store_id": "",
        "street_address": f"{random.randint(100, 9999)} Test St",
        "sub_category": place.place_type.sub_category,
        "top_category": place.place_type.top_category,
        "tracking_closed_since": "",
        "visitor_country_of_origin": json.dumps({"US": place.raw_visitor_counts}),
        "visitor_daytime_cbgs": "",
        "visitor_home_aggregation": "",
        "visitor_home_cbgs": json.dumps(visitor_home_cbgs),
        "visits_by_day": json.dumps([random.randint(5, 20) for _ in range(31)]),
        "websites": "",
        "wkt_area_sq_meters": "1000.0"
    }


def generate_patterns_csv(scenario: TestPatternsScenario, output_path: Path) -> Path:
    """Generate a patterns CSV file from a scenario."""
    
    # Define column order (matching SafeGraph format)
    columns = [
        "brands", "bucketed_dwell_times", "category_tags", "city", "closed_on",
        "date_range_end", "date_range_start", "device_type", "distance_from_home",
        "enclosed", "geometry_type", "includes_parking_lot", "iso_country_code",
        "is_synthetic", "latitude", "location_name", "longitude", "median_dwell",
        "naics_code", "normalized_visits_by_region_naics_visitors",
        "normalized_visits_by_region_naics_visits", "normalized_visits_by_state_scaling",
        "normalized_visits_by_total_visitors", "normalized_visits_by_total_visits",
        "opened_on", "open_hours", "parent_placekey", "phone_number", "placekey",
        "poi_cbg", "polygon_class", "polygon_wkt", "popularity_by_day",
        "popularity_by_hour", "postal_code", "raw_visitor_counts", "raw_visit_counts",
        "related_same_day_brand", "related_same_month_brand", "safegraph_brand_ids",
        "store_id", "street_address", "sub_category", "top_category",
        "tracking_closed_since", "visitor_country_of_origin", "visitor_daytime_cbgs",
        "visitor_home_aggregation", "visitor_home_cbgs", "visits_by_day", "websites",
        "wkt_area_sq_meters"
    ]
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        
        for place in scenario.places:
            row = place_to_csv_row(place, scenario)
            writer.writerow(row)
    
    return output_path


# =============================================================================
# PREDEFINED SCENARIOS
# =============================================================================

def scenario_minimal() -> TestPatternsScenario:
    """Minimal scenario: 3 places in one CBG."""
    scenario = TestPatternsScenario(name="minimal")
    
    scenario.places = [
        TestPlace(
            placekey=generate_placekey(0),
            name="Test Grocery",
            place_type=PLACE_TYPES["grocery"],
            cbg=scenario.cbg,
            latitude=39.0,
            longitude=-76.5,
            raw_visitor_counts=50,
            raw_visit_counts=80
        ),
        TestPlace(
            placekey=generate_placekey(1),
            name="Test Cafe",
            place_type=PLACE_TYPES["cafe"],
            cbg=scenario.cbg,
            latitude=39.001,
            longitude=-76.501,
            raw_visitor_counts=30,
            raw_visit_counts=45
        ),
        TestPlace(
            placekey=generate_placekey(2),
            name="Test Restaurant",
            place_type=PLACE_TYPES["restaurant"],
            cbg=scenario.cbg,
            latitude=39.002,
            longitude=-76.502,
            raw_visitor_counts=40,
            raw_visit_counts=60
        ),
    ]
    
    return scenario


def scenario_neighborhood() -> TestPatternsScenario:
    """Small neighborhood: 6 places across 2 CBGs."""
    scenario = TestPatternsScenario(name="neighborhood")
    cbg1 = "000000000001"
    cbg2 = "000000000002"
    
    scenario.places = [
        # CBG 1 places
        TestPlace(
            placekey=generate_placekey(10),
            name="Corner Store",
            place_type=PLACE_TYPES["grocery"],
            cbg=cbg1,
            latitude=39.0,
            longitude=-76.5,
            raw_visitor_counts=60,
            raw_visit_counts=100
        ),
        TestPlace(
            placekey=generate_placekey(11),
            name="Local Pharmacy",
            place_type=PLACE_TYPES["pharmacy"],
            cbg=cbg1,
            latitude=39.001,
            longitude=-76.501,
            raw_visitor_counts=40,
            raw_visit_counts=55
        ),
        TestPlace(
            placekey=generate_placekey(12),
            name="Morning Cafe",
            place_type=PLACE_TYPES["cafe"],
            cbg=cbg1,
            latitude=39.002,
            longitude=-76.502,
            raw_visitor_counts=35,
            raw_visit_counts=50
        ),
        # CBG 2 places
        TestPlace(
            placekey=generate_placekey(20),
            name="Fitness Plus",
            place_type=PLACE_TYPES["gym"],
            cbg=cbg2,
            latitude=39.01,
            longitude=-76.51,
            raw_visitor_counts=45,
            raw_visit_counts=70
        ),
        TestPlace(
            placekey=generate_placekey(21),
            name="Family Restaurant",
            place_type=PLACE_TYPES["restaurant"],
            cbg=cbg2,
            latitude=39.011,
            longitude=-76.511,
            raw_visitor_counts=50,
            raw_visit_counts=75
        ),
        TestPlace(
            placekey=generate_placekey(22),
            name="Community Bank",
            place_type=PLACE_TYPES["bank"],
            cbg=cbg2,
            latitude=39.012,
            longitude=-76.512,
            raw_visitor_counts=30,
            raw_visit_counts=40
        ),
    ]
    
    return scenario


def scenario_office_park() -> TestPatternsScenario:
    """Office park scenario: offices + supporting businesses."""
    scenario = TestPatternsScenario(name="office_park")
    
    scenario.places = [
        TestPlace(
            placekey=generate_placekey(100),
            name="Tech Office Building A",
            place_type=PLACE_TYPES["office"],
            cbg=scenario.cbg,
            latitude=39.0,
            longitude=-76.5,
            raw_visitor_counts=200,
            raw_visit_counts=1000  # High visits due to daily workers
        ),
        TestPlace(
            placekey=generate_placekey(101),
            name="Tech Office Building B",
            place_type=PLACE_TYPES["office"],
            cbg=scenario.cbg,
            latitude=39.001,
            longitude=-76.501,
            raw_visitor_counts=150,
            raw_visit_counts=750
        ),
        TestPlace(
            placekey=generate_placekey(102),
            name="Office Cafe",
            place_type=PLACE_TYPES["cafe"],
            cbg=scenario.cbg,
            latitude=39.0005,
            longitude=-76.5005,
            raw_visitor_counts=100,
            raw_visit_counts=300
        ),
        TestPlace(
            placekey=generate_placekey(103),
            name="Lunch Spot",
            place_type=PLACE_TYPES["restaurant"],
            cbg=scenario.cbg,
            latitude=39.002,
            longitude=-76.502,
            raw_visitor_counts=80,
            raw_visit_counts=200
        ),
    ]
    
    return scenario


SCENARIOS = {
    "minimal": scenario_minimal,
    "neighborhood": scenario_neighborhood,
    "office_park": scenario_office_park,
}


# =============================================================================
# SCENARIO BUILDER
# =============================================================================

class PatternsCsvBuilder:
    """Fluent builder for creating custom patterns CSV scenarios."""
    
    def __init__(self, name: str = "custom"):
        self.scenario = TestPatternsScenario(name=name)
        self._place_counter = 0
    
    def set_cbg(self, cbg: str) -> "PatternsCsvBuilder":
        self.scenario.cbg = cbg
        return self
    
    def set_date_range(self, start: str, end: str) -> "PatternsCsvBuilder":
        self.scenario.date_range_start = start
        self.scenario.date_range_end = end
        return self
    
    def add_place(
        self,
        name: str,
        place_type: str,  # Key from PLACE_TYPES
        cbg: str = None,
        latitude: float = None,
        longitude: float = None,
        raw_visitor_counts: int = 50,
        raw_visit_counts: int = 80
    ) -> str:
        """Add a place and return its placekey."""
        if place_type not in PLACE_TYPES:
            raise ValueError(f"Unknown place type: {place_type}. Available: {list(PLACE_TYPES.keys())}")
        
        placekey = generate_placekey(self._place_counter)
        self._place_counter += 1
        
        # Default coordinates with small offset per place
        if latitude is None:
            latitude = 39.0 + (self._place_counter * 0.001)
        if longitude is None:
            longitude = -76.5 + (self._place_counter * 0.001)
        
        self.scenario.places.append(TestPlace(
            placekey=placekey,
            name=name,
            place_type=PLACE_TYPES[place_type],
            cbg=cbg or self.scenario.cbg,
            latitude=latitude,
            longitude=longitude,
            raw_visitor_counts=raw_visitor_counts,
            raw_visit_counts=raw_visit_counts
        ))
        
        return placekey
    
    def build(self) -> TestPatternsScenario:
        return self.scenario


# =============================================================================
# CLI
# =============================================================================

def save_scenario(scenario: TestPatternsScenario, output_dir: Path = OUTPUT_DIR) -> Path:
    """Save a scenario to a patterns CSV file."""
    # Create state folder structure like OK/
    state_dir = output_dir / "TEST"
    state_dir.mkdir(exist_ok=True)
    
    # Parse date for filename
    date_str = scenario.date_range_start.split("T")[0]  # "2019-01-01"
    year_month = date_str[:7]  # "2019-01"
    
    filename = f"{year_month}-TEST.csv"
    output_path = state_dir / filename
    
    generate_patterns_csv(scenario, output_path)
    
    print(f"✓ Generated patterns CSV: {output_path}")
    print(f"  - Scenario: {scenario.name}")
    print(f"  - Places: {len(scenario.places)}")
    print(f"  - Date range: {scenario.date_range_start} to {scenario.date_range_end}")
    print(f"  - CBG: {scenario.cbg}")
    
    # Also save a metadata file
    meta = {
        "scenario_name": scenario.name,
        "num_places": len(scenario.places),
        "cbg": scenario.cbg,
        "date_range_start": scenario.date_range_start,
        "date_range_end": scenario.date_range_end,
        "places": [
            {
                "placekey": p.placekey,
                "name": p.name,
                "type": p.place_type.name,
                "cbg": p.cbg,
            }
            for p in scenario.places
        ]
    }
    meta_path = state_dir / f"{year_month}-TEST-meta.json"
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    print(f"  - Metadata: {meta_path}")
    
    return output_path


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Patterns CSV Generator")
    parser.add_argument("--scenario", "-s", choices=list(SCENARIOS.keys()),
                       default="minimal", help="Predefined scenario to use")
    parser.add_argument("--list", action="store_true",
                       help="List available scenarios and place types")
    parser.add_argument("--output", "-o", type=Path, default=OUTPUT_DIR,
                       help="Output directory")
    
    args = parser.parse_args()
    
    if args.list:
        print("Available scenarios:")
        for name, factory in SCENARIOS.items():
            s = factory()
            print(f"  {name}: {len(s.places)} places")
        
        print("\nAvailable place types:")
        for name, pt in PLACE_TYPES.items():
            print(f"  {name}: {pt.name} (median dwell: {pt.median_dwell} min)")
        return
    
    # Generate scenario
    scenario = SCENARIOS[args.scenario]()
    save_scenario(scenario, args.output)


if __name__ == "__main__":
    main()
