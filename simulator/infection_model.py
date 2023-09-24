# Calculate the probability of infection between two people
# over a given time interval (in this case, a timestep in minutes)
# TODO: This will be replaced with an accurate model of infection in the future
def probability_model(p1, p2):
    if p1.location.id != p2.location.id:
        raise Exception(f'{p1.id}/{p1.location.id} : {p2.id}/{p2.location.id}')
    return 0.00005 # one in a million chance per timestep interval