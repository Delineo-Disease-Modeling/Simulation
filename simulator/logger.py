import os
import logging
from collections import defaultdict

import pandas as pd

from .pap import Person, Location, InfectionState, VaccinationState
from . import agentstats as ast

class SimulationLogger:
    """Logging system for simulation"""

    def __init__ (self, log_dir = "simulation_logs", enable_file_logging = True):
        self.log_dir = log_dir
        self.enable_file_logging = enable_file_logging

        if self.enable_file_logging:
            os.makedirs(log_dir, exist_ok=True)

        self.person_logs = []
        self.movement_logs = []
        self.infection_logs = []
        self.intervention_logs = []
        self.location_logs = []
        self.contact_logs = []
        self.exposure_logs = []

        self.person_states = {}
        self.location_population = defaultdict(list)
        self.infection_chains = {}

        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level = logging.INFO,
            format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers = [
                logging.StreamHandler(),
                logging.FileHandler(f'{self.log_dir}/simulation.log' if self.enable_file_logging else logging.NullHandler())
            ]
        )
        self.logger = logging.getLogger('DiseaseSimulator')

    def log_person_demographics(self, person: Person, timestep):
        """Log person demographics and current state"""
        vax = person.vaccination_state
        vax_doses = vax.value
        vax_status = f"Vaccinated ({vax_doses} doses)" if vax != VaccinationState.NONE else "Unvaccinated"

        infection_status = {}
        infectious_variants = []
        symptomatic_variants = []

        for variant, state in person.states.items():
            infection_status[variant] = {
                'infected': bool(state & InfectionState.INFECTED),
                'infectious': bool(state & InfectionState.INFECTIOUS),
                'symptomatic': bool(state & InfectionState.SYMPTOMATIC),
                'recovered': bool(state & InfectionState.RECOVERED),
                'deceased': bool(state & InfectionState.REMOVED)
            }

            if state & InfectionState.INFECTIOUS:
                infectious_variants.append(variant)
            if state & InfectionState.SYMPTOMATIC:
                symptomatic_variants.append(variant)

        loc = person.location
        location_capacity = loc.capacity if loc else -1

        person_log = {
            'timestep': timestep,
            'person_id': person.id,
            'age': person.age,
            'sex': person.sex,
            'household_id': person.household.id if person.household else None,
            'current_location_id': loc.id if loc else None,
            'current_location_type': loc.location_type if loc else "unknown",
            'location_capacity': location_capacity,
            'location_occupancy': loc.total_count if loc else 0,
            'location_utilization': loc.total_count / location_capacity if loc and location_capacity > 0 else 0,
            'is_masked': person.is_masked(),
            'vaccination_status': vax_status,
            'vaccination_doses': vax_doses,
            'infectious_variants': infectious_variants,
            'symptomatic_variants': symptomatic_variants,
            'total_variants_infected': len([v for v in infection_status.values() if v['infected']]),
            'infection_status': infection_status
        }

        self.person_logs.append(person_log)
        self.person_states[person.id] = person_log.copy()

    def log_movement(self, person: Person, from_location: Location, to_location: Location, timestep, reason="normal"):
        movement_log = {
            'timestep': timestep,
            'person_id': person.id,
            'from_location_id': from_location.id if from_location else None,
            'from_location_type': from_location.location_type if from_location else None,
            'to_location_id': to_location.id if to_location else None,
            'to_location_type': to_location.location_type if to_location else None,
            'movement_reason': reason,
            'person_age': person.age,
            'person_sex': person.sex,
            'is_infectious': person.is_infectious(),
            'is_symptomatic': person.is_symptomatic(),
            'is_masked': person.is_masked(),
            'from_occupancy': from_location.total_count if from_location else 0,
            'to_occupancy': to_location.total_count if to_location else 0,
            'to_capacity': to_location.capacity if to_location else -1
        }

        self.movement_logs.append(movement_log)

    def log_infection_event(self, infected_person: Person, infector_person: Person, location: Location, variant, timestep):
        """Log an infection event"""
        infection_log = {
            'timestep': timestep,
            'infected_person_id': infected_person.id,
            'infected_age': infected_person.age,
            'infected_sex': infected_person.sex,
            'infected_masked': infected_person.is_masked(),
            'infected_vaccination_doses': infected_person.vaccination_state.value,
            'infector_person_id': infector_person.id if infector_person else None,
            'infector_age': infector_person.age if infector_person else None,
            'infector_sex': infector_person.sex if infector_person else None,
            'infector_masked': infector_person.is_masked() if infector_person else False,
            'infector_vaccination_doses': infector_person.vaccination_state.value if infector_person else 0,
            'infection_location_id': location.id if location else None,
            'infection_location_type': location.location_type if location else None,
            'location_occupancy': location.total_count if location else 0,
            'location_capacity': location.capacity if location else -1,
            'variant': variant,
            'transmission_pair_age_diff': abs(infected_person.age - infector_person.age) if infector_person else None,
        }
        self.infection_logs.append(infection_log)

        if infector_person:
            self.infection_chains[infected_person.id] = {
                'infector_id': infector_person.id,
                'location_id': location.id if location else None,
                'variant': variant,
                'timestep': timestep
            }

    def log_intervention_effect(self, person: Person, intervention_type, effect, timestep, location: Location = None):
        """Log when interventions affect person behavior"""
        intervention_log = {
            'timestep': timestep,
            'person_id': person.id,
            'intervention_type': intervention_type,
            'effect': effect,
            'person_age': person.age,
            'person_sex': person.sex,
            'person_infectious': person.is_infectious(),
            'person_symptomatic': person.is_symptomatic(),
            'location_id': location.id if location else None,
            'location_type': location.location_type if location else None,
            'location_occupancy': location.total_count if location else 0,
            'location_capacity': location.capacity if location else -1
        }

        self.intervention_logs.append(intervention_log.copy())

    def log_location_state(self, location: Location, timestep):
        population = location.population
        infectious_count = sum(1 for p in population if p.is_infectious())
        symptomatic_count = sum(1 for p in population if p.is_symptomatic())
        masked_count = sum(1 for p in population if p.is_masked())
        vaccinated_count = sum(1 for p in population if p.vaccination_state != VaccinationState.NONE)

        ages = [p.age for p in population]
        avg_age = sum(ages) / len(ages) if ages else 0
        cap = location.capacity if location.capacity > 0 else 1

        location_log = {
            'timestep': timestep,
            'location_id': location.id,
            'location_type': location.location_type,
            'capacity': location.capacity,
            'occupancy': location.total_count,
            'utilization_rate': location.total_count / cap,
            'infectious_count': infectious_count,
            'symptomatic_count': symptomatic_count,
            'masked_count': masked_count,
            'vaccinated_count': vaccinated_count,
            'avg_age': avg_age,
            'male_count': sum(1 for p in population if p.sex == '0'),
            'female_count': sum(1 for p in population if p.sex == '1')
        }

        self.location_logs.append(location_log)

    def log_contact_event(self, person1: Person, person2: Person, location: Location, timestep, contact_duration=1):
        contact_log = {
            'timestep': timestep,
            'person1_id': person1.id,
            'person2_id': person2.id,
            'location_id': location.id if location else None,
            'location_type': location.location_type if location else None,
            'contact_duration': contact_duration,
            'person1_infectious': person1.is_infectious(),
            'person2_infectious': person2.is_infectious(),
            'person1_masked': person1.is_masked(),
            'person2_masked': person2.is_masked(),
            'both_masked': person1.is_masked() and person2.is_masked(),
            'age_diff': abs(person1.age - person2.age),
            'same_household': person1.household.id == person2.household.id,
        }

        self.contact_logs.append(contact_log)

    def calculate_transmission_risk(self, infected_person: Person, infector_person: Person, location: Location):
        if not infector_person or not location:
            return 0

        risk = 1.0

        if infected_person.is_masked():
            risk *= 0.5
        if infector_person.is_masked():
            risk *= 0.5

        if location.capacity > 0:
            risk *= (1 + location.total_count / location.capacity)

        return risk

    def calculate_location_risk(self, location: Location):
        if not location.population:
            return 0

        infectious_count = sum(1 for p in location.population if p.is_infectious())
        if infectious_count == 0:
            return 0

        risk = infectious_count / location.total_count
        if location.capacity > 0:
            risk *= (1 + location.total_count / location.capacity)

        masked_rate = sum(1 for p in location.population if p.is_masked()) / location.total_count
        risk *= (1 - masked_rate * 0.3)

        return risk

    def calculate_contact_risk(self, person1: Person, person2: Person, location: Location):
        if not person1.is_infectious() and not person2.is_infectious():
            return 0

        risk = 1.0

        if person1.is_masked():
            risk *= 0.7
        if person2.is_masked():
            risk *= 0.7

        if location.capacity > 0:
            risk *= (1 + location.total_count / location.capacity * 0.5)

        return risk

    def export_logs_to_csv(self):
        if not self.enable_file_logging:
            return

        if self.person_logs:
            df = pd.DataFrame(self.person_logs)
            df.to_csv(f'{self.log_dir}/person_logs.csv', index=False)

        if self.movement_logs:
            df = pd.DataFrame(self.movement_logs)
            df.to_csv(f'{self.log_dir}/movement_logs.csv', index=False)

        if self.infection_logs:
            df = pd.DataFrame(self.infection_logs)
            df.to_csv(f'{self.log_dir}/infection_logs.csv', index=False)

        if self.intervention_logs:
            df = pd.DataFrame(self.intervention_logs)
            df.to_csv(f'{self.log_dir}/intervention_logs.csv', index=False)

        if self.location_logs:
            df = pd.DataFrame(self.location_logs)
            df.to_csv(f'{self.log_dir}/location_logs.csv', index=False)

        if self.contact_logs:
            df = pd.DataFrame(self.contact_logs)
            df.to_csv(f'{self.log_dir}/contact_logs.csv', index=False)

        if self.infection_chains:
            chains_df = pd.DataFrame.from_dict(self.infection_chains, orient='index')
            chains_df.reset_index(inplace=True)
            chains_df.rename(columns={'index': 'infected_person_id'}, inplace=True)
            chains_df.to_csv(f'{self.log_dir}/infection_chains.csv', index=False)


    def generate_summary_report(self):
        if not self.enable_file_logging:
            return

        report = []
        report.append("=== Simulation Summary Report ===\n")

        total_people = len(set(log['person_id'] for log in self.person_logs))
        total_infections = len(self.infection_logs)
        total_movements = len(self.movement_logs)

        report.append(f"Total people: {total_people}")
        report.append(f"Total infections: {total_infections}")
        report.append(f"Total movements: {total_movements}")

        if self.intervention_logs:
            interventions = pd.DataFrame(self.intervention_logs)
            intervention_summary = interventions.groupby('intervention_type').size()
            report.append("\nIntervention Events:")
            for intervention, count in intervention_summary.items():
                report.append(f"  {intervention}: {count} events")

        with open(f'{self.log_dir}/summary_report.txt', 'w') as f:
            f.write("\n".join(report))

    def graphic_analysis(self):
        if not self.enable_file_logging or not self.infection_logs:
            return 0

        #construct graph
        start = ast.Node(-1,-1,None)
        ast.build_agent_graph_nodupes(start, f'{self.log_dir}/infection_logs.csv')

        #run analysis
        report = []
        ast.calculate_all_harmonic(start)
        ast.check_sse(start, report)
        ast.location_impact(start, report)
        ast.time_gates(start, report)
        ast.time_impact(start, report)

        with open(f'{self.log_dir}/graph_report.txt', 'w') as f:
            f.write("\n".join(report))

        return 1
