import json
import pandas as pd

# Adding category names to algos output (UNUSED)

with open('facility_data.json', 'r', encoding='utf-8') as f:
  facility_data = json.load(f)
  
df = pd.read_csv('barnsdall.pois.csv')

for place, data in facility_data['places'].items():
  loc = df.loc[(df['location_name'].eq(data['label'])) & df['latitude'].eq(data['latitude']) & df['longitude'].eq(data['longitude'])]
  
  if loc.empty:
    continue
  
  #print(loc['top_category'].values)
  
  facility_data['places'][place]['top_category'] = loc['top_category'].values[0]
  facility_data['places'][place]['sub_category'] = loc['sub_category'].values[0]
  
with open('pap_places.json', 'w', encoding='utf-8') as f:
  json.dump(facility_data, f, ensure_ascii=False, indent=4)