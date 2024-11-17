from .pap import InfectionState, InfectionTimeline, VaccinationState
from .infection_model import CAT
from dmp.user_input import process_dataframes
import pandas as pd
from io import StringIO

class InfectionManager:
    def __init__(self, matrices_dict, timestep=15, people=[]):
        self.matrices_dict = matrices_dict  
        self.timestep = timestep
        self.multidisease = True
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
                    
                    # Assuming CAT function can h andle the matrix without needing to specify a disease
                    if CAT(p, True, num_timesteps, 7e2):
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



    # When will this person turn from infected to infectious? And later symptomatic? Hospitalized?
    def create_timeline(self, person, disease, curtime):
        # tl = process_dataframes([self.matrices], {})[0]
        
        demographic_info = pd.read_csv(StringIO(f'Sex,Age,Is_Vaccinated,Matrix_Set\n{"M" if person.sex == 0 else "F"},{person.age},{person.interventions["vaccine"] != VaccinationState.NONE},1'))

        matrices = self.matrices_dict[disease]
        tl = process_dataframes(demographic_info, matrices)[0]
        
        tl.pop('Sex', None)
        tl.pop('Age', None)
        tl.pop('Is_Vaccinated', None)
        tl.pop('Matrix_Set', None)
                        
        mint = tl[min(tl, key=tl.get)]
        maxt = 10080 #tl[max(tl, key=tl.get)]
        
        val = {}
        val[disease] = {
            InfectionState.INFECTED: InfectionTimeline(curtime, curtime + maxt)
        }
                
        str_to_state = {
            'Symptomatic': InfectionState.SYMPTOMATIC,
            'Infectious Asymptomatic': InfectionState.INFECTIOUS,
            'Infectious Symptomatic': InfectionState.INFECTIOUS,
            'Infectious Symptomatic': InfectionState.SYMPTOMATIC,
            'Hospitalized': InfectionState.HOSPITALIZED,
            'ICU': InfectionState.HOSPITALIZED,
            'Recovered': InfectionState.RECOVERED,
            'Removed': InfectionState.REMOVED
        }
        
        for str, state in str_to_state.items():
            if str in tl.keys():
                if state in val[disease].keys():
                    curmin = val[disease][state].start
                    val[disease][state] = InfectionTimeline(min(curmin, curtime + tl[str]), curtime + maxt)
                else:
                    val[disease][state] = InfectionTimeline(curtime + tl[str], curtime + maxt)
                
        person.timeline = val