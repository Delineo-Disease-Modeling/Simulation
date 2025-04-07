import requests 

BASE_URL = "https://db.delineo.me/"

def load_movement_pap_data(cz_id = 1): 
    url = "https://db.delineo.me/patterns/{cz_id}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for HTTP errors

        data = response.json()

        return {
            "movement_patterns": data.get("movement_patterns", {}),
            "papdata": data.get("papdata", {})
        }

    except requests.RequestException as e:
        return {"error": str(e)}



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