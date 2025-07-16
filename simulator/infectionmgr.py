from .pap import InfectionState, InfectionTimeline, VaccinationState
from .infection_model import CAT
from .config import DMP_API, INFECTION_MODEL
import pandas as pd
from io import StringIO
import requests

class InfectionManager:
    def __init__(self, matrices_dict, timestep=None, people=[]):
        self.matrices_dict = matrices_dict  
        self.timestep = timestep or INFECTION_MODEL["default_timestep"]
        self.multidisease = INFECTION_MODEL["allow_multidisease"]
        self.infected = []
        
        for p in people:
            for v in p.states.values():
                if InfectionState.INFECTED in v:
                    self.infected.append(p)
    
    # def run_model(self, num_timesteps=4, file=None, curtime=0, deltaInfected=[], omicronInfected=[]):
    #     if file != None:
    #         file.write(f'====== TIMESTEP {curtime} ======\n')
    #         file.write(f'delta: {[i.id for i in self.infected if i.states.get("delta") != None]}\n')
    #         file.write(f'omicron: {[i.id for i in self.infected if i.states.get("omicron") != None]}\n')
    #         file.write(f"delta count: {len([i.id for i in self.infected if i.states.get('delta') != None])}\n")
    #         file.write(f"omicron count: {len([i.id for i in self.infected if i.states.get('omicron') != None])}\n")

    #     # keep an array of number of people infected at each time step
    #     for i in self.infected:
    #         if i.states.get('delta') != None and i.states['delta'] != InfectionState.SUSCEPTIBLE:
    #             deltaInfected[i.id] = int(i.states['delta'].value)
    #         elif i.states.get('omicron') != None and i.states['omicron'] != InfectionState.SUSCEPTIBLE:
    #             omicronInfected[i.id] = int(i.states['omicron'].value)
        
    #     for i in self.infected:
    #         i.update_state(curtime)
        
    #     for i in self.infected:
    #         if i.invisible == True:
    #             continue

    #         for p in i.location.population:
    #             if i == p or p.invisible == True:
    #                 continue

    #             new_infections = []

    #             for disease, state in i.states.items():   
    #                 # Ignore those who cannot infect others
    #                 if InfectionState.INFECTIOUS not in state:
    #                     continue
                            
    #                 # Ignore those already infected, hospitalized, or recovered
    #                 if p.states.get(disease) != None and InfectionState.INFECTED in p.states[disease]:
    #                     continue
                    
    #                 # Repeat the probability the number of timesteps we passed over the interval
    #                 # for _ in range(num_timesteps):
    #                 if (disease == "delta" and CAT(p, True, num_timesteps, 7e4)) or (disease == "omicron" and CAT(p, True, num_timesteps, 7e4)):
    #                     new_infections.append(disease)
    #                     break
                
    #             for disease in new_infections:
    #                 # If a person is infected with more than one disease at the same time
    #                 # and the model does not support being infected with multiple diseases,
    #                 # this loop is used to remedy that case
                    
    #                 self.infected.append(p) # add to list of infected regardless
                    
    #                 # Set infection state if they were only infected once, or if multidisease is True
    #                 if len(new_infections) == 1 or self.multidisease == True:
    #                     p.states[disease] = InfectionState.INFECTED
    #                     self.create_timeline(p, disease, curtime)
                        
    #                     if file != None:
    #                         file.write(f'{i.id} infected {p.id} @ location {p.location.id} w/ {disease}\n')
    #                     continue
                    
    #                 # TODO: Handle case where a person is infected by multiple diseases at once
    #                 #p.state = InfectionState.INFECTED
    #                 print(f'{i.id} infected {p.id} @ location {p.location.id}')
            
    #         # print(len(all_p))

    def run_model(self, num_timesteps=4, file=None, curtime=0, variantInfected={}, newlyInfected={}):
        if file is not None:
            file.write(f'====== TIMESTEP {curtime} ======\n')
            for variant in variantInfected.keys():
                infected_ids = [i.id for i in self.infected if variant in i.states and i.states[variant] != InfectionState.SUSCEPTIBLE]
                file.write(f'{variant}: {infected_ids}\n')
                file.write(f"{variant} count: {len(infected_ids)}\n")

        # Update the infection counts for each variant
        for i in self.infected:
            for disease in variantInfected.keys():
                if disease in i.states and i.states[disease] != InfectionState.SUSCEPTIBLE:
                    variantInfected[disease][i.id] = int(i.states[disease].value)

        # Update the state of each person based on the current time
        for i in self.infected:
            i.update_state(curtime, self.matrices_dict.keys())

        # Evaluate the possibility of new infections
        for i in self.infected:
            if i.invisible:
                continue

            for p in i.location.population:
                if i == p or p.invisible:
                    continue

                new_infections = []

                for disease, state in i.states.items():
                    if InfectionState.INFECTIOUS not in state:
                        continue
                    if p.states.get(disease) is not None and InfectionState.INFECTED in p.states[disease]:
                        continue

                    mask_modifier = self.calculate_mask_transmission_modifier(i, p)
                    base_transmission_prob = 7e3 * (1 - mask_modifier)

                    
                    # Assuming CAT function can h andle the matrix without needing to specify a disease
                    if CAT(p, True, num_timesteps, base_transmission_prob):
                        new_infections.append(disease)
                        
                        if newlyInfected.get(disease) == None:
                            newlyInfected[disease] = {}
                        newlyInfected[disease][str(i.id)] = [ *newlyInfected.get(str(i.id), []), str(p.id) ]
                        
                        break

                for disease in new_infections:
                    self.infected.append(p)  # Add to list of infected regardless
                    if len(new_infections) == 1 or self.multidisease:
                        self.create_timeline(p, disease, curtime)
                        
                        if file is not None:
                            file.write(f'{i.id} infected {p.id} @ location {p.location.id} w/ {disease}\n')

    def calculate_mask_transmission_modifier(self, infector, susceptible):
        from .simulate import Maskingeffects 
        return Maskingeffects.calculate_mask_transmission_modifier(infector, susceptible)
    

    def create_timeline(self, person, disease, curtime):
        """Create a disease timeline for a newly infected person using the DMP API"""
        
        # Set up API connection
        BASE_URL = DMP_API["base_url"]
        
        # Prepare the demographic payload for the API
        simulation_payload = {
            "demographics": {
                "Age": str(person.age),
                "Vaccination Status": "Vaccinated" if person.interventions["vaccine"] != VaccinationState.NONE else "Unvaccinated",
                "Sex": "F" if person.sex == 1 else "M",
                "Variant": disease 
            }
        }
        
        # Send request to DMP API
        try:
            simulation_response = requests.post(f"{BASE_URL}/simulate", json=simulation_payload)
            simulation_response.raise_for_status()
            
            # Process the timeline returned from the API
            timeline_data = simulation_response.json()
            
            # Map DMP states to our infection states using config
            str_to_state = {k: getattr(InfectionState, v) for k, v in DMP_API["state_mapping"].items()}
            
            # Initialize the timeline for this disease
            val = {}
            val[disease] = {}
            
            # Get the maximum time in the timeline for end time calculation
            max_time = max([time for _, time in timeline_data["timeline"]])
            
            # Process each state transition in the timeline
            for status, time in timeline_data["timeline"]:
                if status in str_to_state:
                    state = str_to_state[status]
                    # Convert time from API units to simulation units
                    adjusted_time = time / DMP_API["time_conversion_factor"]
                    
                    if state in val[disease]:
                        # Update existing timeline entry
                        current_start = val[disease][state].start
                        val[disease][state] = InfectionTimeline(
                            min(current_start, curtime + adjusted_time), 
                            curtime + max_time/DMP_API["time_conversion_factor"]
                        )
                    else:
                        # Create new timeline entry
                        val[disease][state] = InfectionTimeline(
                            curtime + adjusted_time, 
                            curtime + max_time/DMP_API["time_conversion_factor"]
                        )
            
            # Set the person's timeline
            person.timeline = val
            
            # Set the person's initial state for this disease
            person.states[disease] = InfectionState.INFECTED
            
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with DMP API: {e}")
            # Fallback to a simple timeline if API fails
            fallback_timeline = INFECTION_MODEL["fallback_timeline"]
            person.states[disease] = InfectionState.INFECTED
            person.timeline = {
                disease: {
                    InfectionState.INFECTED: InfectionTimeline(curtime, curtime + fallback_timeline["infected_duration"]),
                    InfectionState.INFECTIOUS: InfectionTimeline(curtime + fallback_timeline["infectious_delay"], 
                                                               curtime + fallback_timeline["infected_duration"]),
                    InfectionState.RECOVERED: InfectionTimeline(curtime + fallback_timeline["infected_duration"], 
                                                              curtime + fallback_timeline["recovery_duration"])
                }
            }