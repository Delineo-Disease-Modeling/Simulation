import requests
import json
from pathlib import Path

def test_dmp_api():
    # API base URL
    BASE_URL = "http://localhost:8000"
    
    # Get absolute paths to data files
    data_dir = Path(__file__).parent.parent / "data"
    matrices_path = str(data_dir / "combined_matrices.csv")
    mapping_path = str(data_dir / "demographic_mapping.csv")
    states_path = str(data_dir / "custom_states.txt")
    
    print("\n1. Testing DMP Initialization...")
    try:
        init_response = requests.post(
            f"{BASE_URL}/initialize",
            json={
                "matrices_path": matrices_path,
                "mapping_path": mapping_path,
                "states_path": states_path
            }
        )
        init_response.raise_for_status()
        init_data = init_response.json()
        
        print("✓ Initialization successful")
        print("\nAvailable states:", init_data["states"])
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Initialization failed: {str(e)}")
        return
    
    print("\n2. Testing Simulation...")
    try:
        # Test cases with specific ages that should match to ranges
        test_cases = [
            {
                "demographics": {
                    "Age": "15",
                    "Vaccination Status": "Vaccinated",
                    "Sex": "F",
                    "Variant": "Omicron"
                }
            },
            {
                "demographics": {
                    "Age": "70",
                    "Vaccination Status": "Unvaccinated",
                    "Sex": "M",
                    "Variant": "Delta"
                }
            },
            {
                "demographics": {
                    "Age": "70",
                    "Vaccination Status": "Unvaccinated",
                    "Sex": "M",
                    "Variant": "Omicron"
                }
            }
            # },
            # {
            #     "demographics": {
            #         "Age": "65",
            #         "Vaccination Status": "Vaccinated",
            #         "Sex": "M",
            #         "Variant": "Delta"
            #     }
            # }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\nRunning simulation {i} with demographics:", test_case["demographics"])
            
            sim_response = requests.post(
                f"{BASE_URL}/simulate",
                json=test_case
            )
            sim_response.raise_for_status()
            sim_data = sim_response.json()
            
            print(f"✓ Simulation {i} successful")
            print(f"Used matrix set: {sim_data['matrix_set']}")
            print("\nDisease progression timeline:")
            for state, time in sim_data["timeline"]:
                print(f"{time:>6.1f} hours: {state}")
                
    except requests.exceptions.RequestException as e:
        print(f"✗ Simulation failed: {str(e)}")
        return

if __name__ == "__main__":
    print("Testing DMP API...")
    print("Make sure the API server is running (uvicorn api.dmp_api:app --reload)")
    test_dmp_api() 