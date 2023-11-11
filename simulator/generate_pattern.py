import json
import random
import os

# Check if the "pattern_simple.json" file exists
if not os.path.exists('pattern_simple.json'):
    with open('pattern_simple.json', 'w') as new_file:
        # Create an empty dictionary
        json.dump({}, new_file)

# Load data from papdata.json
with open('papdata.json') as file:
    papdata = json.load(file)

# Define the timestamp intervals
timestamps = []  
for i in range(1, 100):
    timestamps.append(i*60)

# Initialize the patterns dictionary
patterns = {}

# Generate patterns for each timestamp
for timestamp in timestamps:
    pattern = {
        "homes": {},
        "places": {}
    }

    # Assign people to their respective homes
    for person_id, person_data in papdata['people'].items():
        home_id = person_data['home']
        if home_id not in pattern["homes"]:
            pattern["homes"][home_id] = []
        pattern["homes"][home_id].append(person_id)

    # Assign people to places
    for place_id, place_data in papdata['places'].items():
        pattern["places"][place_id] = []
        total_people = place_data['capacity']

        # Randomly select people for the place
        random_people = random.sample(papdata['people'].keys(), min(total_people, len(papdata['people'])))
        pattern["places"][place_id] = random_people

    # Add the pattern to the dictionary with the timestamp
    patterns[str(timestamp)] = pattern

# Save the patterns to pattern_simple.json
with open('pattern_simple.json', 'w') as outfile:
    json.dump(patterns, outfile, indent=4)
