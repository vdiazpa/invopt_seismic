import pandas as pd, sys, random
import pyomo.environ as pyo
import matplotlib.pyplot as plt
from pyomo.environ import *
sys.path.insert(0, "C:\\Users\\vdiazpa\\mpi-sppy")

gen_data    = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\duke_data\\data_genparams_partial.csv", header=0)
line_data   = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\duke_data\\line_params_new.csv", header=0)
linetobus   = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\duke_data\\line_to_bus.csv", header=0)
bus_to_unit = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\duke_data\\gen_mat.csv", header=0)
bus_to_unit.set_index("name", inplace=True)
load_df     = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\duke_data\\data_load_cut.csv", header=0)
solar_df    = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\duke_data\\data_solar_2023.csv", header=0)
nuclear_df  = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\duke_data\\data_nuc.csv", header=0)
hydro_df    = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\duke_data\\data_hydro_H.csv", header=0)

#Sets & Parameters
all_nodes    = list(linetobus.columns[1:])
gens         = gen_data["name"].tolist()
line_to_bus  = linetobus.iloc[:, 1:]
lines_list   = linetobus["line"].to_list()
nodes_load   = list(load_df.columns)
nodes_noload = [n for n in all_nodes if n not in nodes_load]

line_reactance = dict(zip(line_data["line"], line_data["reactance"]))
lines = [("n_" + l.split("_")[1], "n_" + l.split("_")[3]) for l in lines_list]
line_capacity = {line_data["line"][i]: line_data["limit"][i] for i in range(len(lines))}

demand  = {col: load_df[col][27] if col in load_df.columns else 0 for col in all_nodes}
ref_bus = max(demand, key=(demand.get))

line_endpoints = {lines_list[i]: (lines[i][0], lines[i][1]) for i in range(len(lines))}
unit_capacity = {gen_data["name"][i]: gen_data["maxcap"][i] for i in range(len(gens))}
unit_capacity = {}
gen_cost = {}
for index, row in gen_data.iterrows():
    if row["typ"] == "coal":
        unit_capacity[row["name"]] = row["maxcap"]
        cost = row["heat_rate"] * 1.5 + row["var_om"]
    elif row["typ"] == "oil":
        cost = row["heat_rate"] * 10 + row["var_om"]
        unit_capacity[row["name"]] = row["maxcap"]
    elif row["typ"] in ('ngct', 'ngcc'):
        cost = row["heat_rate"] * 3.4 + row["var_om"]
        unit_capacity[row["name"]] = row["maxcap"]
    elif row["typ"] == "nuc":
        cost = 0.1
        unit_capacity[row["name"]] = nuclear_df[row["name"]][27]
    elif row["typ"] == "hydro":
        unit_capacity[row["name"]] = hydro_df[row["name"]][27]
        cost = 0.5
    else:
        unit_capacity[row["name"]] = solar_df[row["name"]][27]
        cost = 0.5
    gen_cost[row["name"]] = cost

line_to_bus.rename(index={i: lines_list[i] for i in range(len(lines_list))}, inplace=True)
line_to_bus_dict = {(lid, b): line_to_bus.loc[lid, b] for lid in lines_list for b in all_nodes if line_to_bus.loc[lid, b] != 0}

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

for gen in gens:
    if gen not in unit_to_bus_dict:
        print("Missing key in unit_to_bus_dict:", gen)

gen_data["num_conn"] = [bus_nlines_adj[unit_to_bus_dict[gen]] for gen in gens]

trans_nodes = set(all_nodes) - set(nodes_load) - set(gen_buses)

print("\nNumber of nodes with load:", len(nodes_load))
print("Number of Generators: ", len(gens))
print("Number of purely transmission nodes: ", len(trans_nodes), "\n")

###############################################################################################################################################################################
##                                                                                                                                                                           ##
##                                                              * ! IDENTIFY CRITICAL ASSETS ! *                                                                             ##
##                                                                                                                                                                           ##
###############################################################################################################################################################################
crit_gens           = gen_data.sort_values(by="maxcap", axis=0, ascending=False)["name"].head(100).to_list()
trans_nlines        = {key: bus_nlines_adj[key] for key in trans_nodes if key in bus_nlines_adj}
crit_trans          = sorted(trans_nodes, key=(lambda n: bus_nlines_adj[n]), reverse=True)[:3]
sorted_nodes_by_load= sorted(demand, key=(lambda n: demand[n]), reverse=True)
top_load_nodes      = sorted_nodes_by_load[:100]
crit_loads          = sorted(top_load_nodes, key=(lambda n: bus_nlines_adj[n]))

print("Number of Critical Loads: ", len(crit_loads), "\nNumber of Critical Generators: ", len(crit_gens), "\nNumber of Critical Transmission nodes: ", len(crit_trans), "\n")
##############################################################################################################################################################################

tau = 0.5
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

    def NodalBalance1(model, i):
        return  sum( model.PowerGenerated[g] * bus_to_unit[i][g] for g in gens ) +  sum( model.PowerFlow[l] * line_to_bus.loc[l][i] for l in lines_list ) + model.LoadShedding[i] == demand[i]
    model.NodalBalLoad_Constraint = pyo.Constraint(nodes_load, rule = NodalBalance1)

    def NodalBalance2(model, i):
        return  sum( model.PowerGenerated[g] * bus_to_unit[i][g] for g in gens ) + sum( model.PowerFlow[l] * line_to_bus.loc[l][i] for l in lines_list ) == 0
    model.NodalBalNoLoad_Constraint = pyo.Constraint(nodes_noload, rule = NodalBalance2)

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
    model.Resil_Constraint = pyo.Constraint(expr = sum(model.LoadShedding[i] - model.Slack[i] for i in nodes_load) <=  t * sum(demand[i] for i in nodes_load)) 

    def ObjectiveRule(model): 
        shedding_costs = sum( model.LoadShedding[i]/demand[i] + model.Slack[i]*5000 for i in nodes_load)  
        return sum(10*model.GenInvest[g] for g in crit_gens) + sum(30*model.DistSSInvest[i] for i in crit_loads) + sum(20*model.TransInvest[i] for i in crit_trans) + shedding_costs
    model.ObjectiveVal  = pyo.Objective(rule = ObjectiveRule, sense = pyo.minimize)

    return model

from mpisppy.opt.ef import ExtensiveForm
import mpisppy.utils.sputils as sputils
import time

ds_loads, ds_trans, ds_gens = {}, {}, {}
num_scenarios = 50

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
    #model.write(f"test_{scenario_name}.lp", io_options={'symbolic_solver_labels': True})
    return model

start_time = time.time()

options = {"solver": "gurobi"}
all_scenario_names = [str(i) for i in range(1, num_scenarios)]
ef = ExtensiveForm(options, all_scenario_names, scenario_creator)
mid_time = time.time()
print(f"Time to build model is: {mid_time - start_time:.2f} seconds")
results = ef.solve_extensive_form(tee=True)
end_time = time.time()
print(f"Runtime: {end_time - mid_time:.2f} seconds")

from pyomo.environ import value
objval = ef.get_objective_value()
print("Total Investment Cost")
print(f"{objval:.1f}")

# from pyomo.environ import value
# variables = ef.gather_var_values_to_rank0()
# invest_vars = ["GenInvest", "DistSSInvest", "TransInvest"]
# printed = set()
# for ((scen_name, var_name), var_value) in variables.items():
#     if any((var_name.startswith(v) for v in invest_vars)):
#         if var_name not in printed:
#             print(f"{var_name} = {var_value}")
#             printed.add(var_name)
#         objval = ef.get_objective_value()
#         print("Total Investment Cost")
#         print((f"{objval:.1f}"))
