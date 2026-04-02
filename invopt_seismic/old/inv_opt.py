#inv_opt.py
from scenario_utils import scenario_generator, critical_assets_identifier
from data_extract import load_wecc_data_m, load_wecc_data_raw
from pyomo.environ  import *
import matplotlib.pyplot as plt
import pandas as pd, sys
import numpy as np
import time
sys.path.insert(0, "C:\\Users\\vdiazpa\\mpi-sppy")
import mpisppy.utils.sputils as sputils
from mpisppy.opt.ef import ExtensiveForm

# data = load_wecc_data_m(
#     gen_csv    = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\m-file-data\gen_data.csv",
#     bus_csv    = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\m-file-data\bus_data.csv",
#     branch_csv = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\m-file-data\branch_data.csv")

data = load_wecc_data_raw(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\gen_data_raw.csv", 
               r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\bus_data_raw.csv", 
               r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\branch_data_raw_with_rateA_m_all.csv", 
                load_csv = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\load_data_raw.csv" )

gens  = data['gens']
lines = data['lines']
demand  = data['demand']
ref_bus = data['ref_bus']
all_nodes   = data['all_nodes']
lines_adj   = data['lines_adj']
nodes_load  = data['nodes_load']
gens_by_bus = data['gens_by_bus']
trans_nodes = data['trans_nodes']
lines_by_bus   = data['lines_by_bus']
nlines_adj  = data['nlines_adj']
line_capacity  = data['line_capacity']
unit_capacity  = data['unit_capacity']
line_reactance = data['line_reactance']
hardening_cost = data['hardening_cost']
line_endpoints = data['line_endpoints']
line_to_bus_dict = data['line_to_bus_dict']
unit_to_bus_dict = data['unit_to_bus_dict']


def build_inv_opt(damage_state_gens, damage_state_trans, damage_state_loads, damage_state_branches, crit_gens, crit_loads, crit_trans, t):

    model = ConcreteModel()

    # ======================================== Variables

    model.VoltAngle      = Var( all_nodes,  within = Reals,  bounds = (-180, 180) )
    model.PowerGenerated = Var( gens,       within = PositiveReals )
    model.LoadShedding   = Var( nodes_load, within = PositiveReals, bounds = lambda model, i: (0, demand[i]) )
    model.Slack          = Var( nodes_load, within = PositiveReals )
    model.PowerFlow      = Var( lines,      within = Reals )
    model.GenInvest      = Var( crit_gens,  within = Binary )  # Investment decision for generation units
    model.DistSSInvest   = Var( crit_loads, within = Binary )  # Investment decision for distribution substations
    model.TransInvest    = Var( crit_trans, within = Binary )  # Investment decision for transmission substations

    # ======================================== Constraints
 
    def FlowOnLine(model, l):
        return model.PowerFlow[l] * line_reactance[l] == model.VoltAngle[line_endpoints[l][0]] - model.VoltAngle[line_endpoints[l][1]]
    model.Flow_Contraint   = Constraint(lines, rule = FlowOnLine)

    def nb_rule(m,b):
        thermal = sum(m.PowerGenerated[g] for g in gens_by_bus[b]) if b in gens_by_bus else 0.0
        flows   = sum(m.PowerFlow[l] * line_to_bus_dict[(l,b)] for l in lines_by_bus[b])
        shed    = m.LoadShedding[b] if b in nodes_load else 0.0
        return thermal + flows + shed == demand.get(b, 0.0)
    model.NodalBalance = Constraint(all_nodes, rule = nb_rule)

    model.RefBus_Constraint = Constraint(expr = model.VoltAngle[ref_bus] == 0)

    model.GenCap_Constraints  = ConstraintList()
    model.FlowUB_Constraints  = ConstraintList()
    model.FlowLB_Constraints  = ConstraintList()
    model.LShedLB_Constraints = ConstraintList()

    # ========== Gen Capacity Upper Bound
    for g in gens: 
        if g in crit_gens: 
            model.GenCap_Constraints.add( 
                expr = model.PowerGenerated[g] <= ( unit_capacity[g] * (1 - damage_state_gens[g]) ) + ( unit_capacity[g] * damage_state_gens[g] * model.GenInvest[g] )  )
        else: 
            model.GenCap_Constraints.add( 
                expr = model.PowerGenerated[g] <= unit_capacity[g] * (1 - damage_state_gens[g] ) )

    # ========== Load Shedding Lower Bound
    for bus in nodes_load: 
        if bus in crit_loads: 
            model.LShedLB_Constraints.add( expr = model.LoadShedding[bus] >= demand[bus] * damage_state_loads[bus] * ( 1 - model.DistSSInvest[bus] ) )
        else: 
            model.LShedLB_Constraints.add( expr = model.LoadShedding[bus] >= demand[bus] * damage_state_loads[bus] )  

    # ========== Flow Upper Bound
    for bus in all_nodes: 
        if bus in crit_trans: 
            for line in lines_adj[bus]:
                model.FlowUB_Constraints.add( expr = model.PowerFlow[line] <= line_capacity[line]*( 1-damage_state_branches[line]) * ( (1-damage_state_trans[bus]) + damage_state_trans[bus]*model.TransInvest[bus] ))
        elif bus in trans_nodes and bus not in crit_trans: 
            for line in lines_adj[bus]:
                model.FlowUB_Constraints.add( expr = model.PowerFlow[line] <= line_capacity[line] * ( 1-damage_state_branches[line]) * (1 - damage_state_trans[bus]))
        else:
            for line in lines_adj[bus]:
                model.FlowUB_Constraints.add( expr = model.PowerFlow[line] <= line_capacity[line] )

    # ========== Flow Lower Bound
    for bus in all_nodes: 
        if bus in crit_trans: 
            for line in lines_adj[bus]:
                model.FlowLB_Constraints.add( expr = model.PowerFlow[line] >= -1 * line_capacity[line]*( 1-damage_state_branches[line]) * ( (1-damage_state_trans[bus]) + damage_state_trans[bus]*model.TransInvest[bus] ))
        elif bus in trans_nodes and bus not in crit_trans: 
            for line in lines_adj[bus]:
                model.FlowLB_Constraints.add( expr = model.PowerFlow[line] >= -1 * line_capacity[line] * ( 1-damage_state_branches[line]) * ( 1 - damage_state_trans[bus]) )
        else:
            for line in lines_adj[bus]:
                model.FlowLB_Constraints.add( expr = model.PowerFlow[line] >= -1 * line_capacity[line] )

    # ========== Resilience Constraint
    model.Resil_Constraint = Constraint(expr = sum(model.LoadShedding[i] for i in nodes_load) <= t * sum(demand[i] for i in nodes_load)) 
    
    # ======================================== Objective Function

    def invest_cost_rule(m):      # Per-scenario Invest Cost
        return (10*(sum(hard_frac * hardening_cost[unit_to_bus_dict[g]] * m.GenInvest[g]    for g in crit_gens) +
                    sum(hard_frac * hardening_cost[i]                   * m.DistSSInvest[i] for i in crit_loads) +
                    sum(hard_frac * hardening_cost[i]                   * m.TransInvest[i]  for i in crit_trans)))
    
    def total_shed_cost_rule(m):  #Per-scenario Load Shedding Cost
        return sum(m.LoadShedding[i]*1.0 for i in nodes_load)
    
    model.ShedCost   = Expression(rule=total_shed_cost_rule)
    model.InvestCost = Expression(rule=invest_cost_rule)

    def ObjectiveRule(model): 
        return  model.ShedCost + model.InvestCost
    model.ObjectiveVal  = Objective(rule = ObjectiveRule, sense = minimize)

    # LS Computation
    def total_shed_rule(m): 
        return sum(m.LoadShedding[i] for i in nodes_load)
    model.TotalShed  = Expression(rule=total_shed_rule)

    return model
                                                                                                                                                                
                                                                            
###################################################################################################################################################################
#                                                                                                            ## Create Earthquake Scenarios & Id critical assets ##
###################################################################################################################################################################

def scenario_creator(scenario_name, **kwargs):
    
    sname = str(scenario_name)

    model = build_inv_opt(
        damage_state_gens=ds_gens[sname], damage_state_trans=ds_trans[sname], damage_state_loads=ds_loads[sname], damage_state_branches=ds_branch[sname], 
        crit_gens=crit_gens, crit_loads=crit_loads, crit_trans = crit_trans, t=tau)

    num_scenarios = int(kwargs.get("num_scenarios", 1))

    form = kwargs.get("form", "risk_neutral")

    if form in ("risk_neutral", "cvar_constr", "cvar_obj"):
        model.del_component(model.Resil_Constraint)

    sputils.attach_root_node(model, model.ObjectiveVal, [model.GenInvest, model.DistSSInvest, model.TransInvest]) # ---- Attach Non-anticipativity info ---
    model._mpisppy_probability = 1.0 / float(num_scenarios)

    return model

##################################################################################################################################################################
#                                                                                                                                           ## Build SP & Solve ##
##################################################################################################################################################################

def model_build_solve(form:str, time_solve = False, tee = False, print_vars = False):

    options = {"solver": "gurobi"}
    all_scenario_names = [str(i) for i in range(0, num_scenarios)]
    ef = ExtensiveForm(options, all_scenario_names, scenario_creator, scenario_creator_kwargs={"num_scenarios": num_scenarios, "form": form})
    ef_model = ef.ef

    if form == "hard_resil":
        print("Resilience parameter: ", tau)

    if form =='cvar_obj':                                                  # ---- Modify Objective to include CVaR term                         
        lam = 1.0                                                          # weight of Cvar in objecive
        ef_model.eta = Var(within=NonNegativeReals)                        # cVar Approximation
        ef_model.xi  = Var(all_scenario_names, within=NonNegativeReals)    # Per scenario auxiliary variable

        def cvar_link_rule(m, sname): 
            scen = ef.local_scenarios[sname]
            return m.xi[sname] >= scen.TotalShed - m.eta
        ef_model.Cvar_linking_Constraint = Constraint(all_scenario_names, rule=cvar_link_rule)

        def CVar_expr_rule(m):
            return m.eta + (1.0 /( (1.0 - alpha)*num_scenarios)) * sum( m.xi[sname] for sname in all_scenario_names)   # Expression for CVaR Value
        ef_model.Cvar = Expression(rule = CVar_expr_rule)

        base_obj_expr = ef_model.EF_Obj.expr
        ef_model.del_component(ef_model.EF_Obj)
        
        def EF_Objective_CVar_rule(m):
            return base_obj_expr + lam * m.Cvar
        
        ef_model.EF_Obj = Objective(rule=EF_Objective_CVar_rule, sense=minimize)

    #ef_model.write(f"SP_{form}.lp", io_options={"symbolic_solver_labels": True})

    # -------- Solve 
    start_time = time.time()
    results    = ef.solve_extensive_form(solver_options = {"MIPGap":0.05}, tee=tee)
    end_time   = time.time()
    if time_solve: 
        print(f"Runtime: {end_time - start_time:.2f} seconds")

    if form == "cvar_obj":               # Print CVaR Value
        eta_val  = value(ef_model.eta)
        xi_sum   = sum(value(ef_model.xi[s]) for s in all_scenario_names)
        cvar_val = eta_val + (1.0 /( (1.0 - alpha)*num_scenarios)) * xi_sum
        print(f"Computed CVaR (MW): {cvar_val}")

    # ---------- Compute CVaR from solution
    all_scenario_names = [str(i) for i in range(num_scenarios)]

    # 1) Take InvestCost from every scenario 
    some_scen = ef.local_scenarios[all_scenario_names[0]]
    inv_cost = value(some_scen.InvestCost)

    # 2) Compute expected load shedding
    shed_vals = []
    for s in all_scenario_names:
        scen = ef.local_scenarios[s]
        shed_vals.append(value(scen.TotalShed))

    prob = 1.0 / num_scenarios
    expected_LS = prob * sum(shed_vals)

    # 3) Compute CVaR from results
    N = len(shed_vals)
    sorted_shed = sorted(shed_vals)
    k = int((1 - alpha) * N)  # number of tail scenarios
    tail = sorted_shed[-k:] if k > 0 else []
    true_cvar = sum(tail) / len(tail) if tail else 0.0

    print(f"\nInvestment cost: {inv_cost:.2f}")
    print(f"Expected load shed: {expected_LS:.2f}")
    print(f"Total EF objective: {value(ef_model.EF_Obj):.2f}")
    print(f"True CVaR from {form} formulation solution:", round(true_cvar,2) )

    #Save Run Results
    variables   = ef.gather_var_values_to_rank0()
    invest_vars = ["GenInvest", "DistSSInvest", "TransInvest"]

    gen_inv, load_inv, trans_inv = {}, {}, {}

    import re

    for ((_, var_name), var_value) in variables.items():
        if var_name.startswith("GenInvest["):
            s = re.search(r"\[(.*?)\]", var_name)
            if not s:
                continue
            idx = s.group(1).strip().strip("'\"")
            gen_inv[idx] = round(var_value)
        elif var_name.startswith("DistSSInvest"):
            s = re.search(r"\[(.*?)\]", var_name)
            if not s:
                continue
            idx = s.group(1).strip().strip("'\"")
            load_inv[idx] = round(var_value)
        elif var_name.startswith("TransInvest"):
            s = re.search(r"\[(.*?)\]", var_name)
            if not s:
                continue
            idx = s.group(1).strip().strip("'\"")  
            trans_inv[idx] = round(var_value)
    # print(gen_inv, load_inv, trans_inv)

    #Print Investment Decisions
    if print_vars: 
        print("\nInvestment Decisions:")
        printed = set()
        for ((_, var_name), var_value) in variables.items():
            if any((var_name.startswith(v) for v in invest_vars)):
                if var_name not in printed and var_value > 0.5:
                    print(f"{var_name} = {var_value}")
                    printed.add(var_name)
        print("\n")

    return { "form": form,
             "inv_cost": inv_cost,  
             "expected_shed": expected_LS,
             "cvar": true_cvar,
             "gen_inv": gen_inv,
             "load_inv": load_inv,
             "trans_inv": trans_inv, 
             "shed_vals": shed_vals}

##################################################################################################################################################################
#                                                                                                                                             ## Main Execution ##
##################################################################################################################################################################
print("\nThis was my last run")
num_scenarios = 500  # Number of earthquake scenarios to consider
hard_frac = 0.5     # Percent of substation capital cost to consider as hardening cost
seed  = 42          # Random seed for scenario generation and critical asset identification
alpha = 0.95         # For 'cvar_constr' formulation: 1-alpha confidence level for CVaR
tau   = 0.1         # For 'hard_resil' formulation: Resilience parameter; percent of total load that must be served after earthquake realization

ds_gens, ds_loads, ds_trans, ds_branch = scenario_generator( 
    mode='random', num_scenarios=num_scenarios, gens=gens, nodes_load=nodes_load, trans_nodes=trans_nodes, lines=lines, frac_gens=0.15, frac_loads=0.15, frac_trans=0.15, seed=seed)

crit_gens, crit_loads, crit_trans = critical_assets_identifier(
    mode = "from_damaged", 
    num_scenarios = num_scenarios, 
    gens=gens, nodes_load=nodes_load, trans_nodes=trans_nodes, 
    ds_gens=ds_gens, ds_loads=ds_loads, ds_trans=ds_trans,
    frac_gens=0.05, frac_loads=0.05, frac_trans=0.05, 
    plot = True)
                                                               
# res_hr   = model_build_solve(form ="hard_resil", tee = False, print_vars = True)      #Formulations: "risk_neutral", "hard_resil", "cvar_obj"
res_rn   = model_build_solve(form ="risk_neutral", time_solve = True, tee = True, print_vars = True)
res_cvar = model_build_solve(form ="cvar_obj", time_solve = True, tee = True, print_vars = True)
#res_hr   = model_build_solve(form ="hard_resil", time_solve = True, tee = True, print_vars = True)
