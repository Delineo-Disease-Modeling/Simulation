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

class Person: 
    def __init__(self, age, vaccination_status, sex, variant, matrix_set): 
        self.age = age
        self.vaccination_status = vaccination_status
        self.sex = sex
        self.variant = variant
        self.matrix_set = matrix_set

    def getDisease(self):
        return self.variant
    
    def __str__(self): 
        return f"{self.age}, {self.vaccination_status}, {self.sex}, {self.variant}, {self.matrix_set}"
    
    def getDemographics(self): 
        return f"{self.age}, {self.vaccination_status}, {self.sex}, {self.variant}, {self.matrix_set}"

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
            variant=row['Variant'],
            matrix_set=row['Matrix_Set']
        )
        people.append(person)
    
    return people

def main():
    people = read_csv_and_create_objects('/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/demographics.csv')
    for person in people: 
        print(person)
    

    for person in people: 
        # calculate probability of infection of each person 
        R_0 = 900 # upper limit of virions to get infected 
        disease = person.getDisease()
        d = 0.5 # particle degradation rate
        t_i = 60 # duration of exposure 
        r = 1860 # emission rate of person (src: https://pmc.ncbi.nlm.nih.gov/articles/PMC9128309/)
        m_i = 0.5 # mask filteration rate 
        V = 3000 # volume of room in liters 
        fv_list = 0.6 # fraction of viruses in droplet size class i 
        p_list = 0.7 # probability of droplet size class i
        t_room = 10000 # time spent in room 
        t_close = 10000 # time spent within 2 meters of infected person
        a_filter = 4.8; # air changes per hour 
        distance = 0.45 #distance from infected person 

        p_infection = probability_of_infection(disease, d, t_i, r, m_i, V, fv_list, p_list, t_room, t_close, a_filter)

        print("Probability of infection: " + str(p_infection))

        if p_infection > 0.05: 
            print("Sending POST request to DMP API with person's demographics")
            BASE_URL = "http://localhost:8000"
            init_payload = {
                "matrices_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/combined_matrices_usecase.csv",
                "mapping_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/demographic_mapping_usecase.csv",
                "states_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/custom_states.txt"
            }
            init_response = requests.post(f"{BASE_URL}/initialize", json=init_payload)
            init_response.raise_for_status()
            init_data = init_response.json()

            if init_response.status_code == 200:
                print("DMP successfully initialized!")
            else:
                print("Initialization failed:", init_response.text)
                exit()

            # Step 2: Send a simulation request with demographics
            simulation_payload = {
                
            }

            simulation_response = requests.post(f"{BASE_URL}/simulate", json=simulation_payload)

            if simulation_response.status_code == 200:
                timeline = simulation_response.json()
                print("✅ Simulation successful! Disease timeline:")
                print(timeline)
            else:
                print("❌ Simulation failed:", simulation_response.text)
                exit()
        


if __name__ == '__main__':
    main()
