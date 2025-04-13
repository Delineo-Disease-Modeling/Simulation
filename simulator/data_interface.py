import requests 

BASE_URL = "https://db.delineo.me/"

def load_movement_pap_data(cz_id = 1): 
    url = "https://db.delineo.me/patterns/1"
    
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
        "movement_patterns": {
            "1": {
                "homes": {
                    "1 ": {"id": 1, "population": [43, 63]},
                    "2": {"id": 2, "population": [75, 103]}
                },
                "places": {
                    "1": {"id": 1, "population": [43,63]},
                    "2": {"id": 2, "population": [75, 103]}
                }
            }
        },
        "papdata": {
            {
                "people": {
                    "43": {
                        "sex": 1,
                        "age": 53,
                        "home": "20"
                    },
                    "63": {
                        "sex": 0,
                        "age": 39,
                        "home": "29"
                    },
                    "75": {
                        "sex": 1,
                        "age": 37,
                        "home": "34"
                    },
                    "103": {
                        "sex": 1,
                        "age": 74,
                        "home": "47"
                }
            }, 
            "places": {
        "1": {
            "label": "American Heritage Bank",
            "cbg": -1
        },
        "2": {
            "label": "Andy's Hamburgers",
            "cbg": -1
        },
        "3": {
            "label": "Ascension Health",
            "cbg": -1
        },
        }
    }
    }  