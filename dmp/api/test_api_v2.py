#!/usr/bin/env python3
"""
Simple test for Disease Modeling Platform API v2.0
Tests all endpoints and both default and vaccination models for measles.
"""

import requests
import json

# API Configuration
BASE_URL = "http://localhost:8000"

def test_root_endpoint():
    """Test the root endpoint"""
    print("🎯 Root Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/")
        response.raise_for_status()
        data = response.json()
        print(f"✅ {data.get('message')} v{data.get('version')}")
        return data
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed: {e}")
        return None

def test_diseases_endpoint():
    """Test the diseases endpoint"""
    print("\n🎯 Diseases Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/diseases")
        response.raise_for_status()
        data = response.json()
        diseases = data.get('diseases', [])
        print(f"✅ Found {len(diseases)} diseases: {diseases}")
        return diseases
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed: {e}")
        return []

def test_variants_endpoint():
    """Test the variants endpoint"""
    print("\n🎯 Variants Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/diseases/COVID-19/variants")
        response.raise_for_status()
        data = response.json()
        variants = data.get('variants', [])
        print(f"✅ COVID-19 variants: {variants}")
        return variants
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed: {e}")
        return []

def test_state_machines_endpoint():
    """Test the state machines endpoint"""
    print("\n🎯 State Machines Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/state-machines")
        response.raise_for_status()
        data = response.json()
        machines = data.get('state_machines', [])
        print(f"✅ Found {len(machines)} state machines")
        return machines
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed: {e}")
        return []

def test_specific_state_machine():
    """Test getting a specific state machine"""
    print("\n🎯 Specific State Machine")
    try:
        response = requests.get(f"{BASE_URL}/state-machines")
        response.raise_for_status()
        data = response.json()
        machines = data.get('state_machines', [])
        
        if machines:
            machine_id = machines[0]['id']
            response = requests.get(f"{BASE_URL}/state-machines/{machine_id}")
            response.raise_for_status()
            data = response.json()
            machine = data.get('state_machine', {})
            print(f"✅ {machine.get('name')} ({machine.get('disease_name')})")
            return machine
        else:
            print("❌ No machines available")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed: {e}")
        return None

def test_measles_default_model():
    """Test measles default model simulation"""
    print("\n🎯 Measles Default Model")
    
    simulation_request = {
        "disease_name": "Measles",
        "demographics": {
            "Age": "5",
            "Sex": "M"
        },
        "model_path": "default.general",
        "initial_state": "Exposed"
    }
    
    print(f"📥 Input: {simulation_request}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/simulate",
            json=simulation_request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        data = response.json()
        print("📤 Output:")
        print(f"   Timeline: {data.get('timeline')}")
        print(f"   Duration: {data.get('total_duration')} hours")
        print(f"   Final State: {data.get('final_state')}")
        print(f"   Machine: {data.get('state_machine', {}).get('name')}")
        print(f"   Model Path: {data.get('model_path')}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Error: {e.response.text}")
        return None

def test_covid_delta_variant():
    """Test COVID-19 Delta variant simulation"""
    print("\n🎯 COVID-19 Delta Variant")
    
    simulation_request = {
        "disease_name": "COVID-19",
        "demographics": {
            "Age": "66",
            "Sex": "Male",
            "Vaccination Status": "Unvaccinated"
        },
        "model_path": "variant.Delta.general",
        "initial_state": "Infected"
    }
    
    print(f"📥 Input: {simulation_request}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/simulate",
            json=simulation_request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        data = response.json()
        print("📤 Output:")
        print(f"   Timeline: {data.get('timeline')}")
        print(f"   Duration: {data.get('total_duration')} hours")
        print(f"   Final State: {data.get('final_state')}")
        print(f"   Machine: {data.get('state_machine', {}).get('name')}")
        print(f"   Model Path: {data.get('model_path')}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Error: {e.response.text}")
        return None

def test_measles_vaccination_model():
    """Test measles vaccination model simulation"""
    print("\n🎯 Measles Vaccination Model")
    
    simulation_request = {
        "disease_name": "Measles",
        "demographics": {
            "Age": "3",
            "Sex": "M",
            "Vaccination Status": "Unvaccinated"
        },
        "model_path": "vaccination.Unvaccinated.general",
        "initial_state": "Exposed"
    }
    
    print(f"📥 Input: {simulation_request}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/simulate",
            json=simulation_request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        data = response.json()
        print("📤 Output:")
        print(f"   Timeline: {data.get('timeline')}")
        print(f"   Duration: {data.get('total_duration')} hours")
        print(f"   Final State: {data.get('final_state')}")
        print(f"   Machine: {data.get('state_machine', {}).get('name')}")
        print(f"   Model Path: {data.get('model_path')}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Error: {e.response.text}")
        return None

def main():
    """Main function"""
    print("Disease Modeling Platform API v2.0 - Test Suite")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code != 200:
            print("❌ Server not running. Start with: uvicorn api.dmp_api_v2:app --reload --port 8000")
            return
    except Exception as e:
        print(f"❌ Server connection failed: {e}")
        return
    
    # Run all tests
    test_root_endpoint()
    test_diseases_endpoint()
    test_variants_endpoint()
    test_state_machines_endpoint()
    test_specific_state_machine()
    
    print("\n" + "=" * 50)
    print("🎯 SIMULATION TESTS")
    print("=" * 50)
    
    test_measles_default_model()
    test_measles_vaccination_model()
    test_covid_delta_variant()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    main() 