#!/usr/bin/env python3
"""
Create Multi-Month Test ConvenienceZone in Database

This script creates a full ConvenienceZone in the database with:
- User account (registers or logs in)
- ConvenienceZone record
- PaPData (people, homes, places)
- MovementPatterns

After running this, you can select "Multi-Month Test" in the UI dropdown.

Usage:
    python create_cz_database.py              # Create with defaults
    python create_cz_database.py --clean      # Delete existing test CZ first
    python create_cz_database.py --check      # Just check if CZ exists

Requirements:
    - Fullstack server running: cd Fullstack/server && pnpm dev
    - PostgreSQL database running
"""

import json
import requests
from pathlib import Path
from datetime import datetime
import sys

# Configuration
API_BASE = "http://localhost:1890"
SCRIPT_DIR = Path(__file__).parent
MULTIMONTH_DIR = SCRIPT_DIR / "MULTIMONTH"

# Test user credentials
TEST_USER = {
    "name": "Test User",
    "email": "test@delineo.local",
    "password": "testpass123",
    "organization": "Delineo Test"
}


class DelineoAPI:
    """Helper class for Delineo API calls."""
    
    def __init__(self, base_url: str = API_BASE):
        self.base_url = base_url
        self.session = requests.Session()
        self.user_id = None
    
    def check_server(self) -> bool:
        """Check if the server is running."""
        try:
            response = self.session.get(f"{self.base_url}/convenience-zones", timeout=5)
            return response.ok
        except requests.exceptions.ConnectionError:
            return False
    
    def register_or_login(self, email: str, password: str, name: str = None, organization: str = None) -> dict:
        """Register a new user or login if exists."""
        # Try to register first
        if name and organization:
            response = self.session.post(
                f"{self.base_url}/auth/register",
                json={
                    "email": email,
                    "password": password,
                    "name": name,
                    "organization": organization
                }
            )
            if response.ok:
                data = response.json()
                self.user_id = data["data"]["id"]
                print(f"✓ Registered new user: {email}")
                return data["data"]
            elif response.status_code != 409:  # Not "already exists"
                print(f"Registration failed: {response.text}")
        
        # Try to login
        response = self.session.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password}
        )
        if response.ok:
            data = response.json()
            self.user_id = data["data"]["id"]
            print(f"✓ Logged in as: {email}")
            return data["data"]
        else:
            raise Exception(f"Login failed: {response.text}")
    
    def get_convenience_zones(self, user_id: str = None) -> list:
        """Get all convenience zones."""
        params = {"user_id": user_id} if user_id else {}
        response = self.session.get(f"{self.base_url}/convenience-zones", params=params)
        if response.ok:
            return response.json().get("data", [])
        return []
    
    def create_convenience_zone(self, name: str, description: str, cbg_list: list,
                                latitude: float, longitude: float, 
                                start_date: str, length: int, size: int) -> dict:
        """Create a new convenience zone."""
        response = self.session.post(
            f"{self.base_url}/convenience-zones",
            json={
                "name": name,
                "description": description,
                "cbg_list": cbg_list,
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date,
                "length": length,
                "size": size,
                "user_id": self.user_id
            }
        )
        if response.ok:
            return response.json().get("data")
        else:
            raise Exception(f"Failed to create CZ: {response.text}")
    
    def delete_convenience_zone(self, czone_id: int) -> bool:
        """Delete a convenience zone."""
        response = self.session.delete(f"{self.base_url}/convenience-zones/{czone_id}")
        return response.ok
    
    def save_simdata(self, czone_id: int, name: str, simdata: dict, 
                     movement: dict, papdata: dict, hours: int = 672) -> dict:
        """Save simulation data (which also creates PaPData)."""
        response = self.session.post(
            f"{self.base_url}/simdata-json",
            json={
                "czone_id": czone_id,
                "name": name,
                "simdata": simdata,
                "movement": movement,
                "papdata": papdata,
                "hours": hours,
                "mask_rate": 0.0,
                "vaccine_rate": 0.0,
                "capacity": 1.0,
                "lockdown": 0.0
            }
        )
        if response.ok:
            return response.json().get("data")
        else:
            raise Exception(f"Failed to save simdata: {response.text}")
    
    def upload_patterns(self, czone_id: int, papdata: dict, patterns: dict) -> dict:
        """
        Upload patterns and papdata as files to create MovementPattern record.
        This is required for the /patterns/:czone_id endpoint to work.
        """
        import tempfile
        import os
        
        # Create temp files for the multipart upload
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as pf:
            json.dump(papdata, pf)
            papdata_path = pf.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as pf:
            json.dump(patterns, pf)
            patterns_path = pf.name
        
        try:
            with open(papdata_path, 'rb') as pap_file, open(patterns_path, 'rb') as pat_file:
                files = {
                    'papdata': ('papdata.json', pap_file, 'application/json'),
                    'patterns': ('patterns.json', pat_file, 'application/json'),
                }
                data = {'czone_id': str(czone_id)}
                
                response = self.session.post(
                    f"{self.base_url}/patterns",
                    files=files,
                    data=data
                )
            
            if response.ok:
                return response.json().get("data")
            else:
                raise Exception(f"Failed to upload patterns: {response.text}")
        finally:
            os.unlink(papdata_path)
            os.unlink(patterns_path)


def load_test_data():
    """Load papdata and patterns from MULTIMONTH folder."""
    # Load papdata
    papdata_path = MULTIMONTH_DIR / "papdata.json"
    if not papdata_path.exists():
        raise FileNotFoundError(f"papdata.json not found. Run multimonth_test.py first!")
    
    with open(papdata_path) as f:
        papdata = json.load(f)
    
    # Load or generate patterns
    patterns_path = Path(__file__).parent.parent / "MULTIMONTH" / "patterns.json"
    if patterns_path.exists():
        with open(patterns_path) as f:
            patterns = json.load(f)
    else:
        # Generate patterns inline
        patterns = generate_multimonth_patterns(papdata)
    
    return papdata, patterns


def generate_multimonth_patterns(papdata: dict) -> dict:
    """
    Generate multi-month patterns:
    - Month 1 (days 0-13): Everyone at Place A during day
    - Month 2 (days 14-27): Everyone at Place B during day
    """
    patterns = {}
    people_ids = list(papdata["people"].keys())
    
    # Month 1: Days 0-13 - Place A
    for day in range(14):
        # Morning at home
        minute = day * 1440
        patterns[str(minute)] = {
            "homes": {"0": ["0", "1"], "1": ["2", "3", "4"]},
            "places": {}
        }
        
        # Daytime at Place A
        for hour in range(8, 18):
            minute = day * 1440 + hour * 60
            patterns[str(minute)] = {
                "homes": {},
                "places": {"0": people_ids.copy()}
            }
        
        # Evening at home
        minute = day * 1440 + 18 * 60
        patterns[str(minute)] = {
            "homes": {"0": ["0", "1"], "1": ["2", "3", "4"]},
            "places": {}
        }
    
    # Month 2: Days 14-27 - Place B
    for day in range(14, 28):
        minute = day * 1440
        patterns[str(minute)] = {
            "homes": {"0": ["0", "1"], "1": ["2", "3", "4"]},
            "places": {}
        }
        
        for hour in range(8, 18):
            minute = day * 1440 + hour * 60
            patterns[str(minute)] = {
                "homes": {},
                "places": {"1": people_ids.copy()}
            }
        
        minute = day * 1440 + 18 * 60
        patterns[str(minute)] = {
            "homes": {"0": ["0", "1"], "1": ["2", "3", "4"]},
            "places": {}
        }
    
    return patterns


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Create Multi-Month Test CZ in Database")
    parser.add_argument("--clean", action="store_true", help="Delete existing test CZ first")
    parser.add_argument("--check", action="store_true", help="Just check if CZ exists")
    parser.add_argument("--name", default="Multi-Month Test", help="CZ name")
    
    args = parser.parse_args()
    
    # Initialize API client
    api = DelineoAPI()
    
    # Check server
    if not api.check_server():
        print("❌ Fullstack server not running!")
        print("   Start with: cd Fullstack/server && pnpm dev")
        sys.exit(1)
    
    print(f"✓ Server is running at {API_BASE}")
    
    # Authenticate
    user = api.register_or_login(
        email=TEST_USER["email"],
        password=TEST_USER["password"],
        name=TEST_USER["name"],
        organization=TEST_USER["organization"]
    )
    
    # Check existing CZs
    existing_czs = api.get_convenience_zones(user_id=api.user_id)
    test_cz = next((cz for cz in existing_czs if cz["name"] == args.name), None)
    
    if args.check:
        if test_cz:
            print(f"✓ CZ exists: ID={test_cz['id']}, ready={test_cz.get('ready', False)}")
        else:
            print(f"✗ CZ '{args.name}' not found")
        return
    
    if args.clean and test_cz:
        print(f"Deleting existing CZ: {test_cz['id']}")
        api.delete_convenience_zone(test_cz["id"])
        test_cz = None
    
    # Load test data
    print("\nLoading test data...")
    papdata, patterns = load_test_data()
    print(f"  - People: {len(papdata['people'])}")
    print(f"  - Homes: {len(papdata['homes'])}")
    print(f"  - Places: {len(papdata['places'])}")
    print(f"  - Pattern timestamps: {len(patterns)}")
    
    # Create CZ if needed
    if not test_cz:
        print(f"\nCreating ConvenienceZone: {args.name}")
        test_cz = api.create_convenience_zone(
            name=args.name,
            description="MULTIMONTH",  # Used for location lookup in simulation
            cbg_list=["000000000001"],
            latitude=39.0,
            longitude=-76.5,
            start_date="2019-01-01T00:00:00Z",
            length=672,  # 28 days in hours
            size=len(papdata["people"])
        )
        print(f"✓ Created CZ: ID={test_cz['id']}")
    else:
        print(f"\n✓ Using existing CZ: ID={test_cz['id']}")
    
    # Upload patterns (creates MovementPattern record for /patterns/:id endpoint)
    print("\nUploading papdata and patterns to database...")
    
    try:
        result = api.upload_patterns(
            czone_id=test_cz["id"],
            papdata=papdata,
            patterns=patterns
        )
        print(f"✓ Uploaded patterns: PaPData ID={result['papdata']['id']}")
        print(f"✓ Uploaded patterns: MovementPattern ID={result['patterns']['id']}")
    except Exception as e:
        # Might already exist
        print(f"Note: {e}")
        print("  (Patterns may already exist for this CZ)")
    
    # Final status
    print("\n" + "="*60)
    print("SUCCESS! Multi-Month Test CZ created in database")
    print("="*60)
    print(f"\nCZ ID: {test_cz['id']}")
    print(f"Name: {args.name}")
    print(f"Description: MULTIMONTH")
    print(f"\nYou can now:")
    print(f"1. Open the UI at http://localhost:5173")
    print(f"2. Log in with: {TEST_USER['email']} / {TEST_USER['password']}")
    print(f"3. Select '{args.name}' from the CZ dropdown")
    print(f"4. Run a simulation!")
    print(f"\nOr test via API:")
    print(f'curl -X POST http://localhost:1870/simulation/legacy \\')
    print(f'  -H "Content-Type: application/json" \\')
    print(f'  -d \'{{"czone_id": {test_cz["id"]}, "length": 40320}}\'')


if __name__ == "__main__":
    main()
