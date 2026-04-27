#inv_opt.py
from ..data_utils.structures import GridData, DamageData, CriticalAssets
from ..scenarios.stats import compute_islanded_undamaged_map
from mpisppy.opt.ef import ExtensiveForm
import mpisppy.utils.sputils as sputils
from pyomo.environ  import *
import pandas as pd, sys
import time
import re
sys.path.insert(0, "C:\\Users\\vdiazpa\\mpi-sppy")

def build_inv_opt(
        grid: GridData, 
        damage_states: DamageData, 
        critical_assets: CriticalAssets, 
        hard_frac:float = 0.5, 
        max_invest = None, 
        add_DG = False, 
        DGcap = 0.0,
        add_trans_fail = False,
        islanded_map = None):

    model = ConcreteModel()

    # ======================================== Sets/Maps/Params

    gens  = grid.gens
    lines = grid.lines
    demand  = grid.demand
    ref_bus = grid.ref_bus
    all_nodes   = grid.all_nodes
    lines_adj   = grid.lines_adj
    nodes_load  = grid.nodes_load
    gens_by_bus = grid.gens_by_bus
    trans_nodes = grid.trans_nodes
    lines_by_bus   = grid.lines_by_bus
    line_capacity  = grid.line_capacity
    unit_capacity  = grid.unit_capacity
    line_reactance = grid.line_reactance
    hardening_cost = grid.hardening_cost
    line_endpoints = grid.line_endpoints
    line_to_bus_dict = grid.line_to_bus_dict
    unit_to_bus_dict = grid.unit_to_bus_dict

    # ======================================== Vars

    model.VoltAngle      = Var( all_nodes,  within = Reals,  bounds = (-180, 180) )
    model.PowerGenerated = Var( gens,       within = NonNegativeReals)
    model.LoadShedding   = Var( nodes_load, within = NonNegativeReals, bounds = lambda model, i: (0, demand[i]) )
    model.PowerFlow      = Var( lines,      within = Reals )
    model.GenInvest      = Var( critical_assets.gens,  within = Binary )  # Investment decision for generation units
    model.DistSSInvest   = Var( critical_assets.loads, within = Binary )  # Investment decision for distribution substations

    # ======================================== Constraints
 
    model.Flow_Contraint    = Constraint(lines, rule = lambda model, l: model.PowerFlow[l] * line_reactance[l] == model.VoltAngle[line_endpoints[l][0]] - model.VoltAngle[line_endpoints[l][1]] )
    model.RefBus_Constraint = Constraint(expr = model.VoltAngle[ref_bus] == 0)

    # ========== Flow Bounds
    model.FlowUB_Constraints  = ConstraintList()
    model.FlowLB_Constraints  = ConstraintList()

    if add_trans_fail:

        model.TransInvest = Var( critical_assets.trans, within = Binary )  # Investment decision for transmission substations

        for bus in all_nodes: 
            if bus in critical_assets.trans: 
                for line in lines_adj[bus]:
                    model.FlowLB_Constraints.add( expr = model.PowerFlow[line] >= -1 * line_capacity[line]*( 1-damage_states.ds_branch[line]) * ( (1-damage_states.ds_trans[bus]) + damage_states.ds_trans[bus]*model.TransInvest[bus] ))
                    model.FlowUB_Constraints.add( expr = model.PowerFlow[line] <= line_capacity[line]*( 1-damage_states.ds_branch[line]) * ( (1-damage_states.ds_trans[bus]) + damage_states.ds_trans[bus]*model.TransInvest[bus] ))
            elif bus in trans_nodes and bus not in critical_assets.trans: 
                for line in lines_adj[bus]:
                    model.FlowLB_Constraints.add( expr = model.PowerFlow[line] >= -1 * line_capacity[line] * ( 1-damage_states.ds_branch[line]) * ( 1 - damage_states.ds_trans[bus]) )
                    model.FlowUB_Constraints.add( expr = model.PowerFlow[line] <= line_capacity[line] * ( 1-damage_states.ds_branch[line]) * (1 - damage_states.ds_trans[bus]))
            else:
                for line in lines_adj[bus]:
                    model.FlowLB_Constraints.add( expr = model.PowerFlow[line] >= -1 * line_capacity[line]* ( 1-damage_states.ds_branch[line]) )
                    model.FlowUB_Constraints.add( expr = model.PowerFlow[line] <= line_capacity[line] * ( 1-damage_states.ds_branch[line]))
    else: 
        for line in lines: 
            model.FlowUB_Constraints.add( expr = model.PowerFlow[line] <= line_capacity[line] * ( 1-damage_states.ds_branch[line]) )
            model.FlowLB_Constraints.add( expr = model.PowerFlow[line] >= -1 * line_capacity[line]* ( 1-damage_states.ds_branch[line]) )

    # ========== Gen Capacity Upper Bound
    model.GenCap_Constraints  = ConstraintList()
    for g in gens: 
        if g in critical_assets.gens: 
            model.GenCap_Constraints.add( 
                expr = model.PowerGenerated[g] <= ( unit_capacity[g] * (1 - damage_states.ds_gens[g]) ) + ( unit_capacity[g] * damage_states.ds_gens[g] * model.GenInvest[g] )  )
        else: 
            model.GenCap_Constraints.add( 
                expr = model.PowerGenerated[g] <= unit_capacity[g] * (1 - damage_states.ds_gens[g] ) )

    # ========== Load Shedding Lower Bound
    model.LShedLB_Constraints = ConstraintList()
    for bus in nodes_load:
        ds = damage_states.ds_loads[bus]
        if bus in critical_assets.loads: 
            model.LShedLB_Constraints.add( expr = model.LoadShedding[bus] >= demand[bus] * ds * ( 1 - model.DistSSInvest[bus] ) )
        else: 
            model.LShedLB_Constraints.add( expr = model.LoadShedding[bus] >= demand[bus] * ds )  


    # ========== DG

    if add_DG: 
        if add_DG and (DGcap == 0.0): 
            print("WARNING: added DG option but capacity is set to 0.0")
        model.DGInvest    = Var( critical_assets.loads, within = Binary)
        model.DGGenerated = Var( critical_assets.loads, within = NonNegativeReals)
        model.DG_Constraints  = ConstraintList()

        for bus in critical_assets.loads:

            site_ok = ( 1- damage_states.ds_loads[bus] ) + ( damage_states.ds_loads[bus] * model.DistSSInvest[bus] )  # 1 if bus is undamaged or if damaged but we invest in dist SS, else 0.

            model.DG_Constraints.add( expr = model.DGGenerated[bus] <= DGcap * model.DGInvest[bus] )             # capacity/indicctor -> fixed capacity if invest
            model.DG_Constraints.add( expr = model.DGGenerated[bus] <= demand[bus] - model.LoadShedding[bus] )   # can't generate more than what's needed to avoid shedding (dg reduces LS but no export is allowed) 
            model.DG_Constraints.add( expr = model.DGGenerated[bus] <= demand[bus] * site_ok )                   # cant use backup if bus is failed

            if islanded_map is not None: 
                model.DG_Constraints.add( expr = model.DGGenerated[bus] <= demand[bus] * islanded_map[bus] * site_ok ) # can't use backup if bus is undamaged but islanded from ref

    # ========= Nodal Balance

    def nb_rule(m,b):
        thermal = sum(m.PowerGenerated[g] for g in gens_by_bus[b]) if b in gens_by_bus else 0.0
        flows   = sum(m.PowerFlow[l] * line_to_bus_dict[(l,b)] for l in lines_by_bus[b])
        shed    = m.LoadShedding[b] if b in nodes_load else 0.0
        dg      =  0.0
        if add_DG and (b in critical_assets.loads):
            dg = m.DGGenerated[b]
        return thermal + flows + shed + dg == demand.get(b, 0.0)
    
    model.NodalBalance = Constraint(all_nodes, rule = nb_rule)
    
    # ================================================== OFV

    def invest_cost_rule(m):      # Per-scenario Invest Cost
        base_inv_cost = (sum(hard_frac * hardening_cost[g] * m.GenInvest[g]    for g in critical_assets.gens)  +  # hardening cost 9-30 -> cost ~= n in [0,1] * r in [9,30]
                         sum(hard_frac * hardening_cost[i] * m.DistSSInvest[i] for i in critical_assets.loads)  )
        if add_DG: 
            base_inv_cost += sum(1*m.DGInvest[i] for i in critical_assets.loads)
            #base_inv_cost += sum(0.005 * m.DGGenerated[i] for i in critical_assets.loads) 
        if add_trans_fail: 
            base_inv_cost += sum(hard_frac * hardening_cost[i] * m.TransInvest[i]  for i in critical_assets.trans)
        return base_inv_cost
    model.InvestCost = Expression(rule=invest_cost_rule)

    if max_invest is not None:   # Invest Budget Constraint
        model.InvestBudgetCons = Constraint(expr = model.InvestCost <= max_invest)
            
    def total_shed_cost_rule(m):  #Per-scenario Load Shedding Cost
        return sum(m.LoadShedding[i] for i in nodes_load)
    model.ShedCost   = Expression(rule=total_shed_cost_rule)

    def total_shed_rule(m): 
        return sum(m.LoadShedding[i] for i in nodes_load)
    model.TotalShed  = Expression(rule=total_shed_rule)

    def ObjectiveRule(model): 
        return  model.ShedCost + model.InvestCost*1e-6  # Scale down investment cost to keep objective in MW scale 
    model.ObjectiveVal  = Objective(rule = ObjectiveRule, sense = minimize)

    
    return model
                                                                                                                                                                                                                                           

################################################################################## Create Earthquake Scenarios 

def scenario_creator(scenario_name, **kwargs):
    
    sname = str(scenario_name)
    ds_all: DamageData = kwargs["damage_states"]

    ds_for_s = DamageData( ds_gens = ds_all.ds_gens[sname],ds_loads = ds_all.ds_loads[sname],ds_trans = ds_all.ds_trans[sname],ds_branch = ds_all.ds_branch[sname])
    
    grid = kwargs.get("grid")
    add_DG = kwargs.get("add_DG", False)
    hard_frac = kwargs.get("hard_frac")
    crit_assets = kwargs.get("crit_assets")
    max_invest = kwargs.get("max_invest", None)
    add_trans_fail = kwargs.get("add_trans_fail", False)
    DGcap = kwargs.get("DGcap", 0.0)
    islanded_all = kwargs.get("islanded_map", None)
    islanded_for_s = islanded_all.get(sname, None) if islanded_all is not None else None

    model = build_inv_opt(grid=grid, 
        hard_frac=hard_frac,
        damage_states=ds_for_s,
        critical_assets=crit_assets,
        max_invest = max_invest, 
        add_DG = add_DG,
        add_trans_fail=add_trans_fail,
        DGcap=DGcap,
        islanded_map = islanded_for_s)

    num_scenarios = int(kwargs.get("num_scenarios", 1))

    form = kwargs.get("form", "risk_neutral")
    
    root_vars = [model.GenInvest, model.DistSSInvest]

    if add_trans_fail: 
        root_vars.append(model.TransInvest)
    if add_DG: 
        root_vars.append(model.DGInvest)

    sputils.attach_root_node(model, model.ObjectiveVal, root_vars) # ---- Attach Non-anticipativity info ---
    model._mpisppy_probability = 1.0 / float(num_scenarios)

    return model

################################################################################### Build SP & Solve 

def model_build_solve(
        form:str, 
        grid: GridData, 
        damage_states: DamageData,
        crit_assets: CriticalAssets,
        hard_frac:float = 0.5, 
        alpha:float = 0.99,
        lam:float = 1.0,
        add_DG: bool = False,
        save_inner_varvals: bool=False, 
        DGcap: float = 0.0,
        add_trans_fail: bool = False,
        max_invest=None,
        time_solve = False, 
        tee = False, 
        print_vars = False, 
        mip_gap: float = 0.01):

    options = {"solver": "gurobi"}
    all_scenario_names = [str(s) for s in damage_states.ds_gens.keys()]
    num_scenarios = len(all_scenario_names)
    islanded_map = compute_islanded_undamaged_map(grid, damage_states)
    any_s = all_scenario_names[0]

    #Build Extensive Form
    ef = ExtensiveForm(options, all_scenario_names, scenario_creator, scenario_creator_kwargs={
                           "num_scenarios": num_scenarios,
                             "form": form, 
                             "grid": grid, 
                             "hard_frac": hard_frac,
                             "damage_states": damage_states,
                             "crit_assets": crit_assets,
                             "max_invest": max_invest, 
                             "add_DG": add_DG,
                             "add_trans_fail": add_trans_fail, 
                             "islanded_map": islanded_map,
                             "DGcap": DGcap})
    ef_model = ef.ef

    def expected_shed_rule(m):
            return (1.0/num_scenarios) * sum( ef.local_scenarios[sname].TotalShed for sname in all_scenario_names)

    ef_model.ExpectedShed = Expression(rule=expected_shed_rule)
    ef_model.Invest = Expression(expr= ef.local_scenarios[any_s].InvestCost)  #Investment Cost
                                       
    if form in ("cvar_mean", "cvar_only"):    
        #===================================================== CVaR
        ef_model.eta = Var(within=NonNegativeReals)                        # Value-at-Risk(VaR) threshold 
        ef_model.xi  = Var(all_scenario_names, within=NonNegativeReals)    # Per scenario aux. var: excess loss above VaR threshold

        def cvar_link_rule(m, sname): 
            scen = ef.local_scenarios[sname]
            return m.xi[sname] >= scen.TotalShed - m.eta
        ef_model.Cvar_linking_Constraint = Constraint(all_scenario_names, rule=cvar_link_rule)

        def CVar_expr_rule(m):
            return m.eta + (1.0 /( (1.0 - alpha)*num_scenarios)) * sum( m.xi[sname] for sname in all_scenario_names)   # Expression for CVaR Value
        ef_model.Cvar = Expression(rule = CVar_expr_rule)

        #======================================================= Objective Function

        ef_model.del_component(ef_model.EF_Obj) # Delete Default objective

        if form=="cvar_mean":
            def EF_Objective_CVar_rule(m):  
                return ef_model.ExpectedShed + lam * m.Cvar 

        elif form=="cvar_only": 
            def EF_Objective_CVar_rule(m):
                return lam * m.Cvar + ef_model.Invest*1e-6  # Scale down investment cost to keep objective in MW scale, but still have it as a tie-breaker among equal CVaR solutions
        else: 
            raise ValueError(f"Unknown form {form} for CVaR objective modification.")
        
        ef_model.EF_Obj = Objective(rule=EF_Objective_CVar_rule, sense=minimize)

    #ef_model.write(f"SP_{form}.lp", io_options={"symbolic_solver_labels": True})

    # =========================================================== Solve & Print Runtime and CVaR (average LS above the VaR threshold)

    extreme_ls_scenarios = {}

    start_time = time.time()
    results    = ef.solve_extensive_form(solver_options = {"MIPGap":mip_gap}, tee=tee)
    end_time   = time.time()

    if time_solve: 
        print(f"Runtime: {end_time - start_time:.2f} seconds")

    if form in ("cvar_mean", "cvar_only"):               # Print CVaR Value
        eta_val  = value(ef_model.eta)
        xi_sum   = sum(value(ef_model.xi[s]) for s in all_scenario_names)
        cvar_val = eta_val + (1.0 /( (1.0 - alpha)*num_scenarios)) * xi_sum
        print(f"Computed CVaR (MW): {round(cvar_val, 4)}")

    #==================================================== Get scenarios with LS above cvar threshold

        for s in all_scenario_names:
            scen = ef.local_scenarios[s]
            if value(scen.TotalShed) >= eta_val:
                extreme_ls_scenarios[s] = round(value(scen.TotalShed), 4)

    #====================================================== Compute CVaR from solution

    all_scenario_names = list(ef.local_scenarios.keys())
    num_scenarios = len(all_scenario_names)

    #============= Compute expected LS
    shed_vals = []
    for s in all_scenario_names:
        scen = ef.local_scenarios[s]
        shed_vals.append(value(scen.TotalShed))
        
    N = len(shed_vals)
    sorted_shed = sorted(shed_vals)
    k = int((1 - alpha) * N)    # number of tail scenarios
    tail = sorted_shed[-k:] if k > 0 else []
    true_cvar = sum(tail) / len(tail) if tail else 0.0

    #====================================================== Print results

    print("========================================================")
    print(f"\nInvestment cost: ${value(ef_model.Invest):.2f} (M)")
    print(f"Expected load shed: {value(ef_model.ExpectedShed):.2f} MW")
    print(f"Total EF objective: {value(ef_model.EF_Obj):.2f}")
    print(f"True CVaR from {form} solution:", round(true_cvar,2) , "MW") 

    #======================================================= Get value of variables and return Results

    variables   = ef.gather_var_values_to_rank0()
    invest_vars = ["GenInvest", "DistSSInvest"]

    if add_trans_fail:
        invest_vars.append("TransInvest")
    if add_DG:
        invest_vars.append("DGInvest")

    def _get_invst_var_dict(var_str:str, var_dict:dict, var_obj, var_val):
        if var_obj.startswith(var_str):
            s = re.search(r"\[(.*?)\]", var_obj) # look for square brackets and extract content
            if  s:
                idx = s.group(1).strip().strip("'\"")
                var_dict[idx] = round(var_val)
        return var_dict


    gen_inv, load_inv, trans_inv, DG_inv = {}, {}, {}, {}
    for ((_, var_name), var_value) in variables.items():
        _get_invst_var_dict("GenInvest[", gen_inv, var_name, var_value)
        _get_invst_var_dict("DistSSInvest[", load_inv, var_name, var_value)
        _get_invst_var_dict("TransInvest[", trans_inv, var_name, var_value)
        _get_invst_var_dict("DGInvest[", DG_inv, var_name, var_value)

    # ================================================================ Print Investment Decisions

    if print_vars == True:                     
        print("\nInvestment Decisions:")
        printed = set()
        for ((_, var_name), var_value) in variables.items():
            if any((var_name.startswith(v) for v in invest_vars)):
                if var_name not in printed and var_value > 0.5:
                    print(f"{var_name} = {var_value}")
                    printed.add(var_name)


    if save_inner_varvals  == True: 

        import numpy as np

        def _extract_df(var):
            series = pd.Series(var.extract_values(), name=var.name)
            df = series.reset_index()
            df.columns = ["ID", var.name]
            return df

        def _extract_results(m):
            scen = getattr(m, "experiment_id", "unknown_scenario")
            flow = _extract_df(m.PowerFlow)
            mwh  = _extract_df(m.PowerGenerated)
            shed = _extract_df(m.LoadShedding)
            return { "flow": flow, "mwh": mwh, "shed": shed}

        var_values = {}
        for s in all_scenario_names:
            worst_s = all_scenario_names[int(np.argmax(shed_vals))]
            scen = ef.local_scenarios[worst_s]
            var_values = {worst_s: _extract_results(scen)}


        return { "form": form,
                "inv_cost": value(ef_model.Invest),  
                "expected_shed": value(ef_model.ExpectedShed),
                "cvar": true_cvar,
                "gen_inv": gen_inv,
                "load_inv": load_inv,
                "trans_inv": trans_inv, 
                "shed_vals": shed_vals, 
                "inner_var_vals": var_values,
                "DG_inv": DG_inv, 
                "extreme_ls_scenarios": extreme_ls_scenarios,
                "DGcap": DGcap,
                "scenario_names": all_scenario_names, 
                "variables": variables, 
                "ef": ef_model}
    else:
        return { "form": form,
                "inv_cost": value(ef_model.Invest),  
                "expected_shed": value(ef_model.ExpectedShed),
                "cvar": true_cvar,
                "gen_inv": gen_inv,
                "load_inv": load_inv,
                "trans_inv": trans_inv, 
                "shed_vals": shed_vals, 
                "DG_inv": DG_inv, 
                "extreme_ls_scenarios": extreme_ls_scenarios,
                "DGcap": DGcap,
                "scenario_names": all_scenario_names, 
                "variables": variables, 
                "ef": ef_model}



