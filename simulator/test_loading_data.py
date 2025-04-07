from data_interface import *
import json

data = load_movement_pap_data()
print(data)

movement_patterns = data['movement_patterns']
pap_data = data['papdata']
print(movement_patterns)
print(pap_data)
