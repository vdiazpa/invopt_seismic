
import pandas as pd, sys, random
import pyomo.environ as pyo
from pyomo.environ import *
import matplotlib.pyplot as plt
import numpy as np
sys.path.insert(0, "C:\\Users\\vdiazpa\\mpi-sppy")

# Read the Data
gen_data  = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\RTS_data\\gen_data.csv", header=0)
bus_data  = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\RTS_data\\bus_data.csv", header=0)
line_data = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\RTS_data\\branch_data.csv", header=0)

# Sets and Parameters
all_nodes = bus_data["Bus ID"].unique()
gens = gen_data["GEN UID"]
lines = [(line_data["From Bus"][i], line_data["To Bus"][i]) for i in range(len(line_data["To Bus"]))]

# Create line-to-bus (incidence matrix) & Bus-to-unit (adjacency matrix) Maps
line_to_bus = pd.DataFrame(0, index=(range(len(lines))), columns=all_nodes)
bus_to_unit = pd.DataFrame(0, index=gens, columns=all_nodes)

for i in range(len(lines)):
    line_to_bus.iloc[i][lines[i][0]] = -1
    line_to_bus.iloc[i][lines[i][1]] = 1

for i in range(len(gens)):
    bus_to_unit.loc[(gen_data["GEN UID"][i], gen_data["Bus ID"][i])] = 1

#Create nodes q. load set and demand dict
nodes_load = []
nodes_noload = []
demand = {}

for i in range(len(all_nodes)):
    if bus_data["Bus Type"][i] == "PV" and bus_data["MW Load"][i] != 0:
        nodes_load.append(bus_data["Bus ID"][i])
        demand[bus_data["Bus ID"][i]] = bus_data["MW Load"][i]
    else:
        demand[bus_data["Bus ID"][i]] = 0
        nodes_noload.append(bus_data["Bus ID"][i])

#Create Generation Sets and Costs by Fuel Type
coal_gens, solar_gens, nuc_gens, oil_gens, steam_gens, wind_gens, other_gens, ng_gens, hydro_gens = [], [], [], [], [], [], [], [], []
gen_cost = {}

for i in range(len(gens)):
    if gen_data["Fuel"][i] == "Coal":
        coal_gens.append(gen_data["GEN UID"][i])
        gen_cost[gen_data["GEN UID"][i]] = gen_data["Fuel Price $/MMBTU"][i]
    elif gen_data["Fuel"][i] == "NG":
        ng_gens.append(gen_data["GEN UID"][i])
        gen_cost[gen_data["GEN UID"][i]] = gen_data["Fuel Price $/MMBTU"][i]
    elif gen_data["Fuel"][i] == "Solar":
        solar_gens.append(gen_data["GEN UID"][i])
        gen_cost[gen_data["GEN UID"][i]] = 0.1
    elif gen_data["Fuel"][i] == "Oil":
        oil_gens.append(gen_data["GEN UID"][i])
        gen_cost[gen_data["GEN UID"][i]] = gen_data["Fuel Price $/MMBTU"][i]
    elif gen_data["Fuel"][i] == "Hydro":
        hydro_gens.append(gen_data["GEN UID"][i])
        gen_cost[gen_data["GEN UID"][i]] = 0.1
    elif gen_data["Fuel"][i] == "Nuclear":
        nuc_gens.append(gen_data["GEN UID"][i])
        gen_cost[gen_data["GEN UID"][i]] = gen_data["Fuel Price $/MMBTU"][i]
    elif gen_data["Fuel"][i] == "Wind":
        wind_gens.append(gen_data["GEN UID"][i])
        gen_cost[gen_data["GEN UID"][i]] = 0.1
    else:
        other_gens.append(gen_data["GEN UID"][i])
        gen_cost[gen_data["GEN UID"][i]] = gen_data["Fuel Price $/MMBTU"][i]
# More Parameters for model inputs
lines_list     = [ str(lines[i][0]) + '_' + str(lines[i][1])       for i in range(len(lines)) ]
unit_capacity  = { gen_data['GEN UID'][i]: gen_data['PMax MW'][i]  for i in range(len(gens))  }
line_reactance = { lines_list[i] : line_data['X'][i]               for i in range(len(lines)) }
line_capacity  = { lines_list[i] : line_data['Cont Rating'][i]     for i in range(len(lines)) }
line_endpoints = { lines_list[i] : (lines[i][0], lines[i][1])      for i in range(len(lines)) }
ref_bus        = max(demand, key=demand.get)  # Reference bus has higheest load

# Dictionary to map direction of line respect to bus
line_to_bus_dict = {}
for idx, line in enumerate(line_to_bus.index):  
    for col in line_to_bus.columns:  
        line_to_bus_dict[(lines_list[idx], col)] = line_to_bus.loc[line, col]

# Dictionary to map nodes to lines adjacent & count number of lines adjacent to node
lines_adj = {}
bus_nlines_adj= {}
for col in line_to_bus.columns:
    lines_adj[col] = []
    bus_nlines_adj[col] = 0
    for idx, line in enumerate(line_to_bus.index):
        if line_to_bus.loc[line, col] != 0:
            bus_nlines_adj[col] +=1
            lines_adj[col].append(lines_list[idx])

# Dictionary to map units to buses
unit_to_bus_dict = {}  
gen_buses = []
for idx, unit in enumerate(bus_to_unit.index):  
    for col in bus_to_unit.columns:  
        if bus_to_unit.loc[unit, col] != 0:
            unit_to_bus_dict[unit] = col  
            if col not in gen_buses:
                gen_buses.append(col)

gen_data['num_conn'] = [ bus_nlines_adj[unit_to_bus_dict[gen]] for gen in gens ] # add column to gen dataframe with # of lines adjacent to gen bus

trans_nodes = set(all_nodes) - set(nodes_load) - set(gen_buses)


print("\nNumber of nodes with load:", len(nodes_load))
print("Number of Generators: ", len(gens))
print("Number of purely transmission nodes: ", len(trans_nodes), "\n")

# get critical generators
highly_conn_gens = gen_data.sort_values(by='num_conn', axis = 0, ascending = False)['GEN UID'].head(10).to_list()
crit_gens        = gen_data.sort_values(by='PMax MW',  axis = 0, ascending = False)['GEN UID'].head(5).to_list( )
for unit in highly_conn_gens:
    if unit not in crit_gens:
         crit_gens.append(unit)
    if len(crit_gens) == 10:
        break

# get critical transmission nodes
trans_nlines = { key: bus_nlines_adj[key] for key in trans_nodes if key in bus_nlines_adj }
max_nlines   = max(trans_nlines.values())
crit_trans   = []
for node in trans_nodes: 
    if trans_nlines[node] == max_nlines:
        crit_trans.append(node)
    if len(crit_trans) == 2:
        break

#get critical loads
bus_data['num_conn'] = bus_data['Bus ID'].map( bus_nlines_adj )

crit_loads   = []
new_bus_data = bus_data.sort_values(by = 'MW Load', axis = 0, ascending = False).reset_index(drop=True)
#new_bus_data.to_csv('new_bus_data.csv', header = True)
i = 1
while i < 4:
    for j in range(len(new_bus_data)):
        if new_bus_data.iloc[j]['num_conn'] ==i and new_bus_data.iloc[j]['Bus Type'] != 'PQ':
            crit_loads.append(new_bus_data.iloc[j]['Bus ID'])
        if len(crit_loads) == 5:
            break
    i+=1

print("\nNumber of Critical Loads: ", len(crit_loads))
print("Number of Critical Generators: ", len(crit_gens))
print("Number of Critical Transmission nodes: ", len(crit_trans), '\n')

#Resilience Parameter
tau = 0.2
print("Resilience parameter: ", tau)

def build_inv_opt(damage_state_gens, damage_state_trans, damage_state_loads, t):

    model = pyo.ConcreteModel()

    # Variables
    model.VoltAngle      = pyo.Var( all_nodes,  within = pyo.Reals,  bounds = (-180, 180) )
    model.PowerGenerated = pyo.Var( gens,       within = pyo.PositiveReals )
    model.LoadShedding   = pyo.Var( nodes_load, within = pyo.PositiveReals )
    model.Slack          = pyo.Var( nodes_load, within = pyo.PositiveReals )
    model.PowerFlow      = pyo.Var( lines_list, within = pyo.Reals )

    model.GenInvest      = pyo.Var( crit_gens,  within = pyo.Binary )
    model.DistSSInvest   = pyo.Var( crit_loads, within = pyo.Binary )
    model.TransInvest    = pyo.Var( crit_trans, within = pyo.Binary )

    # Constraints
    model.GenCap_Constraints  = pyo.ConstraintList()
    model.FlowUB_Constraints  = pyo.ConstraintList()
    model.FlowLB_Constraints  = pyo.ConstraintList()
    model.LShedLB_Constraints = pyo.ConstraintList()

    #Gen Capacity Constraint
    for g in gens: 
        if g in crit_gens: 
            model.GenCap_Constraints.add( expr = model.PowerGenerated[g] <= ( unit_capacity[g] * (1 - damage_state_gens[g]) ) + ( unit_capacity[g] * damage_state_gens[g] * model.GenInvest[g] )  )
        else: 
            model.GenCap_Constraints.add( expr = model.PowerGenerated[g] <=  unit_capacity[g] * (1 - damage_state_gens[g] ) )
        
    def FlowOnLine(model, l):
        return model.PowerFlow[l] * line_reactance[l] == model.VoltAngle[line_endpoints[l][0]] - model.VoltAngle[line_endpoints[l][1]]
    model.Flow_Contraint   = pyo.Constraint(lines_list, rule = FlowOnLine)

    model.RefBus_Constraint = pyo.Constraint(expr = model.VoltAngle[ref_bus] == 0)

    def NodalBalanceLoad(model, i):
        return  sum( model.PowerGenerated[g] * bus_to_unit[i][g] for g in gens ) +  sum( model.PowerFlow[l] * line_to_bus_dict[(l,i)] for l in lines_list ) + model.LoadShedding[i]  + model.Slack[i] >= demand[i]
    model.NodalBalLoad_Constraint = pyo.Constraint(nodes_load, rule = NodalBalanceLoad)

    def NodalBalanceNoLoad(model, i):
        return  sum( model.PowerGenerated[g] * bus_to_unit[i][g] for g in gens ) + sum( model.PowerFlow[l] * line_to_bus_dict[(l,i)] for l in lines_list ) == 0
    model.NodalBalNoLoad_Constraint = pyo.Constraint(nodes_noload, rule = NodalBalanceNoLoad)

    #Load Shedding Lower Bound
    for bus in nodes_load: 
        if bus in crit_loads: 
            model.LShedLB_Constraints.add( expr = model.LoadShedding[bus] >= demand[bus] * damage_state_loads[bus] * ( 1 - model.DistSSInvest[bus] ) )
        else: 
            model.LShedLB_Constraints.add( expr = model.LoadShedding[bus] >= demand[bus] * damage_state_loads[bus] )  

    def LoadShedUpperBound(model, i):
        return model.LoadShedding[i] <= demand[i]
    model.LoadShedUB_Constraint = pyo.Constraint(nodes_load, rule = LoadShedUpperBound)

    #Flow Upper Bound
    for bus in all_nodes: 
        if bus in crit_trans: 
            for line in lines_adj[bus]:
                model.FlowUB_Constraints.add( expr = model.PowerFlow[line] <= line_capacity[line] * (1 - damage_state_trans[bus] * (1 - model.TransInvest[bus])))
        elif bus in trans_nodes and bus not in crit_trans: 
            for line in lines_adj[bus]:
                model.FlowUB_Constraints.add( expr = model.PowerFlow[line] <= line_capacity[line] * (1 - damage_state_trans[bus]))
        else:
            for line in lines_adj[bus]:
                model.FlowUB_Constraints.add( expr = model.PowerFlow[line] <= line_capacity[line] )

    #Flow Lower Bound
    for bus in all_nodes: 
        if bus in crit_trans: 
            for line in lines_adj[bus]:
                model.FlowLB_Constraints.add( expr = model.PowerFlow[line] >= -1 * line_capacity[line] * ( 1 - damage_state_trans[bus] * (1 - model.TransInvest[bus])))
        elif bus in trans_nodes and bus not in crit_trans: 
            for line in lines_adj[bus]:
                model.FlowLB_Constraints.add( expr = model.PowerFlow[line] >= -1 * line_capacity[line] * ( 1 - damage_state_trans[bus]) )
        else:
            for line in lines_adj[bus]:
                model.FlowLB_Constraints.add( expr = model.PowerFlow[line] >= -1 * line_capacity[line] )

    #Resilience Constraint
    model.Resil_Constraint = pyo.Constraint(expr = sum(model.LoadShedding[i] for i in nodes_load) <= t * sum(demand[i] for i in nodes_load)) 

    def ObjectiveRule(model): 
        shedding_costs = sum( model.LoadShedding[i]/demand[i] + model.Slack[i]*5000 for i in nodes_load)  
        return sum( 10 * model.GenInvest[g] for g in crit_gens ) + sum( 40 * model.DistSSInvest[i] for i in crit_loads ) + sum( 20 * model.TransInvest[i] for i in crit_trans ) + shedding_costs
    model.ObjectiveVal  = pyo.Objective(rule = ObjectiveRule, sense = pyo.minimize)

    return model


# taus = np.linspace(0.2, 0.8, 15) # % of demand that must be met

import mpisppy.utils.sputils as sputils
import time

objvals = []
investment_costs = []
ds_loads, ds_trans, ds_gens = {}, {}, {}
num_scenarios = 100

def scenario_creator(scenario_name, **kwargs):

    num_scenarios = int(kwargs.get("num_scenarios", 1)) # recieve extras passed via kwargs

    random.seed(int(scenario_name))                     # Set random seed equal to scenario name

    # --- Build current scenario's damage states --- 
    damaged_loads = crit_loads.copy()
    damaged_loads.extend(random.sample(list(set(nodes_load) - set(crit_loads)), 1))
    ds_loads[scenario_name] = {node: int(node in damaged_loads) for node in nodes_load}

    damaged_trans = crit_trans.copy()
    damaged_trans.extend(random.sample(list(trans_nodes - set(crit_trans)), 1))
    ds_trans[scenario_name] = {node: int(node in damaged_trans) for node in list(trans_nodes)}

    damaged_gens = crit_gens.copy()
    damaged_gens.extend(random.sample(list(set(gens) - set(crit_gens)), 1))
    ds_gens[scenario_name] = {gen: int(gen in damaged_gens) for gen in gens}

    #---- Build Pyomo model for this scenario ---
    model = build_inv_opt(damage_state_gens  = ds_gens[scenario_name], damage_state_trans = ds_trans[scenario_name], damage_state_loads = ds_loads[scenario_name], t = tau)

    # ---- Attach Non-anticipativity info ---damage_state_loads = ds_loads[scenario_name]
    sputils.attach_root_node(model, model.ObjectiveVal, [model.GenInvest, model.DistSSInvest, model.TransInvest])
    model._mpisppy_probability = 1.0 / float(num_scenarios)
    model.write(f"test_{scenario_name}.lp", io_options={'symbolic_solver_labels': True})
    return model

from mpisppy.opt.ef import ExtensiveForm

options = {"solver": "gurobi"}
all_scenario_names = [str(i) for i in range(1, num_scenarios + 1)]
ef = ExtensiveForm(options, all_scenario_names, scenario_creator, scenario_creator_kwargs={"num_scenarios": num_scenarios})
start_time = time.time()
results = ef.solve_extensive_form(tee=True)
end_time = time.time()
print(f"Runtime: {end_time - start_time:.2f} seconds")

from pyomo.environ import value
objval = ef.get_objective_value()
print("Total Investment Cost")
print(f"{objval:.1f}")



# for tau in taus:
#     print(f"\nRunning for tau = {tau}")
#     objvals = []
#     for run in range(5):  # Run 5 times per tau
#         ds_loads, ds_trans, ds_gens = {}, {}, {}
#         for i in range(1, 6):
#             damaged_loads = crit_loads.copy()
#             damaged_loads.extend(random.sample(list(set(nodes_load) - set(crit_loads)), k = 2))
#             ds_loads[f'{i}'] = {node: int(node in damaged_loads) for node in nodes_load}

#             damaged_trans = crit_trans.copy()
#             damaged_trans.extend(random.sample(list(trans_nodes - set(crit_trans)), k = 2))
#             ds_trans[f'{i}'] = {node: int(node in damaged_trans) for node in list(trans_nodes)}

#             damaged_gens = crit_gens.copy()
#             damaged_gens.extend(random.sample(list(set(gens) - set(crit_gens)), k = 8))
#             ds_gens[f'{i}'] = {gen: int(gen in damaged_gens) for gen in gens}

#         import mpisppy.utils.sputils as sputils
#         import time

#         def scenario_creator(scenario_name):
#             for i in range(1, 6):
#                 scenario_name = f'{i}'
#                 damage_state_gens = ds_gens[scenario_name]
#                 damage_state_trans = ds_trans[scenario_name]
#                 damage_state_loads = ds_loads[scenario_name]
#             model = build_inv_opt(damage_state_gens, damage_state_trans, damage_state_loads, tau)
#             sputils.attach_root_node(model, model.ObjectiveVal, [model.GenInvest, model.DistSSInvest, model.TransInvest])
#             model._mpisppy_probability = 1.0 / 5.0
#             model.write(f"test_{scenario_name}.lp", io_options={'symbolic_solver_labels': True})
#             return model

#         from mpisppy.opt.ef import ExtensiveForm

#         options = {"solver": "gurobi"}
#         all_scenario_names = [str(i) for i in range(1, 6)]
#         ef = ExtensiveForm(options, all_scenario_names, scenario_creator)
#         start_time = time.time()
#         results = ef.solve_extensive_form(tee=True)
#         end_time = time.time()
#         print(f"Runtime: {end_time - start_time:.2f} seconds")

#         from pyomo.environ import value
#         objval = ef.get_objective_value()
#         print("Total Investment Cost")
#         print(f"{objval:.1f}")
#         objvals.append(objval)

#     avg_objval = sum(objvals) / len(objvals)
#     investment_costs.append(avg_objval)

# plt.figure()
# plt.plot([t * 100 for t in taus], investment_costs, marker='o')
# plt.xlabel('% of Demand That Must Be Met')
# plt.ylabel('Average Total Investment Cost')
# plt.title('Average Investment Cost vs. % Demand Met')
# plt.grid(True)
# plt.show()
