#gen_types.py

import pandas as pd

res_mix = { "biomass":     round(float(  1841/290961), 4),
            "coal":        round(float( 44596/290961), 4),
            "geo-thermal": round(float(  4238/290961), 4),
            "gas":         round(float( 10826/290961), 4),
            "hydro":       round(float( 60588/290961), 4), 
            "nuclear":     round(float(  7733/290961), 4), 
            "pumped_sto":  round(float(  4255/290961), 4), 
            "utility_pv":  round(float(  4255/290961), 4), 
            "wind":        round(float( 21032/290961), 4), 
            "DPV":         round(float(  9982/290961), 4)   } 

gen_data=pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\gen_data_raw.csv", header=0)
gen_data["ID"] = gen_data["ID"].str.replace(' ', '')
gen_data["ID"] = gen_data["ID"].str.replace("'", '')

accounted_for = { "biomass":  0.0, "coal": 0.0, "geo-thermal": 0.0, "gas": 0.0, "hydro": 0.0, "nuclear": 0.0,  "pumped_sto": 0.0,  "utility_pv":  0.0, "wind":  0.0, "DPV": 0.0 }  

for i, row in gen_data.iterrows():
    if  row['ID'][0]=='C' :
        accounted_for['coal'] += row['PT']

    elif row['ID'] in ['B', 'NB']:
        accounted_for['biomass'] += row['PT']

    elif row['ID']=='G' :
        accounted_for['gas'] += row['PT']

    elif row['ID']=='S' :
        accounted_for['utility_pv'] += row['PT']

    elif row['ID'] in ['E', 'NE' , 'CE']:
        accounted_for['geo-thermal'] += row['PT']

    elif row['ID'] in ['N', 'NN'] :
        accounted_for['nuclear'] += row['PT']

    elif row['ID'] in ['H', 'NH', 'SH']:
        accounted_for['hydro'] += row['PT']

    elif row['ID'] in ['P', 'NP']:
        accounted_for['pumped_sto'] += row['PT']

    elif row['ID'] in ['W', 'NW', 'SW']:
        accounted_for['wind'] += row['PT']

print("\naccounted for:", accounted_for)

accounted_for_props = {k: round(v/281220.0, 4) for k,v in accounted_for.items()}

print("\nRequired proportions in gen mix:", res_mix)
print("\nAccounted for proportions:     ", accounted_for_props)
print("\nAccounted for total:", accounted_for)

cap_by_id = gen_data.groupby("ID")["PT"].sum().sort_values(ascending=False)

print(cap_by_id)