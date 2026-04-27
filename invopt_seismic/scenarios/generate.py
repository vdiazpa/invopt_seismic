# scenario_utils.py

from ..data_utils.structures import as_damage_data
from pathlib import Path
import pandas as pd
import numpy as np
import pickle
import random
import math
import re

def parse_branch_entry(v):
    if pd.isna(v) or re.sub(r"\s+", "", v) =="None":
        return None
    else: 
        s = re.search(r'\((.*?)\)', v).group(1).split(" ")
        l = str(s[0]) + '_' + str(s[1]) + '_' + s[2].strip("'")
        return l

def parse_gen_entry(v):
    if pd.isna(v) or re.sub(r"\s+", "", v) =="None":
        return None
    else:
        bus   = re.search(r'\d+', v).group(0)
        ftype = re.search(r"'(.*?)'", v).group(1).strip()
        return f"{bus}_{ftype}"
    
def parse_xfmr_entry(v):
    if pd.isna(v) or re.sub(r"\s+", "", v) =="None":
        return None
    else:
        s = re.search(r'\((.*?)\)', v).group(1).split(" ")
        xf = str(s[0]) + '_' + str(s[1]) + '_' + str(s[2])
        return xf

def generate_rand_all(data: dict, num_rand_sc: int=None, seed: int=None, frac_gens: float=0.15, frac_loads: float=0.15, frac_trans:float=0.05, frac_branch: float=0.10,): 
    
    ds_gens   = {}
    ds_loads  = {}
    ds_trans  = {}
    ds_branch = {}

    gens  = data['gens']
    lines = data['lines']
    nodes_load  = data['nodes_load']
    trans_nodes = data['trans_nodes']

    if seed is not None:
        random.seed(seed)

    all_scenario_names = [str(i) for i in range(num_rand_sc)]

    print(f"Random damage states will be generated for {len(all_scenario_names)} scenarios")

    for sc in all_scenario_names:
        dam_gens_samp   = random.sample(gens,        k=min(math.ceil(len(gens)        * frac_gens),   len(gens)))
        dam_lnodes_samp = random.sample(nodes_load,  k=min(math.ceil(len(nodes_load)  * frac_loads),  len(nodes_load)))
        dam_trans_samp  = random.sample(trans_nodes, k=min(math.ceil(len(trans_nodes) * frac_trans),  len(trans_nodes)))
        dam_branch_samp = random.sample(lines,       k=min(math.ceil(len(lines)       * frac_branch), len(lines)))

        ds_gens[sc]   = {g: int(g in dam_gens_samp)   for g in gens}
        ds_loads[sc]  = {n: int(n in dam_lnodes_samp) for n in nodes_load}
        ds_trans[sc]  = {t: int(t in dam_trans_samp)  for t in trans_nodes}      
        ds_branch[sc] = {l: int(l in dam_branch_samp) for l in lines}

    return as_damage_data(ds_gens, ds_loads, ds_trans, ds_branch)

def generate_rand_in_polygon(data: dict, num_rand_sc: int=None, seed: int=None, bus_in_poly: list=None, use_avg_k: bool= False,
    frac_gens:   float=0.15,
    frac_loads:  float=0.15,
    frac_trans:  float=0.05,
    frac_branch: float=0.10,
    avg_k_gens:  float= None,  # number of generators to fail on random in polygon mode
    avg_k_loads: float= None,  # number of loads to fail on random in polygon mode
    avg_k_trans:  float= None, # number of transmission nodes to fail on random in polygon mode
    avg_k_branch: float= None, # number of branches to fail on random in polygon
    ):

    ds_gens   = {}
    ds_loads  = {}
    ds_trans  = {}
    ds_branch = {}

    gens  = data['gens']
    lines = data['lines']
    nodes_load  = data['nodes_load']
    trans_nodes = data['trans_nodes']
    gens_by_bus = data['gens_by_bus']

    if seed is not None:
        random.seed(seed)

    all_scenario_names = [str(i) for i in range(num_rand_sc)]

    print(f"Random damage states will be generated for {len(all_scenario_names)} scenarios, only for assets inside polygon")

    line_endpoints = data['line_endpoints']

    lines_in_poly = [l for l in line_endpoints if (line_endpoints[l][0] in bus_in_poly) and (line_endpoints[l][1] in bus_in_poly)]
    gens_in_poly  = [g for bus_id, gens_tup in gens_by_bus.items() if bus_id in bus_in_poly for g in gens_tup]
    trans_in_poly = [t for t in trans_nodes if t in bus_in_poly]
    loads_in_poly = [n for n in nodes_load if n in bus_in_poly]

    if use_avg_k:
        k_g = 0 if avg_k_gens is None else int(math.ceil(avg_k_gens))
        k_l = 0 if avg_k_loads is None else int(math.ceil(avg_k_loads))
        k_t = 0 if avg_k_trans is None else int(math.ceil(avg_k_trans))
        k_b = 0 if avg_k_branch is None else int(math.ceil(avg_k_branch))

    else: 
        k_g = math.ceil(len(gens_in_poly)  * frac_gens)
        k_l = math.ceil(len(loads_in_poly) * frac_loads)
        k_t = math.ceil(len(trans_in_poly) * frac_trans)     
        k_b = math.ceil(len(lines_in_poly) * frac_branch)

    k_g = max(0, min(k_g, len(gens_in_poly)))
    k_l = max(0, min(k_l, len(loads_in_poly)))
    k_t = max(0, min(k_t, len(trans_in_poly)))
    k_b = max(0, min(k_b, len(lines_in_poly)))

    for sc in all_scenario_names:
        dam_gens_samp   = random.sample(gens_in_poly,   k=k_g)
        dam_lnodes_samp = random.sample(loads_in_poly,  k=k_l)
        dam_trans_samp  = random.sample(trans_in_poly,  k=k_t)
        dam_branch_samp = random.sample(lines_in_poly, k=k_b)

        ds_gens[sc]   = {g: int(g in dam_gens_samp)   for g in gens}
        ds_loads[sc]  = {n: int(n in dam_lnodes_samp) for n in nodes_load}
        ds_trans[sc]  = {t: int(t in dam_trans_samp)  for t in trans_nodes}      
        ds_branch[sc] = {l: int(l in dam_branch_samp) for l in lines}

    return as_damage_data(ds_gens, ds_loads, ds_trans, ds_branch)

def generate_from_MC(
    data: dict, 
    num_trials:  int = None,   # number of trials per eartquake to consider
    event_ids:   list= None,   # list w. earthquake ID numbers to consider
    patch:      str = "",
    cache_dir:  str = None,
    cache_tag: str = None,
    use_cache: bool = True):
    
    gens  = data['gens']
    lines = data['lines']
    nodes_load  = data['nodes_load']
    trans_nodes = data['trans_nodes']

    ds_gens   = {}
    ds_loads  = {}
    ds_trans  = {}
    ds_branch = {}

    print(f"Loading damage states from files for {len(event_ids)} realizations and {num_trials} trials each")

    # samples_folder = Path(r"//snl/collaborative/Seismic_Grid/seismicGridProject_v2_share_expanded/data/Results/Dynamic_Simulations_Anchored/failure_times/")
    
    samples_folder = Path(r"//cee/Projects/Seismic_Grid/seismic_grid/data/Results")

    if not samples_folder.exists():
        print(f"Cant find cee parent folder ...", flush=True)

    all_scenario_names = [f'event{i}_trial{j}' for i in event_ids for j in range(num_trials)]
    
    cache_path = None
    if cache_dir is not None:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

        if cache_tag is None:
            cache_tag = f"files_events{event_ids}_trials{num_trials}"

        cache_path = Path(cache_dir) / f"ds_{cache_tag}.pkl"

        if use_cache and cache_path.exists():
            with open(cache_path, 'rb') as f:
                ds_gens, ds_loads, ds_trans, ds_branch = pickle.load(f)
            print(f"Loaded damage states from cache: {cache_path}")

            return as_damage_data(ds_gens, ds_loads, ds_trans, ds_branch)

    total = len(event_ids) * num_trials
    samples_df = {}
    count = 0

    for event in event_ids:

        parent_folder = f"240busWECC_2018_PSS_real{event}_Anchored_Moderate"
        print(parent_folder)
        
        for trial in range(num_trials):
            count +=1
            print(f"[{count}/{total}] Parsing EQ event {event}, trial {trial} ...")
            fname = f"fail_table_trial{trial}.csv"
            # fname = f"240busWECC_2018_PSS_real{event}{patch}_combined_trial{trial}.csv"
            
            fpath = samples_folder / parent_folder / fname

            if not fpath.exists():
                print(f"File not found: {fpath}, skipping ...", flush=True)
                continue
            try:
                df = pd.read_csv(fpath)
            except Exception as e:
                print(f"Error reading {fpath}: {e}")
                continue

            samples_df[f"event{event}_trial{trial}"] = df

    for sc, df in samples_df.items():
        if df.empty:
            continue

        df = df.copy()
        df.columns = df.columns.str.strip()

        branch_failures, load_failures, gen_failures = [], [], []
        
        if "Line_fails" in df.columns:
        # if "Branch_fails" in df.columns:
            for v in df["Branch_fails"].dropna():
                key = parse_branch_entry(v)
                if key != None and key in lines:
                    branch_failures.append(key)

        if "Xfmr_fails" in df.columns:
            for v in df["Xfmr_fails"].dropna():
                key = parse_xfmr_entry(v)
                if key != None and key in lines:
                    branch_failures.append(key)

        if "Load_fails" in df.columns:
            for val in df["Load_fails"].dropna():
                s = str(val).strip()
                if s not in ("", "None"):
                    load_failures.append(s)
        load_failures_strp = [int(x.strip("[]")) for x in load_failures]

        if "Gen_fails" in df.columns:
            for v in df["Gen_fails"].dropna():
                key = parse_gen_entry(v)
                if key != None: 
                    gen_failures.append(key)

        ds_branch[sc] = {l: int(l in branch_failures)    for l in lines}
        ds_loads[sc]  = {n: int(n in load_failures_strp) for n in nodes_load}
        ds_gens[sc]   = {g: int(g in gen_failures)       for g in gens}
        ds_trans[sc]  = {t: 0 for t in trans_nodes}                        # no trans failures

    if cache_path is not None:
        with open(cache_path, 'wb') as f:
            pickle.dump((ds_gens, ds_loads, ds_trans, ds_branch), f, protocol=pickle.HIGHEST_PROTOCOL)

        print(f"Saved damage states to cache: {cache_path}")

    return as_damage_data(ds_gens, ds_loads, ds_trans, ds_branch)

def generate_from_bernoulli(
    data: dict, 
    num_trials:  int = None,   # number of trials per eartquake to consider
    event_ids:   list= None,   # list w. earthquake ID numbers to consider
    patch: str = "",
    by_type: bool=False, 
    cache_dir: str=None,
    cache_tag: str=None,
    seed: int = None, 
    use_cache: bool=True):
    
    if seed is not None: 
        np.random.seed(seed)

    gens  = data['gens']
    lines = data['lines']
    nodes_load  = data['nodes_load']
    trans_nodes = data['trans_nodes']

    ds_gens   = {}
    ds_loads  = {}
    ds_trans  = {}
    ds_branch = {}

    print(f"Loading damage states from files for {len(event_ids)} realizations and {num_trials} trials each")

    samples_folder = Path(r"//snl/collaborative/Seismic_Grid/seismicGridProject_v2_share_expanded/data/Results/Dynamic_Simulations_Anchored/failure_times/")

    all_scenario_names = [f'event{i}_trial{j}' for i in event_ids for j in range(num_trials)]
    total = len(event_ids) * num_trials
    samples_df = {}
    count = 0

    cache_path = None
    if cache_dir is not None:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

        if cache_tag is None:
            cache_tag = f"files_events{event_ids}_trials{num_trials}"

        cache_path = Path(cache_dir) / f"ds_{cache_tag}.pkl"

        if use_cache and cache_path.exists():
            with open(cache_path, 'rb') as f:
                ds_gens, ds_loads, ds_trans, ds_branch = pickle.load(f)
            print(f"Loaded damage states from cache: {cache_path}")

        else: 
            for event in event_ids:
                for trial in range(num_trials):
                    
                    count +=1
                    print(f"[{count}/{total}] Parsing EQ event {event}, trial {trial} ...")
                    fname = f"240busWECC_2018_PSS_real{event}{patch}_combined_trial{trial}.csv"
                    fpath = samples_folder / fname

                    if not fpath.exists():
                        print(f"File not found: {fpath}, skipping ...", flush=True)
                        continue

                    try:
                        df = pd.read_csv(fpath)
                    except Exception as e:
                        print(f"Error reading {fpath}: {e}")
                        continue

                    samples_df[f"event{event}_trial{trial}"] = df

            for sc, df in samples_df.items():
                if df.empty:
                    continue

                df = df.copy()
                df.columns = df.columns.str.strip()

                branch_failures, load_failures, gen_failures = [], [], []
                
                if "Branch_fails" in df.columns:
                    for v in df["Branch_fails"].dropna():
                        key = parse_branch_entry(v)
                        if key != None and key in lines:
                            branch_failures.append(key)

                if "Xfmr_fails" in df.columns:
                    for v in df["Xfmr_fails"].dropna():
                        key = parse_xfmr_entry(v)
                        if key != None and key in lines:
                            branch_failures.append(key)

                if "Load_fails" in df.columns:
                    for val in df["Load_fails"].dropna():
                        s = str(val).strip()
                        if s not in ("", "None"):
                            load_failures.append(s)
                load_failures_strp = [int(x.strip("[]")) for x in load_failures]

                if "Gen_fails" in df.columns:
                    for v in df["Gen_fails"].dropna():
                        key = parse_gen_entry(v)
                        if key != None: 
                            gen_failures.append(key)

                ds_branch[sc] = {l: int(l in branch_failures)    for l in lines}
                ds_loads[sc]  = {n: int(n in load_failures_strp) for n in nodes_load}
                ds_gens[sc]   = {g: int(g in gen_failures)       for g in gens}
                ds_trans[sc]  = {t: 0 for t in trans_nodes}                        # no trans failures

    if by_type==False:   #Create probability dict per component type. 
        
        ds_gens_orig = ds_gens.copy()
        ds_loads_orig = ds_loads.copy()
        ds_branch_orig = ds_branch.copy()
        ds_trans_orig = ds_trans.copy()

        for sc in ds_gens_orig:
            event_tag = sc.split("_trial")[0]

            event_scens = [k for k in ds_gens_orig if k.startswith(event_tag + "_")]

            #compute marginal probabilities
            prob_gens = {g: np.mean([ds_gens_orig[k][g] for k in event_scens]) for g in gens}
            prob_loads = {node: np.mean([ds_loads_orig[k][node] for k in event_scens]) for node in nodes_load}
            prob_lines = {line: np.mean([ds_branch_orig[k][line] for k in event_scens]) for line in lines}

            #crate the damage-state objects for the model 
            ds_gens[sc] = {g: np.random.binomial(1,p) for g,p in prob_gens.items()}
            ds_loads[sc] = {node: np.random.binomial(1,p) for node,p in prob_loads.items()}
            ds_branch[sc] = {line: np.random.binomial(1,p) for line,p in prob_lines.items()}
            ds_trans[sc]  = {t: 0 for t in trans_nodes}

        return as_damage_data(ds_gens, ds_loads, ds_trans, ds_branch)

def scenario_generator(
        mode: str,
        data: dict,
        num_rand_sc: int = None,
        num_trials:  int = None,   # number of trials per eartquake to consider
        event_ids:   list= None,   # list w. earthquake ID numbers to consider
        bus_in_poly: list= None,   # list of buses inside polygon
        use_avg_k:   bool= False,
        avg_k_gens:  float= None,  # number of generators to fail on random in polygon mode
        avg_k_loads: float= None,  # number of loads to fail on random in polygon mode
        avg_k_trans:  float= None, # number of transmission nodes to fail on random in polygon mode
        avg_k_branch: float= None, # number of branches to fail on random in polygon mode
        frac_gens:   float=0.15,
        frac_loads:  float=0.15,
        frac_trans:  float=0.05,
        frac_branch: float=0.10,
        patch:      str = "",
        seed:       int = None, 
        cache_dir:  str = None,
        cache_tag: str = None,
        use_cache: bool = True):

    """Returns a damage state object with per asset damage states (ds_*). 
    """
    ds_gens   = {}
    ds_loads  = {}
    ds_trans  = {}
    ds_branch = {}

    gens  = data['gens']
    lines = data['lines']
    nodes_load  = data['nodes_load']
    gens_by_bus = data['gens_by_bus']
    trans_nodes = data['trans_nodes']
    
    all_scenario_names = ([str(i) for i in range(num_rand_sc)] if mode in ["rand_in_polygon", "rand_all"] else [f'event{i}_trial{j}' for i in event_ids for j in range(num_trials)])

    cache_path = None
    if cache_dir is not None:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

        if cache_tag is None:
            if mode == "files":
                cache_tag = f"files_events{event_ids}_trials{num_trials}"
            elif mode in ["rand_in_polygon", "rand_all"]:
                cache_tag = f"{mode}_N{num_rand_sc}_seed{seed}"
            else: 
                cache_tag = f"{mode}_seed{seed}"

        cache_path = Path(cache_dir) / f"ds_{cache_tag}.pkl"

        if use_cache and cache_path.exists():
            with open(cache_path, 'rb') as f:
                ds_gens, ds_loads, ds_trans, ds_branch = pickle.load(f)
            print(f"Loaded damage states from cache: {cache_path}")

            return as_damage_data(ds_gens, ds_loads, ds_trans, ds_branch)

    if seed is not None:
        random.seed(seed)

    if mode == "rand_all":

        print(f"Random damage states will be generated for {len(all_scenario_names)} scenarios")

        for sc in all_scenario_names:
            dam_gens_samp   = random.sample(gens,        k=min(math.ceil(len(gens)        * frac_gens),   len(gens)))
            dam_lnodes_samp = random.sample(nodes_load,  k=min(math.ceil(len(nodes_load)  * frac_loads),  len(nodes_load)))
            dam_trans_samp  = random.sample(trans_nodes, k=min(math.ceil(len(trans_nodes) * frac_trans),  len(trans_nodes)))
            dam_branch_samp = random.sample(lines,       k=min(math.ceil(len(lines)       * frac_branch), len(lines)))

            ds_gens[sc]   = {g: int(g in dam_gens_samp)   for g in gens}
            ds_loads[sc]  = {n: int(n in dam_lnodes_samp) for n in nodes_load}
            ds_trans[sc]  = {t: int(t in dam_trans_samp)  for t in trans_nodes}      
            ds_branch[sc] = {l: int(l in dam_branch_samp) for l in lines}

        return as_damage_data(ds_gens, ds_loads, ds_trans, ds_branch)


    elif mode == "rand_in_polygon":

        print(f"Random damage states will be generated for {len(all_scenario_names)} scenarios, only for assets inside polygon")

        line_endpoints = data['line_endpoints']

        lines_in_poly = [l for l in line_endpoints if (line_endpoints[l][0] in bus_in_poly) and (line_endpoints[l][1] in bus_in_poly)]
        gens_in_poly  = [g for bus_id, gens_tup in gens_by_bus.items() if bus_id in bus_in_poly for g in gens_tup]
        trans_in_poly = [t for t in trans_nodes if t in bus_in_poly]
        loads_in_poly = [n for n in nodes_load if n in bus_in_poly]

        if use_avg_k:
            k_g = 0 if avg_k_gens is None else int(math.ceil(avg_k_gens))
            k_l = 0 if avg_k_loads is None else int(math.ceil(avg_k_loads))
            k_t = 0 if avg_k_trans is None else int(math.ceil(avg_k_trans))
            k_b = 0 if avg_k_branch is None else int(math.ceil(avg_k_branch))

        else: 
            k_g = math.ceil(len(gens_in_poly)  * frac_gens)
            k_l = math.ceil(len(loads_in_poly) * frac_loads)
            k_t = math.ceil(len(trans_in_poly) * frac_trans)     
            k_b = math.ceil(len(lines_in_poly) * frac_branch)

        k_g = max(0, min(k_g, len(gens_in_poly)))
        k_l = max(0, min(k_l, len(loads_in_poly)))
        k_t = max(0, min(k_t, len(trans_in_poly)))
        k_b = max(0, min(k_b, len(lines_in_poly)))

        for sc in all_scenario_names:
            dam_gens_samp   = random.sample(gens_in_poly,   k=k_g)
            dam_lnodes_samp = random.sample(loads_in_poly,  k=k_l)
            dam_trans_samp  = random.sample(trans_in_poly,  k=k_t)
            dam_branch_samp = random.sample(lines_in_poly, k=k_b)

            ds_gens[sc]   = {g: int(g in dam_gens_samp)   for g in gens}
            ds_loads[sc]  = {n: int(n in dam_lnodes_samp) for n in nodes_load}
            ds_trans[sc]  = {t: int(t in dam_trans_samp)  for t in trans_nodes}      
            ds_branch[sc] = {l: int(l in dam_branch_samp) for l in lines}

    elif mode == "files":

        print(f"Loading damage states from files for {len(event_ids)} realizations and {num_trials} trials each")

        samples_folder = Path(r"//snl/collaborative/Seismic_Grid/seismicGridProject_v2_share_expanded/data/Results/Dynamic_Simulations_Anchored/failure_times/")
        
        samples_df = {}

        total = len(event_ids) * num_trials
        count = 0
        for event in event_ids:
            for trial in range(num_trials):
                
                count +=1
                print(f"[{count}/{total}] Parsing EQ event {event}, trial {trial} ...")
                fname = f"240busWECC_2018_PSS_real{event}{patch}_combined_trial{trial}.csv"
                fpath = samples_folder / fname

                if not fpath.exists():
                    print(f"File not found: {fpath}, skipping ...", flush=True)
                    continue

                try:
                    df = pd.read_csv(fpath)
                except Exception as e:
                    print(f"Error reading {fpath}: {e}")
                    continue

                samples_df[f"event{event}_trial{trial}"] = df

        for sc, df in samples_df.items():
            if df.empty:
                continue

            df = df.copy()
            df.columns = df.columns.str.strip()

            branch_failures, load_failures, gen_failures = [], [], []

            def _parse_branch_entry(v):
                if pd.isna(v) or re.sub(r"\s+", "", v) =="None":
                    return None
                else: 
                    s = re.search(r'\((.*?)\)', v).group(1).split(" ")
                    l = str(s[0]) + '_' + str(s[1]) + '_' + s[2].strip("'")
                    return l

            def _parse_gen_entry(v):
                if pd.isna(v) or re.sub(r"\s+", "", v) =="None":
                    return None
                else:
                    bus   = re.search(r'\d+', v).group(0)
                    ftype = re.search(r"'(.*?)'", v).group(1).strip()
                    return f"{bus}_{ftype}"
                
            def _parse_xfmr_entry(v):
                if pd.isna(v) or re.sub(r"\s+", "", v) =="None":
                    return None
                else:
                    s = re.search(r'\((.*?)\)', v).group(1).split(" ")
                    xf = str(s[0]) + '_' + str(s[1]) + '_' + str(s[2])
                    return xf

            if "Branch_fails" in df.columns:
                for v in df["Branch_fails"].dropna():
                    key = _parse_branch_entry(v)
                    if key != None and key in lines:
                        branch_failures.append(key)

            if "Xfmr_fails" in df.columns:
                for v in df["Xfmr_fails"].dropna():
                    key = _parse_xfmr_entry(v)
                    if key != None and key in lines:
                        branch_failures.append(key)

            if "Load_fails" in df.columns:
                for val in df["Load_fails"].dropna():
                    s = str(val).strip()
                    if s not in ("", "None"):
                        load_failures.append(s)
            load_failures_strp = [int(x.strip("[]")) for x in load_failures]

            if "Gen_fails" in df.columns:
                for v in df["Gen_fails"].dropna():
                    key = _parse_gen_entry(v)
                    if key != None: 
                        gen_failures.append(key)

            ds_branch[sc] = {l: int(l in branch_failures)    for l in lines}
            ds_loads[sc]  = {n: int(n in load_failures_strp) for n in nodes_load}
            ds_gens[sc]   = {g: int(g in gen_failures)       for g in gens}
            ds_trans[sc]  = {t: 0 for t in trans_nodes}                        # no trans failures

        #  #----- Plot Branch Failures across samples -----

        #plot_failure_frequencies(ds_branch, asset_type='Branch')

    else:
        raise ValueError(f"Unknown mode: {mode}")

    if cache_path is not None:
        with open(cache_path, 'wb') as f:
            pickle.dump((ds_gens, ds_loads, ds_trans, ds_branch), f, protocol=pickle.HIGHEST_PROTOCOL)

        print(f"Saved damage states to cache: {cache_path}")

    return as_damage_data(ds_gens, ds_loads, ds_trans, ds_branch)
