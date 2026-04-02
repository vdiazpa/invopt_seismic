import pandas as pd, sys
import pyomo.environ as pyo
from pyomo.environ import *
import numpy as np
import csv

# Read the Data
gen_data  = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\m-file-data\gen_data.csv", header=0)
bus_data  = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\m-file-data\bus_data.csv", header=0)
line_data = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\m-file-data\branch_data.csv", header=0)

# Make sure bus IDs are int
gen_data['bus'] = gen_data['bus'].apply(lambda x: int(x))  #make bus ID int in DataFrame
bus_data['bus_i'] = bus_data["bus_i"].apply(lambda x: int(x))  #make bus ID int in DataFrame

# Sets and Parameters
all_nodes = bus_data["bus_i"]
fuel_type = list(set([str(x) for x in gen_data["fuel_type"]]))

# Add gen  & branch name
gen_data['GEN UID']  = ['' for _ in range(len(gen_data))]
line_data['circuit'] = line_data.groupby(['fbus', 'tbus']).cumcount() # Created a unique ID for parallel lines
line_data['line_id'] = (line_data['fbus'].astype(str) + '_' + line_data['tbus'].astype(str) + '_' + line_data['circuit'].astype(str) )

k = 902 - 574 + 1
line_data  = line_data.iloc[:k]                           # Only first 329 entries are lines, rest are transformers

counts = { (b, t): 1 for b in all_nodes for t in fuel_type }
for g in range(len(gen_data)):
    gen_name = ''
    bus  = int(gen_data.at[g, 'bus'])
    type = str(gen_data.at[g, 'fuel_type'])
    gen_name = str(bus) + '_' + str(type) + '_' + str(counts[(bus, type)])
    counts[(bus, type)] += 1
    gen_data.at[g, 'GEN UID'] = gen_name

gens  = gen_data["GEN UID"]
lines = line_data['line_id'].tolist()

# # More Parameters for model inputs
line_endpoints = dict(zip(line_data['line_id'], zip(line_data['fbus'], line_data['tbus'])))
line_reactance = dict(zip(line_data['line_id'], line_data['x'].astype(float)))
line_capacity  = dict(zip(line_data['line_id'], line_data['rateA'].astype(float)))
lines_list     = [ str(lines[i][0]) + '_' + str(lines[i][1])       for i in range(len(lines)) ]
unit_capacity  = { gen_data['GEN UID'][i]: gen_data['Pmax'][i]     for i in range(len(gens))  }

# Create line-to-bus (incidence matrix) & Bus-to-unit (adjacency matrix) Maps
line_to_bus = pd.DataFrame(0, index=lines, columns=all_nodes, dtype = int)
bus_to_unit = pd.DataFrame(0, index=gens , columns=all_nodes, dtype = int)

for lid, (i,j) in line_endpoints.items():
    line_to_bus.loc[lid, i] = -1
    line_to_bus.loc[lid, j] =  1

for i in range(len(gens)):
    bus_to_unit.loc[(gen_data["GEN UID"][i], gen_data["bus"][i])] = 1

#line_to_bus.to_csv("linetobus_WECC.csv", header=1)

#Create nodes with load set and demand dict
nodes_load = []
nodes_noload = []
demand = {}
for i in range(len(all_nodes)):
    if bus_data["type"][i] == 1.0 and bus_data["Pd"][i] != 0:
        nodes_load.append(bus_data["bus_i"][i])
        demand[bus_data["bus_i"][i]] = abs(bus_data["Pd"][i])

    else:
        demand[bus_data["bus_i"][i]] = 0
        nodes_noload.append(bus_data["bus_i"][i])
ref_bus = max(demand, key=demand.get)  # Reference bus has higheest load

#Create Generation Sets and Costs by Fuel Type
coal_gens, solar_gens, nuc_gens, oil_gens, steam_gens, wind_gens, other_gens, ng_gens, hydro_gens = [], [], [], [], [], [], [], [], []
gen_cost = {}

# for i in range(len(gens)):
#     if gen_data["Fuel"][i] == "Coal":
#         coal_gens.append(gen_data["GEN UID"][i])
#         gen_cost[gen_data["GEN UID"][i]] = gen_data["Fuel Price $/MMBTU"][i]
#     elif gen_data["Fuel"][i] == "NG":
#         ng_gens.append(gen_data["GEN UID"][i])
#         gen_cost[gen_data["GEN UID"][i]] = gen_data["Fuel Price $/MMBTU"][i]
#     elif gen_data["Fuel"][i] == "Solar":
#         solar_gens.append(gen_data["GEN UID"][i])
#         gen_cost[gen_data["GEN UID"][i]] = 0.1
#     elif gen_data["Fuel"][i] == "Oil":
#         oil_gens.append(gen_data["GEN UID"][i])
#         gen_cost[gen_data["GEN UID"][i]] = gen_data["Fuel Price $/MMBTU"][i]
#     elif gen_data["Fuel"][i] == "Hydro":
#         hydro_gens.append(gen_data["GEN UID"][i])
#         gen_cost[gen_data["GEN UID"][i]] = 0.1
#     elif gen_data["Fuel"][i] == "Nuclear":
#         nuc_gens.append(gen_data["GEN UID"][i])
#         gen_cost[gen_data["GEN UID"][i]] = gen_data["Fuel Price $/MMBTU"][i]
#     elif gen_data["Fuel"][i] == "Wind":
#         wind_gens.append(gen_data["GEN UID"][i])
#         gen_cost[gen_data["GEN UID"][i]] = 0.1
#     else:
#         other_gens.append(gen_data["GEN UID"][i])
#         gen_cost[gen_data["GEN UID"][i]] = gen_data["Fuel Price $/MMBTU"][i]


# Dictionary to map direction of line respect to bus
line_to_bus_dict = {(lid, b): line_to_bus.loc[lid, b] for lid in lines for b in all_nodes if line_to_bus.loc[lid, b] != 0}

def build_DCOPF():
    model = pyo.ConcreteModel()
     
    model.VoltAngle      = pyo.Var(all_nodes,  within=(pyo.Reals), bounds=(-180, 180))
    model.PowerGenerated = pyo.Var(gens,       within=(pyo.PositiveReals))
    model.LoadShedding   = pyo.Var(nodes_load, within=(pyo.PositiveReals))
    model.PowerFlow      = pyo.Var(lines     , within=(pyo.Reals))

    def UnitCapacity(model, g):
        return model.PowerGenerated[g] <= unit_capacity[g]
    model.UnitCap_Constraint = pyo.Constraint(gens, rule=UnitCapacity)

    def FlowOnLine(model, l):
        return model.PowerFlow[l] * line_reactance[l] == model.VoltAngle[line_endpoints[l][0]] - model.VoltAngle[line_endpoints[l][1]]
    model.Flow_Contraint = pyo.Constraint(lines, rule=FlowOnLine)

    def PowerFlow_UpperBound(model, l):
        return model.PowerFlow[l] <= line_capacity[l]
    model.PowerFlowUB_Constraint = pyo.Constraint(lines, rule=PowerFlow_UpperBound)

    def PowerFlow_LowerBound(model, l):
        return model.PowerFlow[l] >= -1 * line_capacity[l]
    model.PowerFlowLB_Constraint = pyo.Constraint(lines, rule=PowerFlow_LowerBound)

    def NodalBalanceLoad(model, i):
        return sum(model.PowerGenerated[g] * bus_to_unit[i][g] for g in gens) + sum(model.PowerFlow[l] * line_to_bus.loc[l][i] for l in lines) + model.LoadShedding[i] >= demand[i]
    model.NodalBalLoad_Constraint = pyo.Constraint(nodes_load, rule=NodalBalanceLoad)

    def NodalBalanceNoLoad(model, i):
        return sum((model.PowerGenerated[g] * bus_to_unit[i][g] for g in gens)) + sum(model.PowerFlow[l] * line_to_bus.loc[l][i] for l in lines) == 0
    model.NodalBalNoLoad_Constraint = pyo.Constraint(nodes_noload, rule=NodalBalanceNoLoad)

    def LoadShedUpperBound(model, i):
        return model.LoadShedding[i] <= demand[i]
    model.LoadShedUB_Constraint = pyo.Constraint(nodes_load, rule=LoadShedUpperBound)

    def ObjectiveRule(model):
        return sum((5000 * model.LoadShedding[i] for i in nodes_load)) #+ sum((model.PowerGenerated[g] * gen_cost[g] for g in gens)) 

    model.ObjectiveVal = pyo.Objective(rule=ObjectiveRule, sense=(pyo.minimize))

    model.write("model.lp", io_options={"symbolic_solver_labels": True})

    # for i in nodes_load:
    #     model.LoadShedding[i].fix(float(demand[i]))
    # for g in gens:
    #     model.PowerGenerated[g].fix(0.0)
    # for l in lines:
    #     model.PowerFlow[l].fix(0.0)
    # for n in all_nodes:
    #     model.VoltAngle[n].fix(0.0)

    #Solve
    opt = SolverFactory("gurobi")
    results = opt.solve(model, tee=True)
    print((f"{pyo.value(model.ObjectiveVal):.1f}"))

    # #Save Results
    # results_obj = pd.DataFrame()
    # for v in model.component_objects(Var, active=True):
    #     for index in v:
    #         results_obj.at[(index, v.name)] = value(v[index])

    # results_obj.to_csv("DCOPF_results.csv", header=True)
    # return model


x = build_DCOPF()
