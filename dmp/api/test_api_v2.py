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
    print("🎯 Testing Root Endpoint")
    print("=" * 40)
    
    try:
        response = requests.get(f"{BASE_URL}/")
        response.raise_for_status()
        
        data = response.json()
        print("✅ Root endpoint successful!")
        print(f"   Message: {data.get('message')}")
        print(f"   Version: {data.get('version')}")
        print(f"   Available endpoints: {len(data.get('endpoints', {}))}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Root endpoint failed: {e}")
        return None

def test_diseases_endpoint():
    """Test the diseases endpoint"""
    print("\n🎯 Testing Diseases Endpoint")
    print("=" * 40)
    
    try:
        response = requests.get(f"{BASE_URL}/diseases")
        response.raise_for_status()
        
        data = response.json()
        diseases = data.get('diseases', [])
        
        print("✅ Diseases endpoint successful!")
        print(f"   Found {len(diseases)} diseases: {diseases}")
        
        return diseases
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Diseases endpoint failed: {e}")
        return []

def test_variants_endpoint():
    """Test the variants endpoint"""
    print("\n🎯 Testing Variants Endpoint")
    print("=" * 40)
    
    try:
        response = requests.get(f"{BASE_URL}/diseases/Measles/variants")
        response.raise_for_status()
        
        data = response.json()
        variants = data.get('variants', [])
        
        print("✅ Variants endpoint successful!")
        print(f"   Disease: {data.get('disease')}")
        print(f"   Found {len(variants)} variants: {variants}")
        
        return variants
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Variants endpoint failed: {e}")
        return []

def test_state_machines_endpoint():
    """Test the state machines endpoint"""
    print("\n🎯 Testing State Machines Endpoint")
    print("=" * 40)
    
    try:
        response = requests.get(f"{BASE_URL}/state-machines")
        response.raise_for_status()
        
        data = response.json()
        machines = data.get('state_machines', [])
        
        print("✅ State machines endpoint successful!")
        print(f"   Found {len(machines)} state machines")
        
        # Show first few machines
        for i, machine in enumerate(machines):
            print(f"   {i+1}. {machine['name']} ({machine['disease_name']})")
        return machines
        
    except requests.exceptions.RequestException as e:
        print(f"❌ State machines endpoint failed: {e}")
        return []

def test_specific_state_machine():
    """Test getting a specific state machine"""
    print("\n🎯 Testing Specific State Machine")
    print("=" * 40)
    
    # First get list of machines
    try:
        response = requests.get(f"{BASE_URL}/state-machines")
        response.raise_for_status()
        data = response.json()
        machines = data.get('state_machines', [])
        
        if machines:
            machine_id = machines[0]['id']
            
            # Get specific machine
            response = requests.get(f"{BASE_URL}/state-machines/{machine_id}")
            response.raise_for_status()
            
            data = response.json()
            machine = data.get('state_machine', {})
            
            print("✅ Specific state machine endpoint successful!")
            print(f"   Name: {machine.get('name')}")
            print(f"   Disease: {machine.get('disease_name')}")
            print(f"   States: {len(machine.get('states', []))}")
            print(f"   Edges: {len(machine.get('edges', []))}")
            
            return machine
        else:
            print("❌ No machines available to test")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Specific state machine endpoint failed: {e}")
        return None

def test_measles_default_model():
    """Test measles default model simulation"""
    print("\n🎯 Testing Measles Default Model")
    print("=" * 40)
    
    simulation_request = {
        "disease_name": "Measles",
        "demographics": {
            "Age": "5",
            "Sex": "M"
        },
        "model_category": "default",
        "initial_state": "Exposed"
    }
    
    print(f"📋 Request:")
    print(f"   Disease: {simulation_request['disease_name']}")
    print(f"   Demographics: {simulation_request['demographics']}")
    print(f"   Model Category: {simulation_request['model_category']}")
    print(f"   Initial State: {simulation_request['initial_state']}")
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/simulate",
            json=simulation_request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        data = response.json()
        print("✅ Simulation successful!")
        print()
        
        # Show the timeline
        timeline = data.get('timeline', [])
        print("📊 DISEASE PROGRESSION TIMELINE:")
        print("-" * 40)
        
        for i, (state, time) in enumerate(timeline):
            print(f"{i+1:2d}. {state:25s} | {time:6.1f} hours")
        
        print("-" * 40)
        print(f"Total duration: {timeline[-1][1]:.1f} hours ({timeline[-1][1]/24:.1f} days)")
        print(f"Final state: {timeline[-1][0]}")
        
        # Show state machine info
        state_machine = data.get('state_machine', {})
        print()
        print("🔧 State Machine Used:")
        print(f"   Name: {state_machine.get('name', 'N/A')}")
        print(f"   ID: {state_machine.get('id', 'N/A')}")
        print(f"   Demographics: {state_machine.get('demographics', {})}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Simulation failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Error details: {error_data}")
            except:
                print(f"   Error text: {e.response.text}")
        return None

def test_covid_delta_variant():
    """Test COVID-19 Delta variant simulation"""
    print("\n🎯 Testing COVID-19 Delta Variant")
    print("=" * 40)
    
    # First, let's see what COVID machines are available
    print("🔍 Available COVID-19 State Machines:")
    try:
        response = requests.get(f"{BASE_URL}/state-machines?disease_name=COVID-19")
        if response.status_code == 200:
            data = response.json()
            machines = data.get('state_machines', [])
            for machine in machines:
                print(f"   - {machine['name']}")
                print(f"     Demographics: {machine['demographics']}")
                print(f"     Model Category: {machine['model_category']}")
                print()
    except Exception as e:
        print(f"   Error getting machines: {e}")
    
    simulation_request = {
        "disease_name": "COVID-19",
        "demographics": {
            "Age": "66",
            "Sex": "Male",
            "Vaccination Status": "Unvaccinated"
        },
        "model_category": "variant",
        "variant_name": "Delta",
        "initial_state": "Infected"
    }
    
    print(f"📋 Request:")
    print(f"   Disease: {simulation_request['disease_name']}")
    print(f"   Demographics: {simulation_request['demographics']}")
    print(f"   Model Category: {simulation_request['model_category']}")
    if 'variant_name' in simulation_request:
        print(f"   Variant: {simulation_request['variant_name']}")
    print(f"   Initial State: {simulation_request['initial_state']}")
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/simulate",
            json=simulation_request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        data = response.json()
        print("✅ Simulation successful!")
        print()
        
        # Show the timeline
        timeline = data.get('timeline', [])
        print("📊 DISEASE PROGRESSION TIMELINE:")
        print("-" * 40)
        
        for i, (state, time) in enumerate(timeline):
            print(f"{i+1:2d}. {state:25s} | {time:6.1f} hours")
        
        print("-" * 40)
        print(f"Total duration: {timeline[-1][1]:.1f} hours ({timeline[-1][1]/24:.1f} days)")
        print(f"Final state: {timeline[-1][0]}")
        
        # Show state machine info
        state_machine = data.get('state_machine', {})
        print()
        print("🔧 State Machine Used:")
        print(f"   Name: {state_machine.get('name', 'N/A')}")
        print(f"   ID: {state_machine.get('id', 'N/A')}")
        print(f"   Demographics: {state_machine.get('demographics', {})}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Simulation failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Error details: {error_data}")
            except:
                print(f"   Error text: {e.response.text}")
        return None

def test_measles_vaccination_model():
    """Test measles vaccination model simulation"""
    print("\n🎯 Testing Measles Vaccination Model")
    print("=" * 40)
    
    # First, let's see what machines are available
    print("🔍 Available State Machines:")
    try:
        response = requests.get(f"{BASE_URL}/state-machines?disease_name=Measles&model_category=vaccination")
        if response.status_code == 200:
            data = response.json()
            machines = data.get('state_machines', [])
            for machine in machines:
                print(f"   - {machine['name']}")
                print(f"     Demographics: {machine['demographics']}")
                print(f"     Model Category: {machine['model_category']}")
                print()
    except Exception as e:
        print(f"   Error getting machines: {e}")
    
    simulation_request = {
        "disease_name": "Measles",
        "demographics": {
            "Age": "3",
            # "Sex": "M",
            "Vaccination Status": "Unvaccinated"
        },
        "model_category": "vaccination",
        "initial_state": "Exposed"
    }
    
    print(f"📋 Request:")
    print(f"   Disease: {simulation_request['disease_name']}")
    print(f"   Demographics: {simulation_request['demographics']}")
    print(f"   Model Category: {simulation_request['model_category']}")
    print(f"   Initial State: {simulation_request['initial_state']}")
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/simulate",
            json=simulation_request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        data = response.json()
        print("✅ Simulation successful!")
        print()
        
        # Show the timeline
        timeline = data.get('timeline', [])
        print("📊 DISEASE PROGRESSION TIMELINE:")
        print("-" * 40)
        
        for i, (state, time) in enumerate(timeline):
            print(f"{i+1:2d}. {state:25s} | {time:6.1f} hours")
        
        print("-" * 40)
        print(f"Total duration: {timeline[-1][1]:.1f} hours ({timeline[-1][1]/24:.1f} days)")
        print(f"Final state: {timeline[-1][0]}")
        
        # Show state machine info
        state_machine = data.get('state_machine', {})
        print()
        print("🔧 State Machine Used:")
        print(f"   Name: {state_machine.get('name', 'N/A')}")
        print(f"   ID: {state_machine.get('id', 'N/A')}")
        print(f"   Demographics: {state_machine.get('demographics', {})}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Simulation failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Error details: {error_data}")
            except:
                print(f"   Error text: {e.response.text}")
        return None

def main():
    """Main function"""
    print("Disease Modeling Platform API v2.0 - Comprehensive Test Suite")
    print("=" * 70)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code != 200:
            print("❌ Cannot connect to API server. Make sure the server is running:")
            print("   uvicorn dmp_api_v2:app --reload --host 0.0.0.0 --port 8000")
            return
    except Exception as e:
        print(f"❌ Server connection failed: {e}")
        print("Make sure the API server is running on http://localhost:8000")
        return
    
    # Run all endpoint tests
    print("\n" + "=" * 70)
    print("🔍 TESTING ALL API ENDPOINTS")
    print("=" * 70)
    
    # Test basic endpoints
    test_root_endpoint()
    test_diseases_endpoint()
    test_variants_endpoint()
    test_state_machines_endpoint()
    test_specific_state_machine()
    
    # Test simulation endpoints
    print("\n" + "=" * 70)
    print("🎯 TESTING SIMULATION ENDPOINTS")
    print("=" * 70)
    
    result1 = test_measles_default_model()
    result2 = test_measles_vaccination_model()
    result3 = test_covid_delta_variant()
    
    if result1 and result2 and result3:
        print("\n" + "=" * 70)
        print("✅ All tests completed successfully!")
        
        # Compare results
        timeline1 = result1.get('timeline', [])
        timeline2 = result2.get('timeline', [])
        timeline3 = result3.get('timeline', [])
        
        print("\n📊 COMPARISON:")
        print(f"Measles Default: {timeline1[-1][1]:.1f} hours ({timeline1[-1][1]/24:.1f} days) → {timeline1[-1][0]}")
        print(f"Measles Vaccination: {timeline2[-1][1]:.1f} hours ({timeline2[-1][1]/24:.1f} days) → {timeline2[-1][0]}")
        print(f"COVID-19 Delta: {timeline3[-1][1]:.1f} hours ({timeline3[-1][1]/24:.1f} days) → {timeline3[-1][0]}")

if __name__ == "__main__":
    main() 