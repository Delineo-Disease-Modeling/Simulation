## README V0: Simulator and Algorithms Team Integration 

## Overview 
This documentation covers the integration of the simulator and the algorithms team's outputs (people and places data, movement patterns, CBGs)

## Version 0: Initial Integration 

## 1. Integrating People and Places Data 
`data_interface.py` has two functions load_people() and load_places(). These send an HTTPS request to the central database to get people and places data that can be used. 

Expected format of people and places data: 
```
       "people": {
            "0": {
                "sex": "M", 
                "age": 52, 
                "home": 0
                },
            "1": {
                "sex": "F", 
                "age": 30,
                 "home": 1
                 }
        }, 
        "places": {
            "0": {
                "label": "school",
                "cbg": "1", 
                },
            "1": {
                "cbg": "24003707003", 
                "label": "work", 
                "capacity": 25
                }
        }
```
`simulate.py` calls load_people() and load_places() to get dictionaries of people and places, adds the information to the simulator, and then runs the simulation. 

## 2. Integrating Movement Patterns Data

