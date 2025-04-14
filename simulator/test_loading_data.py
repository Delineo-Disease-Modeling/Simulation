from data_interface import *
import json

data = load_movement_pap_data()
patterns = data.get("data", {}).get("patterns", {})
papdata = data.get("data", {}).get("papdata", {})
people_data = papdata.get("people", {})
places_data = papdata.get("places", {})
homes_data = papdata.get("homes", {})

print("Movement Patterns: ")
print(patterns)
print("Patterns printed successfully")
print("-------------------------------")

print("People and places data")
print(papdata)
print("pap data printed successfully")
print("-------------------------------")

print("People data")
print(people_data)
print("People data printed successfully")   
print("-------------------------------")

print("Homes data")
print(homes_data)
print("-------------------------------")


print("Places data")
print(places_data)
print("-------------------------------")



