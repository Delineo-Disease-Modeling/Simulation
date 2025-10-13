from .pap import InfectionState, InfectionTimeline, VaccinationState
from .infection_models.v5_wells_riley import CAT
from .config import DMP_API, INFECTION_MODEL
import pandas as pd
import requests

class InfectionManager:
    def __init__(self, infected_ids: list[str]):
        self.multidisease = INFECTION_MODEL["allow_multidisease"]
        self.infected = [ *infected_ids ]
        
    def run_model(self, simulator, curtime, variantInfected, newlyInfected, file=None):
        if file is not None:
            file.write(f'====== TIMESTEP {curtime} ======\n')
            for variant in variantInfected.keys():
                infected_ids = [i.id for i in self.infected if variant in i.states and i.states[variant] != InfectionState.SUSCEPTIBLE]
                file.write(f'{variant}: {infected_ids}\n')
                file.write(f"{variant} count: {len(infected_ids)}\n")
        
        # Update variantInfected
        for id in self.infected:
            for disease in variantInfected.keys():
                state = simulator.people[id].states.get(disease, InfectionState.SUSCEPTIBLE)
                if state != InfectionState.SUSCEPTIBLE:
                    variantInfected[disease][id] = int(state.value)
                        
        infected = [ simulator.people[id] for id in self.infected ]
        
        for i in infected:
            if i.invisible:
                continue
                
            for p in i.location.population:
                if i.id == p.id:
                    continue
                
                for disease, state in i.states.items():
                    if InfectionState.INFECTIOUS not in state:
                        continue
                                        
                    # Check if the susceptible person is already infected with this disease
                    if p.states.get(disease, InfectionState.SUSCEPTIBLE) != InfectionState.SUSCEPTIBLE:
                        continue
                                        
                    # Get mask status for both people
                    # infector_masked = getattr(i, 'masked', False)
                    infector_masked = i.is_masked()
                    susceptible_masked = p.is_masked()
                    
                    # Use base transmission probability without pre-applying mask effects
                    # Let CAT handle mask effects internally
                    base_transmission_prob = 7e3
                    
                    # Call CAT with all required parameters
                    if CAT(p, True, 1, base_transmission_prob, infector_masked, susceptible_masked):
                        print(f"New infection detected, ({i.id} -> {p.id}) infector_masked: {infector_masked}, susceptible_masked: {susceptible_masked}")
                        
                        if p.id not in self.infected:
                            self.infected.append(p.id)
                        elif self.multidisease == False:
                            continue
                        
                        timeline = self.create_timeline(p, disease, curtime)
                        simulator.people[p.id].timeline = timeline
                        
                        if file is not None:
                            file.write(f'{i.id} infected {p.id} @ location {p.location.id} w/ {disease}\n')

                        # Track newly infected individuals
                        if disease not in newlyInfected:
                            newlyInfected[disease] = {}
                        if str(i.id) not in newlyInfected[disease]:
                            newlyInfected[disease][str(i.id)] = []

                        newlyInfected[disease][str(i.id)].append(str(p.id))
    
    def calculate_mask_transmission_modifier(self, infector, susceptible):
        from .simulate import Maskingeffects 
        return Maskingeffects.calculate_mask_transmission_modifier(infector, susceptible)
    
    def create_timeline(self, person, disease, curtime):
        """Create a disease timeline for a newly infected person using the DMP API"""
        
        # Set up API connection
        BASE_URL = DMP_API["base_url"]
        
        # Prepare the demographic payload for the API
        simulation_payload = {
            "disease_name": "COVID-19",
            "model_path": None,
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
            val = { disease: {} }
            
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
            return val

        except requests.exceptions.RequestException as e:
            print(f"Error communicating with DMP API: {e}")
            # Fallback to a simple timeline if API fails
            fallback_timeline = INFECTION_MODEL["fallback_timeline"]
            return {
                disease: {
                    InfectionState.INFECTED: InfectionTimeline(curtime, curtime + fallback_timeline["infected_duration"]),
                    InfectionState.INFECTIOUS: InfectionTimeline(curtime + fallback_timeline["infectious_delay"], 
                                                               curtime + fallback_timeline["infected_duration"]),
                    InfectionState.RECOVERED: InfectionTimeline(curtime + fallback_timeline["infected_duration"], 
                                                              curtime + fallback_timeline["recovery_duration"])
                }
            }
