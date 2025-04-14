import requests 

BASE_URL = "https://db.delineo.me/"

def load_movement_pap_data(cz_id=1): 
    url = "https://db.delineo.me/patterns/2"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for HTTP errors

        data = response.json().get("data", {})

        return {
            "data": {
                "patterns": data.get("patterns", {}),
                "papdata": data.get("papdata", {})
            }
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
    
