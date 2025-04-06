import requests 

BASE_URL = "https://api.delineo.me"  

def load_people(): 
    """
    Loads people and their information from central database. 
        
    Returns: 
        people(dict): Dictionary containing people information.
        """
    try:
        response = requests.get(f"{BASE_URL}/people")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print("Error fetching people data:", e)
        return []


def load_places(): 
    try:
        response = requests.get(f"{BASE_URL}/places")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print("Error fetching places data:", e)
        return []
    
def load_sample_data(): 
    return {
        "people": {
            "0": {
                "sex": "M", 
                "age": 52, 
                "home": 0
                },
            "1": {
                "sex": "F", 
                "age": 30,
                 "home": 1
                 }
        }, 
        "places": {
            "0": {
                "label": "school",
                "cbg": "1", 
                },
            "1": {
                "cbg": "24003707003", 
                "label": "work", 
                "capacity": 25
                }
        }
    }