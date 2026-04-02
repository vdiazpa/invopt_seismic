# scenario_utils.py
import math
import random
import re
import os
import pandas as pd
from collections import Counter
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib.pyplot as plt


def scenario_generator(
        mode: str,
        num_scenarios: int,
        gens,
        nodes_load,
        trans_nodes,
        lines,
        frac_gens:  float=0.15,
        frac_loads: float=0.15,
        frac_trans: float=0.05,
        frac_branch = 0.10,
        seed: int = 42):
    
    """Return damage states for all scenarios.
    gens, nodes_load, trans_nodes, lines are iterables (lists, sets, etc.).
    """

    gens_list  = list(gens)
    load_list  = list(nodes_load)
    trans_list = list(trans_nodes)
    line_list  = list(lines)

    ds_gens   = {}
    ds_loads  = {}
    ds_trans  = {}
    ds_branch = {}

    all_scenario_names = [str(i) for i in range(num_scenarios)]

    if seed:
        random.seed(seed)

    if mode == "random":

        print(f"Random damage states will be generated for {num_scenarios} scenarios")

        random.seed(seed)
        for sc in all_scenario_names:
            dam_gens_samp   = random.sample(gens_list,  k=min(math.ceil(len(gens_list)  * frac_gens), len(gens_list)))
            dam_lnodes_samp = random.sample(load_list,  k=min(math.ceil(len(load_list)  * frac_loads), len(load_list)))
            dam_trans_samp  = random.sample(trans_list, k=min(math.ceil(len(trans_list) * frac_trans), len(trans_list)))
            dam_branch_samp = random.sample(line_list,  k=min(math.ceil(len(line_list)  * frac_branch), len(line_list)))

            ds_gens[sc]   = {g: int(g in dam_gens_samp)    for g in gens_list}
            ds_loads[sc]  = {n: int(n in dam_lnodes_samp)  for n in load_list}
            ds_trans[sc]  = {t: int(t in dam_trans_samp)  for t in trans_list}       # no trans failures
            ds_branch[sc] = {l: int(l in dam_branch_samp)  for l in line_list}

    elif mode == "files":

        print(f"Loading damage states from files for {num_scenarios} scenarios")

        all_scenario_names = random.sample([str(i) for i in range(0, 9999+1)], k=num_scenarios)

        samples_folder = (r"//snl/collaborative/Seismic_Grid/seismicGridProject_v2_share/"
            r"data/Results/Dynamic_Simulations_Anchored/failure_times/")

        #samples_folder = (r"//snl/collaborative/Seismic_Grid/seismicGridProject_v2_share_expanded/data/Results/Dynamic_Simulations_Anchored/failure_times/")
        
        samples_df = {}

        for i in range(num_scenarios):
            fname = f"240busWECC_2018_PSS_real1_combined_trial{i}.csv"
            fpath = os.path.join(samples_folder, fname)
            df = pd.read_csv(fpath)
            samples_df[i] = df

        for trial, df in samples_df.items():
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
                    if key != None and key in line_list:
                        branch_failures.append(key)

            if "Xfmr_fails" in df.columns:
                for v in df["Xfmr_fails"].dropna():
                    key = _parse_xfmr_entry(v)
                    if key != None and key in line_list:
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

            sname = str(trial)

            ds_branch[sname] = {l: int(l in branch_failures)    for l in line_list}
            ds_loads[sname]  = {n: int(n in load_failures_strp) for n in load_list}
            ds_gens[sname]   = {g: int(g in gen_failures)       for g in gens_list}
            ds_trans[sname]  = {t: 0 for t in trans_list}       # no trans failures

        #  #----- Plot Branch Failures across samples -----

        branch_fail_count = {l: 0 for l in line_list}

        for _, branch_state in ds_branch.items():
            for l, state in branch_state.items():
                if state == 1:
                    branch_fail_count[l] += 1


        freq_df_branch = pd.DataFrame(list(branch_fail_count.items()), columns=['Branch', 'Count'])
        freq_df_branch = freq_df_branch.sort_values(by='Count', ascending=False)

        plt.figure(figsize=(10, 6))
        plt.bar(range(len(freq_df_branch)), freq_df_branch['Count'])
        plt.xlabel('Branch (fbus_tbus_ckt)')
        plt.ylabel('Failure Count')
        plt.title(f'Branch Failure Frequencies Across {num_scenarios} Samples')
        plt.xticks(ticks=range(len(freq_df_branch)),labels=[g.replace('_', '-') for g in freq_df_branch['Branch']],rotation=90)
        plt.tight_layout()
        plt.show()  

    else:
        raise ValueError(f"Unknown mode: {mode}")

    return ds_gens, ds_loads, ds_trans, ds_branch

def critical_assets_identifier(mode: str, num_scenarios: int, 
                               gens, nodes_load, trans_nodes, 
                               ds_gens, ds_loads, ds_trans, 
                               frac_gens: float  = 0.25,
                               frac_loads: float = 0.10,
                               frac_trans: float = 0.05,
                               plot: bool = False, 
                               seed: int = 42):

    # ------------------------------------------------------------------
    # Mode 1: all assets are critical
    # ------------------------------------------------------------------
    
    if mode == "all":
        crit_gens   = set(gens)
        crit_loads  = set(nodes_load)
        crit_trans  = set(trans_nodes)

        print("\nNumber of Critical Loads Buses ", len(crit_loads))                                                                                                      
        print("Number of Critical Generators: ", len(crit_gens))                                                                                                                                      
        print("Number of Critical Transmission Buses: ", len(crit_trans), "\n")    

        return crit_gens, crit_loads, crit_trans
    
    # ------------------------------------------------------------------
    # Mode 2: pick from most frequently damaged assets
    # ------------------------------------------------------------------

    elif mode == "from_damaged":

        print("Getting critical assets from failure frequency: a fraction of most frequently failed assets will be chosen")
        
        #----- Loads -----

        load_fail_count = {n: 0 for n in nodes_load}
        for _, load_state in ds_loads.items():
            for n, state in load_state.items():
                if state == 1:
                    load_fail_count[n] += 1

        freq_df_load = pd.DataFrame(list(load_fail_count.items()), columns=['Load', 'Count'])
        freq_df_load = freq_df_load.sort_values(by='Count', ascending=False)

        if plot and not freq_df_load.empty:
            plt.figure(figsize=(10, 6))
            plt.bar(range(len(freq_df_load)), freq_df_load['Count'])
            plt.xlabel('Load Bus')
            plt.ylabel('Failure Count')
            plt.title(f'Load Bus Failure Frequencies Across {num_scenarios} Samples')
            plt.xticks(ticks=range(len(freq_df_load)),labels=[str(b) for b in freq_df_load['Load']],rotation=90)
            plt.tight_layout()
            plt.show()


        # #----- Generators -----

        gen_fail_count = {g: 0 for g in gens}
        for _, gen_state in ds_gens.items():
            for g, state in gen_state.items():
                if state == 1:
                    gen_fail_count[g] += 1

        freq_df_gen = pd.DataFrame(list(gen_fail_count.items()), columns=['Generator', 'Count'])
        freq_df_gen = freq_df_gen.sort_values(by='Count', ascending=False)

        if plot and not freq_df_gen.empty:
            plt.figure(figsize=(10, 6))
            plt.bar(range(len(freq_df_gen)), freq_df_gen['Count'])
            plt.xlabel('Generator (bus_fueltype)')
            plt.ylabel('Failure Count')
            plt.title(f'Generator Failure Frequencies Across {num_scenarios} Samples')
            plt.xticks(ticks=range(len(freq_df_gen)),labels=[g.replace('_', '-') for g in freq_df_gen['Generator']],rotation=90)
            plt.tight_layout()
            plt.show()  
            
        def pick_top(df, col, frac, total_assets):
            if df.empty or frac <=0:
                return set()
            k = max(1, math.ceil(total_assets * frac))
            k = min(k, len(df))
            return set(df[col].iloc[:k].tolist())
        
        crit_loads = pick_top(freq_df_load, 'Load', frac_loads, len(nodes_load))
        crit_gens  = pick_top(freq_df_gen, 'Generator', frac_gens, len(gens))
        crit_trans = trans_nodes

        print(f"\nConsidering", len(crit_loads), "critical loads buses")                                                                                                      
        print(f"Considering", len(crit_gens), "critical generators")                                                                                                                                      
        #print(f"Considering {frac_trans*100}% of transmission buses as critical for a total of", len(crit_trans), "critical transmission buses\n")    

        return crit_gens, crit_loads, crit_trans
    

    # ------------------------------------------------------------------
    # Mode 3: Random Subset of Critical Assets
    # ------------------------------------------------------------------

    if mode == "random":

        print("A random sample of assets will be selected as critical")

        random.seed(seed)

        crit_gens   = random.sample(gens,        k=min(math.ceil(       len(gens) * frac_gens),  len(gens)))
        crit_loads  = random.sample(nodes_load,  k=min(math.ceil( len(nodes_load) * frac_loads), len(nodes_load)))
        crit_trans  = random.sample(trans_nodes, k=min(math.ceil(len(trans_nodes) * frac_trans), len(trans_nodes)))

        print(f"\nConsidering", len(crit_loads), "critical loads buses")                                                                                                      
        print(f"Considering", len(crit_gens), "critical generators")                                                                                                                                        
        print(f"Considering {frac_trans*100}% of transmission buses as critical for a total of", len(crit_trans), "critical transmission buses\n")   

        return crit_gens, crit_loads, crit_trans
    

    # ------------------------------------------------------------------
    # Mode 4: From failure probabilities
    # ------------------------------------------------------------------

    if mode == "fail_prob":  ## Need to finish this bit

        print("Criritical assets will be selected based on failure probabilities")

        N = num_scenarios

        load_fail_prob = {bus: sum(ds_loads[sc][bus] for sc in ds_loads) / N for bus in nodes_load}
        gen_fail_prob  = {gen: sum(ds_gens[sc][gen] for sc in ds_gens) / N for gen in gens}

        crit_gens   = random.sample(gens,        k=min(math.ceil(       len(gens) * frac_gens),  len(gens)))
        crit_loads  = random.sample(nodes_load,  k=min(math.ceil( len(nodes_load) * frac_loads), len(nodes_load)))
        crit_trans  = random.sample(trans_nodes, k=min(math.ceil(len(trans_nodes) * frac_trans), len(trans_nodes)))

        print(f"\nConsidering", len(crit_loads), "critical loads buses")                                                                                                      
        print(f"Considering", len(crit_gens), "critical generators")                                                                                                                                        
        print(f"Considering {frac_trans*100}% of transmission buses as critical for a total of", len(crit_trans), "critical transmission buses\n")   

        return crit_gens, crit_loads, crit_trans