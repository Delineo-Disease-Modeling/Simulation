from .pap import InfectionState, InfectionTimeline, VaccinationState
from .infection_models.v5_wells_riley import CAT
from .config import DMP_API, INFECTION_MODEL
import pandas as pd
from io import StringIO
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

class InfectionManager:
    def __init__(self, matrices_dict, timestep=None, people=[]):
        self.matrices_dict = matrices_dict  
        self.timestep = timestep or INFECTION_MODEL["default_timestep"]
        self.multidisease = INFECTION_MODEL["allow_multidisease"]
        self.infected = []
        
        # Enhanced caching and batching
        self._dmp_cache = {}
        self._pending_timeline_requests = []
        self._cache_lock = threading.Lock()
        
        # Connection pooling for better performance
        self._session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        
        # Thread pool for concurrent API calls
        self._executor = ThreadPoolExecutor(max_workers=5)
        
        # Fast lookup structures
        self._infected_set = set()
        
        for p in people:
            for v in p.states.values():
                if InfectionState.INFECTED in v:
                    self.infected.append(p)
                    self._infected_set.add(p.id)
    
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

    # def run_model(self, num_timesteps=4, file=None, curtime=0, variantInfected={}, newlyInfected={}):
    #     if file is not None:
    #         file.write(f'====== TIMESTEP {curtime} ======\n')
    #         for variant in variantInfected.keys():
    #             infected_ids = [i.id for i in self.infected if variant in i.states and i.states[variant] != InfectionState.SUSCEPTIBLE]
    #             file.write(f'{variant}: {infected_ids}\n')
    #             file.write(f"{variant} count: {len(infected_ids)}\n")

    #     # Update the infection counts for each variant
    #     for i in self.infected:
    #         for disease in variantInfected.keys():
    #             if disease in i.states and i.states[disease] != InfectionState.SUSCEPTIBLE:
    #                 variantInfected[disease][i.id] = int(i.states[disease].value)

    #     # Update the state of each person based on the current time
    #     for i in self.infected:
    #         i.update_state(curtime, self.matrices_dict.keys())

    #     # Evaluate the possibility of new infections
    #     for i in self.infected:
    #         if i.invisible:
    #             continue

    #         for p in i.location.population:
    #             if i == p or p.invisible:
    #                 continue

    #             new_infections = []

    #             for disease, state in i.states.items():
    #                 if InfectionState.INFECTIOUS not in state:
    #                     continue
    #                 if p.states.get(disease) is not None and InfectionState.INFECTED in p.states[disease]:
    #                     continue

    #                 mask_modifier = self.calculate_mask_transmission_modifier(i, p)
    #                 base_transmission_prob = 7e3 * (1 - mask_modifier)

                    
    #                 # Assuming CAT function can h andle the matrix without needing to specify a disease
    #                 if CAT(p, True, num_timesteps, base_transmission_prob):
    #                     new_infections.append(disease)
                        
    #                     if newlyInfected.get(disease) == None:
    #                         newlyInfected[disease] = {}
    #                     newlyInfected[disease][str(i.id)] = [ *newlyInfected.get(str(i.id), []), str(p.id) ]
                        
    #                     break

    #             for disease in new_infections:
    #                 self.infected.append(p)  # Add to list of infected regardless
    #                 if len(new_infections) == 1 or self.multidisease:
    #                     self.create_timeline(p, disease, curtime)
                        
    #                     if file is not None:
    #                         file.write(f'{i.id} infected {p.id} @ location {p.location.id} w/ {disease}\n')
    
    def run_model(self, num_timesteps=4, file=None, curtime=0, variantInfected={}, newlyInfected={}):
        if file is not None:
            file.write(f'====== TIMESTEP {curtime} ======\n')
            for variant in variantInfected.keys():
                infected_ids = [i.id for i in self.infected if variant in i.states and i.states[variant] != InfectionState.SUSCEPTIBLE]
                file.write(f'{variant}: {infected_ids}\n')
                file.write(f"{variant} count: {len(infected_ids)}\n")

        # Optimized infection count updates using batch processing
        for disease in variantInfected.keys():
            for i in self.infected:
                if disease in i.states and i.states[disease] != InfectionState.SUSCEPTIBLE:
                    variantInfected[disease][i.id] = int(i.states[disease].value)

        # Batch update states for better performance
        matrix_keys = list(self.matrices_dict.keys())
        for i in self.infected:
            i.update_state(curtime, matrix_keys)

        # Highly optimized infection evaluation with early exits and batch processing
        new_infection_batch = []
        
        for i in self.infected:
            if i.invisible:
                continue

            # Pre-compute infector mask status once
            infector_masked = i.is_masked()
            location_population = list(i.location.population)  # Cache population list
            
            for p in location_population:
                if i == p or p.invisible or p.id in self._infected_set:
                    continue

                new_infections = []

                for disease, state in i.states.items():
                    # Fast state checks with early exits
                    if (InfectionState.INFECTIOUS not in state or
                        (p.states.get(disease) is not None and InfectionState.SUSCEPTIBLE not in p.states[disease])):
                        continue

                    # Cache susceptible mask status
                    susceptible_masked = p.is_masked()
                    
                    # Call CAT with optimized parameters
                    if CAT(p, True, num_timesteps, 7e3, infector_masked, susceptible_masked):
                        new_infections.append(disease)
                        
                        # Track newly infected individuals efficiently
                        if disease not in newlyInfected:
                            newlyInfected[disease] = {}
                        if str(i.id) not in newlyInfected[disease]:
                            newlyInfected[disease][str(i.id)] = []
                        newlyInfected[disease][str(i.id)].append(str(p.id))
                        break  # Early exit after first infection

                # Batch new infections for processing
                for disease in new_infections:
                    if p.id not in self._infected_set:
                        self.infected.append(p)
                        self._infected_set.add(p.id)
                        new_infection_batch.append((p, disease, curtime))
                        
                        if file is not None:
                            file.write(f'{i.id} infected {p.id} @ location {p.location.id} w/ {disease}\n')
        
        # Process new infections in batch
        if new_infection_batch:
            self._process_new_infections_batch(new_infection_batch)

    def calculate_mask_transmission_modifier(self, infector, susceptible):
        from .simulate import Maskingeffects 
        return Maskingeffects.calculate_mask_transmission_modifier(infector, susceptible)
    

    def _process_new_infections_batch(self, new_infection_batch):
        """Process multiple new infections efficiently"""
        # Group by cache key to minimize API calls
        cache_groups = {}
        for person, disease, curtime in new_infection_batch:
            vax_status = "Vaccinated" if person.interventions["vaccine"] != VaccinationState.NONE else "Unvaccinated"
            cache_key = f"{person.age}_{vax_status}_{person.sex}_{disease}"
            
            if cache_key not in cache_groups:
                cache_groups[cache_key] = []
            cache_groups[cache_key].append((person, disease, curtime))
        
        # Process each group
        for cache_key, group in cache_groups.items():
            with self._cache_lock:
                if cache_key in self._dmp_cache:
                    # Use cached data for all in group
                    timeline_data = self._dmp_cache[cache_key]
                    for person, disease, curtime in group:
                        self._apply_timeline_to_person(person, disease, curtime, timeline_data)
                else:
                    # Add to pending requests
                    self._pending_timeline_requests.extend([(p, d, c, cache_key) for p, d, c in group])
        
        # Process pending requests if we have enough
        if len(self._pending_timeline_requests) >= 5:  # Lower threshold for faster processing
            self._process_timeline_batch_concurrent()
    
    def create_timeline_cached(self, person, disease, curtime):
        """Create a disease timeline with enhanced caching"""
        vax_status = "Vaccinated" if person.interventions["vaccine"] != VaccinationState.NONE else "Unvaccinated"
        cache_key = f"{person.age}_{vax_status}_{person.sex}_{disease}"
        
        with self._cache_lock:
            if cache_key in self._dmp_cache:
                timeline_data = self._dmp_cache[cache_key]
                self._apply_timeline_to_person(person, disease, curtime, timeline_data)
                return
        
        # Add to pending requests
        self._pending_timeline_requests.append((person, disease, curtime, cache_key))
        
        # Process batch with lower threshold
        if len(self._pending_timeline_requests) >= 5:
            self._process_timeline_batch_concurrent()
        else:
            self._use_fallback_timeline(person, disease, curtime)
    
    def _process_timeline_batch_concurrent(self):
        """Process timeline requests with concurrent API calls"""
        if not self._pending_timeline_requests:
            return
            
        BASE_URL = DMP_API["base_url"]
        
        # Group requests by cache key to avoid duplicates
        unique_requests = {}
        for person, disease, curtime, cache_key in self._pending_timeline_requests:
            if cache_key not in unique_requests:
                unique_requests[cache_key] = []
            unique_requests[cache_key].append((person, disease, curtime))
        
        # Submit concurrent API requests
        future_to_cache_key = {}
        for cache_key, persons_list in unique_requests.items():
            person, disease, curtime = persons_list[0]
            
            simulation_payload = {
                "demographics": {
                    "Age": str(person.age),
                    "Vaccination Status": "Vaccinated" if person.interventions["vaccine"] != VaccinationState.NONE else "Unvaccinated",
                    "Sex": "F" if person.sex == 1 else "M",
                    "Variant": disease 
                }
            }
            
            future = self._executor.submit(self._make_api_request, BASE_URL, simulation_payload)
            future_to_cache_key[future] = (cache_key, persons_list)
        
        # Process completed requests
        for future in as_completed(future_to_cache_key, timeout=10):
            cache_key, persons_list = future_to_cache_key[future]
            try:
                timeline_data = future.result()
                if timeline_data:
                    with self._cache_lock:
                        self._dmp_cache[cache_key] = timeline_data
                    
                    for person, disease, curtime in persons_list:
                        self._apply_timeline_to_person(person, disease, curtime, timeline_data)
                else:
                    # Use fallback
                    for person, disease, curtime in persons_list:
                        self._use_fallback_timeline(person, disease, curtime)
            except Exception as e:
                # Use fallback for all persons in this group
                for person, disease, curtime in persons_list:
                    self._use_fallback_timeline(person, disease, curtime)
        
        # Clear pending requests
        self._pending_timeline_requests.clear()
    
    def _make_api_request(self, base_url, payload):
        """Make API request with connection pooling"""
        try:
            response = self._session.post(f"{base_url}/simulate", json=payload, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return None
    
    def _apply_timeline_to_person(self, person, disease, curtime, timeline_data):
        """Apply timeline data to a person"""
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
    
    def _use_fallback_timeline(self, person, disease, curtime):
        """Use fallback timeline when API is unavailable"""
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
    
    def create_timeline(self, person, disease, curtime):
        """Backward compatibility wrapper"""
        self.create_timeline_cached(person, disease, curtime)
    
    def __del__(self):
        """Cleanup resources"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
        if hasattr(self, '_session'):
            self._session.close()