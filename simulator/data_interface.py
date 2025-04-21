import requests 

BASE_URL = "https://db.delineo.me/"

def load_movement_pap_data(cz_id: int): 
    print('loading data...')
    
    response = requests.get(f"https://db.delineo.me/patterns/{cz_id}")
    
    if not response.ok:
        print('error getting patterns')
        return
    
    data = response.json().get("data", {})
    
    print(data)

    return {
        "data": {
            "patterns": data.get("patterns", {}),
            "papdata": data.get("papdata", {})
        }
    }


def load_people(): 
    """
    Loads people and their information from central database. 
        
    Returns: 
        people(dict): Dictionary containing people information.
        """
    try:
        response = requests.get(f"{BASE_URL}people")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print("Error fetching people data:", e)
        return []


def load_places(): 
    try:
        response = requests.get(f"{BASE_URL}places")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print("Error fetching places data:", e)
        return []
    
