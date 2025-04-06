from data_interface import load_people, load_places, load_sample_data
import json

pap = load_sample_data()
people = pap['people']
places = pap['places']
homes = pap['homes']
print("All data", pap)
print("---------------")
print("People data", people)
print("---------------")
print("Places data", places)
print("---------------")
print("Homes data", homes)