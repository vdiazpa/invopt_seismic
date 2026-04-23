#gen_types.py

import pandas as pd

res_mix = { "biomass":     round(float(  1841/290961), 4),
            "coal":        round(float( 44596/290961), 4),
            "geo-thermal": round(float(  4238/290961), 4),
            "gas":         round(float( 108628/290961), 4),
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

#Create column in gen_data with type based on ID. Note: some IDs have multiple types (e.g. 'S' is utility PV but could also be small-scale PV), so this is an approximation to get a sense of the mix of generation types in the data.
gen_data["type"] = gen_data["ID"].apply(lambda x:
    "coal" if x in ['C'] else
    "biomass" if x in ['B', 'NB', 'R'] else
    "gas" if x in ['SG', 'G', 'NG', 'CG', 'EG', 'DG', 'TG', 'RG', 'WG', 'MG'] else
    "utility_pv" if x=='S' else
    "geo-thermal" if x in ['E', 'NE' , 'CE'] else
    "nuclear" if x in ['N', 'NN'] else
    "hydro" if x in ['H', 'NH', 'SH'] else
    "pumped_sto" if x in ['P', 'NP'] else
    "wind" if x in ['W', 'NW', 'SW'] else
    "DPV" if x in ['DPV'] else
    "other")

print(gen_data[["ID", "type"]].head(20))

print("\nGeneration data with types:\n", gen_data.head(), '\n')

for i, row in gen_data.iterrows():
    if  row['ID'] in ['C'] :
        accounted_for['coal'] += row['PT']
    elif row['ID'] in ['B', 'NB']:
        accounted_for['biomass'] += row['PT']
    elif row['ID'] in ['SG', 'G', 'NG', 'CG', 'EG', 'DG', 'TG', 'RG', 'WG', 'MG'] :
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

print("\nRequired proportions in gen mix:", res_mix)
print("\nAccounted for total:", accounted_for, '\n')

#total generation by raw gen file column 'ID' (type)
cap_by_id = gen_data.groupby("ID")["PT"].sum().sort_values(ascending=False)
#print(cap_by_id)

cap_costs = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\capital_costs_atb.csv", header=0)

capex_technologies = cap_costs['display_name'].unique()

#print(cap_costs[['display_name', 'value']])
print(cap_costs[cap_costs['technology'] == 'Hydropower'].median()['value'])

capex_by_type = { 
    "coal": cap_costs[cap_costs['technology'] == 'Coal_FE'].median()['value'],
    "biomass": cap_costs[cap_costs['technology'] == 'Biopower'].median()['value'],
    "geo-thermal": cap_costs[cap_costs['technology'] == 'Geothermal'].median()['value'],
    "gas": cap_costs[cap_costs['technology'] == 'NaturalGas_FE'].median()['value'],
    "hydro": cap_costs[cap_costs['technology'] == 'Hydropower'].median()['value'],
    "nuclear": cap_costs[cap_costs['technology'] == 'Nuclear'].median()['value'],
    "pumped_sto": cap_costs[cap_costs['technology'] == 'Pumped Storage Hydropower'].median()['value'],
    "utility_pv": cap_costs[cap_costs['technology'] == 'UtilityPV'].median()['value'],
    "wind": cap_costs[cap_costs['technology'] == 'LandbasedWind'].median()['value'], 
}

print(capex_by_type)
gen_data["capex"] = gen_data["type"].apply(lambda x: capex_by_type[x] if x in capex_by_type else 500000)

print(gen_data.head())

gen_data.to_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\gen_data_with_types.csv", index=False)