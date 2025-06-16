import numpy as np
import pandas as pd
import yaml
import json

import random
random.seed(2)

from enum import Flag, Enum

'''
    GLOBAL VARIABLES
'''

'''
    Class Definitions to use in pop_mov_sim
'''

# Use bitwise operators
class InfectionState(Flag):
    SUSCEPTIBLE = 0 # Default value for all diseases
    INFECTED = 1
    INFECTIOUS = 2
    SYMPTOMATIC = 4
    HOSPITALIZED = 8
    RECOVERED = 16
    REMOVED = 32
    
class VaccinationState(Enum):
    NONE = 0 
    PARTIAL = 1 # Not yet up-to-date on boosters?
    IMMUNIZED = 2

class InfectionTimeline:
    def __init__(self, start, end):
        self.start = int(start)
        self.end = int(end)

class Person:
    '''
    Class for each individual
    '''
    def __init__(self, id, sex, age, household):
        self.id = id
        self.sex = sex # male 0 female 1
        self.age = age
        self.household = household
        self.location = household
        self.invisible = False
        self.states = {}
        self.timeline = {}
        self.interventions = {
            'mask': False,
            'vaccine': VaccinationState.NONE
        }
        self.vaccination_state = 0
    
    def set_masked(self, masked):
        self.interventions['mask'] = masked
    
    def get_masked(self):
        return self.interventions['mask']
    
    def set_vaccinated(self, state):
        self.interventions['vaccine'] = state
        
    def get_vaccinated(self):
        return self.interventions['vaccine']
    
    # Returns whether user has a state on ANY disease
    def get_state(self, state):
        for val in self.states.values():
            if state in val:
                return True
        
        return False
    
    def update_state(self, curtime, variants):
        '''
        Updates the InfectionState of this Person based on the current time
        self.timeline is a dict where the keys are the InfectionStates and values are
            the times at which this person will become that state
        '''
        self.invisible = False
        
        for variant in variants: 
            self.states[variant] = InfectionState.SUSCEPTIBLE

        for disease, value in self.timeline.items():
            for state, timeline in value.items():
                if timeline.end <= curtime:
                    self.states[disease] = self.states[disease] & ~state
                elif timeline.start <= curtime:
                    self.states[disease] = self.states[disease] | state
                    if state == InfectionState.REMOVED or state == InfectionState.RECOVERED or state == InfectionState.HOSPITALIZED:
                        self.invisible = True

            

class Population:
    '''
    Class for storing population
    '''
    def __init__(self):
        #total population
        self.total_count = 0
        #container for persons in the population
        self.population = []
    
    def add_member(self, person):
        '''
        Adds member to the household, with sanity rules applied
        @param person = person to be added to household
        '''
        self.population.append(person)
        self.total_count = len(self.population)
    
    def remove_member(self, person_id):
        self.population = [x for x in self.population if x.id != person_id]
        self.total_count = len(self.population)
        
class Household(Population):
    ''' 
    Household class, inheriting Population since its a small population
    '''
    count = 0
    
    def __init__(self, cbg, id=None):
        super().__init__()
        self.cbg = cbg
        if id is None:
            self.id = str(Household.count)
            Household.count += 1
        else:
            self.id = id

class Facility(Population):
    def __init__(self, id, cbg, label, capacity=-1):
        super().__init__()
        self.cbg = cbg
        self.id = id
        self.label = label
        
        # maximum amount of people that can be in this population (-1 = no limit)
        self.capacity = capacity


    
'''
    if ran(not imported), yields household assignment values
'''
if __name__== '__main__':
    def create_households(pop_data, households, cbg):
        result = []
        '''
            FOR INFORMATION: family_percents = [married, opposite_sex, same_sex, female_single, male_single, other]
        '''
        family_types = ['married', 'opposite_sex', 'same_sex', 'female_single', 'male_single', 'other']
        
        for i in range(len(family_types)):
            for _ in range(int(households * pop_data['family_percents'][i])):
                result.append(create_household(pop_data, cbg, family_types[i]))

        return result
    
    def create_household(pop_data, cbg, type):
        household = Household(cbg)
        
        age_percent = 0.0
        age_group = 0
        
        if type == 'married':
            age_percent = pop_data['age_percent_married']
            age_group = random.choices(pop_data['age_groups_married'], age_percent)[0]
        else:
            age_percent = pop_data['age_percent']
            age_group = random.choices(pop_data['age_groups'], age_percent)[0]
        
        if type == 'married' or type == 'same_sex' or type == 'opposite_sex':
            ages = random.choices(range(age_group, age_group + 10), k=2)
            sexes = [ 0, 1 ]
            
            # Ensure same sex relationship for this household type
            if type == 'samesex':
                samesex = random.choices([0, 1], [pop_data['male_percent'], pop_data['female_percent']])
                sexes = [ samesex[0], samesex[0] ]

            household.add_member(Person(pop_data['count'], sexes[0], ages[0], household))
            household.add_member(Person(pop_data['count'] + 1, sexes[1], ages[1], household))
            pop_data['count'] += 2

            # TODO: 2 Main issues:
            # For now, married families are the only family types that can have kids
            # Additionally, it's assumed that they are an opposite-sex relationship
            if type == 'married':
                handle_children_hh(pop_data, cbg, household)
                
        else: # single/other household
            age = random.choice(range(age_group, age_group + 10))
            sex = 1 if type == 'female_single' else 0
            
            if type == 'other':
                sex = random.choices([0, 1], [pop_data['male_percent'], pop_data['female_percent']])[0]

            household.add_member(Person(pop_data['count'], sex, age, household))
            pop_data['count'] += 1
            
        return household
    
    def handle_children_hh(pop_data, cbg, household):
        child_chance = pop_data['children_true_percent']
        has_children = random.choices([True, False], [child_chance, 1.0 - child_chance])[0]

        if has_children:
            num_children = random.choices(pop_data['children_groups'], pop_data['children_percent'])[0]
            ages = random.choices(range(1, 19), k=num_children)
            sexes = random.choices([0, 1], [pop_data['male_percent'], pop_data['female_percent']], k=num_children)
            for i in range(num_children):
                household.add_member(Person(pop_data['count'], sexes[i], ages[i], household))
                pop_data['count'] += 1

    def create_pop_from_cluster(cluster, census_df):
        populations = 0
        households = 0
        for i in cluster:
            populations += int(census_df[census_df.census_block_group == int(i)].values[0][1])
            households += int(census_df[census_df.census_block_group == int(i)].values[0][2])

        return populations, households

    # reading population information from yaml file
    pop_data = {}

    with open('population_info.yaml', mode="r", encoding="utf-8") as file:
        pop_data = yaml.full_load(file)

    # Reading Census Information
    census_df = pd.read_csv('cbg_populations.csv')

    # read clusters into string array in order to easier census search
    cluster_df = pd.read_csv('clusters.csv')
    clusters = [str(i) for i in list(cluster_df['cbgs'])]

    household_list = []

    # get number of households
    for cbg in clusters:
        _, household = create_pop_from_cluster([cbg], census_df)
        household_list.append(create_households(pop_data, household, cbg))
    
    # Flatten list
    household_list = [item for sublist in household_list for item in sublist]
    
    # Dump people and house data into new papdata.json file
    with open('papdata.json', 'w', encoding='utf-8') as f:
        data = {'people': {}, 'homes': {}, 'places': {}}
        
        for house in household_list:
            data['homes'][house.id] = { 'cbg': house.cbg, 'members': house.total_count }
            
            for person in house.population:
                data['people'][person.id] = { 'sex': person.sex, 'age': person.age, 'home': house.id }
        
        json.dump(data, f, ensure_ascii=False, indent=4)

    with open('facility_data.json', 'r', encoding='utf-8') as f:
        facility_data = json.load(f)

    data['places'] = facility_data['places']

    with open('papdata.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    print("Successfully Created PAP Data")

    # Dump household list data into households.yaml file
    #with open('households.yaml', mode="wt", encoding="utf-8") as outstream:
    #    yaml.dump(household_list, outstream)