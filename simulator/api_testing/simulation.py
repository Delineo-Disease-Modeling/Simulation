'''
This file does the following: 
1. Reads sample demographic data of 100 individuals from demographics.csv 
2. Uses infection_model.py to calculate the probability of infection for each individual 
3. If the probability of infection is above 50%, it sends a POST to dmp API with person's demographics. 
4. DMP API returns the person's status after full disease trajectory has been calculated 
'''
import pandas as pd
import requests 
from infection_model import probability_of_infection 
import random

class Person: 
    def __init__(self, age, vaccination_status, sex, variant): 
        self.age = age
        self.vaccination_status = vaccination_status
        self.sex = sex
        self.variant = variant
        self.invisible = False 

    def getDisease(self):
        return self.variant
    
    def __str__(self): 
        return f"{self.age}, {self.vaccination_status}, {self.sex}, {self.variant}"
    
    def getDemographics(self): 
        return {
            "demographics": {
                        "Age": str(self.age),
                        "Vaccination Status": self.vaccination_status,
                        "Sex": self.sex,
                        "Variant": self.variant
                    }
        }
    
    def setInvisible(self): 
        self.invisible = True 

# Function to read the CSV file using pandas and create Person objects
def read_csv_and_create_objects(csv_file):
    # Read the CSV file into a pandas DataFrame
    df = pd.read_csv(csv_file)
    
    people = []
    
    # Loop through each row in the DataFrame and create a Person object
    for _, row in df.iterrows():
        person = Person(
            age=row['Age'],
            vaccination_status=row['Vaccination Status'],
            sex=row['Sex'],
            variant=row['Variant']
        )
        people.append(person)
    
    return people

def load_infection_paramters(): 
    df = pd.read_csv("/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/infection_model_parameters.csv", header = 0)
    return df.set_index("parameter")["value"].to_dict()

def get_status_at_time(t, timeline):
    current_status = "Unknown"
    for status, time in timeline["timeline"]:
        if t >= time:
            current_status = status
    return current_status

def main():
    people = read_csv_and_create_objects('/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/demographics.csv')

    
    print("Sending POST request to DMP API with person's demographics")
    BASE_URL = "http://localhost:8000"
    init_payload = {
        "matrices_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/combined_matrices_usecase.csv",
        "mapping_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/demographic_mapping_usecase.csv",
        "states_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/custom_states.txt"
        # "matrices_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/api_testing/combined_matrices_usecase.csv",
        # "mapping_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/api_testing/demographic_mapping_usecase.csv",
        # "states_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/api_testing/custom_states.txt"
    }
    init_response = requests.post(f"{BASE_URL}/initialize", json=init_payload)
    init_response.raise_for_status()
    init_data = init_response.json()

    if init_response.status_code == 200:
        print("DMP successfully initialized!")
    else:
        print("Initialization failed:", init_response.text)
        exit()

    for person in people: 
        # if a person is invisible, it means they are not in the simulation anymore 
        if person.invisible: 
            return 
        
        params = load_infection_paramters()

        # calculate probability of infection of each person 
        p_infection = probability_of_infection(person.getDisease(), params["d"], params["t_i"], params["r"], params["m_i"], params["V"], params["fv_list"], params["p_list"], params["t_room"], params["t_close"], params["a_filter"])

        print("Probability of infection: " + str(p_infection))

        if random.random() < p_infection:
            time = random.randint(0, 100)
            # Send a simulation request with demographics
            simulation_payload = person.getDemographics()
        

            simulation_response = requests.post(f"{BASE_URL}/simulate", json=simulation_payload)

            if simulation_response.status_code == 200:
                timeline = simulation_response.json()
                print("✅ Simulation successful! Disease timeline:")
                print(timeline)
                current_status = get_status_at_time(time, timeline)
                print("Status at time " + str(time) + ": " + current_status)
                if "timeline" in timeline and timeline["timeline"]:
                    last_status = timeline["timeline"][-1][0]  # Get the last status in the timeline
                    if (last_status.lower() == "deceased" or last_status.lower() == "ICU" or last_status.lower() == "hospitalized"): 
                        person.setInvisible()
            else:
                print("❌ Simulation failed:", simulation_response.text)
                exit()
        

if __name__ == '__main__':
    main()
