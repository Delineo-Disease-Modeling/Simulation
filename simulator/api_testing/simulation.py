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
from collections import Counter

class Person: 
    def __init__(self, age, vaccination_status, sex, variant): 
        self.age = age
        self.vaccination_status = vaccination_status
        self.sex = sex
        self.variant = variant
        self.invisible = False 
        self.final_state = None

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
    
    def setInvisible(self, state): 
        self.invisible = True
        self.final_state = state

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
    #df = pd.read_csv("/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/api_testing/infection_model_parameters.csv", header = 0)
    return df.set_index("parameter")["value"].to_dict()

def get_status_at_time(t, timeline):
    current_status = "Unknown"
    for status, time in timeline["timeline"]:
        if t >= time:
            current_status = status
    return current_status

def main():
    people = read_csv_and_create_objects('/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/demographics.csv')
    # people = read_csv_and_create_objects('/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/api_testing/demographics.csv')
    total_people = len(people)
    infected_count = 0
    invisible_states = Counter()
    current_states = Counter()
    infectious = []
    can_get_infected = [] # list of people who are not infectious or invisible and can get infected 
    recoveredCanGetInfected = True
    
    print(f"Total population: {total_people} people")
    
    print("Sending POST request to DMP API with person's demographics")
    BASE_URL = "http://localhost:8000"
    init_payload = {
        "matrices_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/combined_matrices_usecase.csv",
        "mapping_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/demographic_mapping_usecase.csv",
        "states_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing/custom_states.txt"
        #"matrices_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/api_testing/combined_matrices_usecase.csv",
        #"mapping_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/api_testing/demographic_mapping_usecase.csv",
        #"states_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/api_testing/custom_states.txt"
    }
    init_response = requests.post(f"{BASE_URL}/initialize", json=init_payload)
    init_response.raise_for_status()
    init_data = init_response.json()

    if init_response.status_code == 200:
        print("DMP successfully initialized!")
    else:
        print("Initialization failed:", init_response.text)
        exit()

    for i, person in enumerate(people): 
        # if a person is invisible, it means they are not in the simulation anymore 
        if person.invisible: 
            continue
        
        params = load_infection_paramters()

        # calculate probability of infection of each person 
        p_infection = probability_of_infection(person.getDisease(), params["d"], params["t_i"], params["r"], params["m_i"], params["V"], params["fv_list"], params["p_list"], params["t_room"], params["t_close"], params["a_filter"])

        print(f"Person {i+1}: {person} - Probability of infection: {p_infection:.4f}")

        if random.random() < p_infection:
            infected_count += 1
            time = random.randint(100, 300)
            # Send a simulation request with demographics
            simulation_payload = person.getDemographics()
            simulation_response = requests.post(f"{BASE_URL}/simulate", json=simulation_payload)

            if simulation_response.status_code == 200:
                timeline = simulation_response.json()
                print(f"✅ Person {i+1} infected - Disease timeline:")
                print(timeline["timeline"])
                
                # Get status at the current time
                current_status = get_status_at_time(time, timeline)
                print(f"Status at time {time}: {current_status}")
                
                # Track this person's current disease state
                current_states[current_status] += 1
                
                # Set person as invisible based on CURRENT state, not final state
                if current_status in ["Deceased", "ICU", "Hospitalized"]:
                    person.setInvisible(current_status)
                    invisible_states[current_status] += 1
                    print(f"⚠️ Person {i+1} marked invisible due to {current_status} at time {time}")

                if current_status == "Infectious_Asymptomatic" or current_status == "Infectious_Symptomatic" or current_status == "Infected": 
                    infectious.append(person)

                if (current_status == "Recovered" and recoveredCanGetInfected) or (person.invisible == False and not(current_status == "Infectious_Asymptomatic" or current_status == "Infectious_Symptomatic" or current_status == "Infected")):
                    can_get_infected.append(person)
            
            else:
                print(f"❌ Person {i+1} simulation failed: {simulation_response.text}")
                exit()
    
    # Calculate statistics
    infection_rate = (infected_count / total_people) * 100
    invisible_count = sum(invisible_states.values())
    invisible_rate = (invisible_count / total_people) * 100
    
    # Print summary statistics
    print("\n" + "="*50)
    print("SIMULATION SUMMARY")
    print("="*50)
    print(f"Total population: {total_people}")
    print(f"Total infected: {infected_count} ({infection_rate:.2f}%)")
    print(f"Total invisible: {invisible_count} ({invisible_rate:.2f}%)")
    
    print("\nCurrent Disease States at Simulation End:")
    for state, count in current_states.items():
        percentage = (count / infected_count) * 100 if infected_count > 0 else 0
        print(f"  - {state}: {count} ({percentage:.2f}%)")
    
    print("\nInvisible People by Reason:")
    for state, count in invisible_states.items():
        percentage = (count / invisible_count) * 100 if invisible_count > 0 else 0
        print(f"  - {state}: {count} ({percentage:.2f}%)")
    
    # Calculate visibility statistics
    visible_count = infected_count - invisible_count
    visible_rate = (visible_count / infected_count) * 100 if infected_count > 0 else 0
    
    print("\nVisibility Summary:")
    print(f"  - Visible: {visible_count} ({visible_rate:.2f}% of infected)")
    print(f"  - Invisible: {invisible_count} ({100-visible_rate:.2f}% of infected)")
    
    print("="*50)

    print("All infectious people at time " + str(time) + ":")
    for person in infectious: 
        print(person)

    print("\n")

    print("People who can get infected at time " + str(time) + ":")
    for person in can_get_infected: 
        print(person)
        

if __name__ == '__main__':
    main()
