from pap import VaccinationState

# Calculate the probability of infection from p1 to p2
# over a given time interval (in this case, a timestep in minutes)
# TODO: This will be replaced with an accurate model of infection in the future
def probability_model(p1, p2):
    if p1.location.id != p2.location.id:
        raise Exception(f'{p1.id}/{p1.location.id} : {p2.id}/{p2.location.id}')

    chance = 0.0017
    
    if p1.interventions.get('mask') == True:
        chance *= 0.5
    
    if p2.interventions.get('mask') == True:
        chance *= 0.5
    
    if p2.interventions.get('vaccine') == VaccinationState.PARTIAL:
        chance *= 0.5
    elif p2.interventions.get('vaccine') == VaccinationState.IMMUNIZED:
        chance *= 0.1
    
    return chance