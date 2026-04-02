#critical.py
from ..data_utils.structures import as_damage_data, DamageData, GridData, CriticalAssets
import pandas as pd
import random
import math

def critical_assets_identifier(
            mode: str, 
            grid: GridData,
            damage_states: DamageData,
            frac_gens:  float = 0.25,
            frac_loads: float = 0.10,
            frac_trans: float = 0.05,
            seed: int  = False, 
            bus_in_poly: list = None):
    
    """Identify critical assets based on different modes.
    """

    gens  = grid.gens
    nodes_load  = grid.nodes_load
    trans_nodes = grid.trans_nodes

    # ------------------------------------------------------------------
    # Mode 1: all assets are critical
    # ------------------------------------------------------------------ 

    if mode == "all":

        print("\nAll assets are considered critical") 
        crit_gens   = list(gens)
        crit_loads  = list(nodes_load)
        crit_trans  = list(trans_nodes)
                                                                                   
        return CriticalAssets(crit_gens, crit_loads, crit_trans)
    
    # ------------------------------------------------------------------
    # Mode 2: pick from most frequently damaged assets
    # ------------------------------------------------------------------ 

    elif mode == "from_damaged":

        print("Getting critical assets from failure frequency: a fraction of most frequently failed assets will be chosen")
        
        def _freq_df(ds_dict, asset_col_name):
                """Compute frequency dataframe from damage state dictionary."""
                if not ds_dict:
                    return pd.DataFrame(columns=[asset_col_name, 'Count'])
                
                keys = list(next(iter(ds_dict.values())).keys())
                fail_count = {k: 0 for k in keys}
                for _, state_map in ds_dict.items():
                    for k, v in state_map.items():
                        if v == 1:
                            fail_count[k] += 1
                freq_df = pd.DataFrame(list(fail_count.items()), columns=[asset_col_name, 'Count'])
                return freq_df.sort_values(by='Count', ascending=False)

        #----- Loads -----
        freq_df_load = _freq_df(damage_states.ds_loads, 'Load')   # Define what the df frequency is. 

        #----- Generators -----
        freq_df_gen = _freq_df(damage_states.ds_gens, 'Generator')

        def pick_top(df, col, frac, total_assets, failing_only=False):
            if df.empty or frac <=0:
                return set()
            
            if failing_only:
                df = df[df['Count'] > 0].copy()
                if df.empty:
                    return set()
                k = max(1, math.ceil(len(df) * frac))  # <--fraction of failing assets only
            else:
                k = max(1, math.ceil(total_assets * frac))

            k = min(k, len(df))
            return set(df[col].iloc[:k].tolist())
        
        crit_loads = pick_top(freq_df_load, 'Load', frac_loads, len(nodes_load), failing_only=True)
        crit_gens  = pick_top(freq_df_gen, 'Generator', frac_gens, len(gens), failing_only=True)
        crit_trans = trans_nodes

        print(f"\nConsidering", len(crit_loads), "critical loads buses")                                                                                                      
        print(f"Considering", len(crit_gens), "critical generators")                                                                                                                                      
        #print(f"Considering {frac_trans*100}% of transmission buses as critical for a total of", len(crit_trans), "critical transmission buses\n")    

        return CriticalAssets(crit_gens, crit_loads, crit_trans)
    

    # ------------------------------------------------------------------
    # Mode 3: Random Subset of Critical Assets
    # ------------------------------------------------------------------

    elif mode == "random":

        print("A random sample of assets will be selected as critical")

        random.seed(seed)

        crit_gens   = random.sample(gens,        k=min(math.ceil(       len(gens) * frac_gens),  len(gens)))
        crit_loads  = random.sample(nodes_load,  k=min(math.ceil( len(nodes_load) * frac_loads), len(nodes_load)))
        crit_trans  = random.sample(trans_nodes, k=min(math.ceil(len(trans_nodes) * frac_trans), len(trans_nodes)))

        print(f"\nConsidering", len(crit_loads), "critical loads buses")                                                                                                      
        print(f"Considering", len(crit_gens), "critical generators")                                                                                                                                        
        print(f"Considering {frac_trans*100}% of transmission buses as critical for a total of", len(crit_trans), "critical transmission buses\n")   

        return CriticalAssets(crit_gens, crit_loads, crit_trans)
    

    # ------------------------------------------------------------------
    # Mode 4: From failure probabilities
    # ------------------------------------------------------------------

    elif mode == "fail_prob":  ## Need to finish this bit

        print("Criritical assets will be selected based on failure probabilities")

        N = len(damage_states.ds_gens)

        load_fail_prob = {bus: sum(damage_states.ds_loads[sc][bus] for sc in damage_states.ds_loads) / N for bus in nodes_load}
        gen_fail_prob  = {gen: sum(damage_states.ds_gens[sc][gen] for sc in damage_states.ds_gens) / N for gen in gens}

        crit_gens   = random.sample(gens,        k=min(math.ceil(       len(gens) * frac_gens),  len(gens)))
        crit_loads  = random.sample(nodes_load,  k=min(math.ceil( len(nodes_load) * frac_loads), len(nodes_load)))
        crit_trans  = random.sample(trans_nodes, k=min(math.ceil(len(trans_nodes) * frac_trans), len(trans_nodes)))

        print(f"\nConsidering", len(crit_loads), "critical loads buses")                                                                                                      
        print(f"Considering", len(crit_gens), "critical generators")                                                                                                                                        
        print(f"Considering {frac_trans*100}% of transmission buses as critical for a total of", len(crit_trans), "critical transmission buses\n")   

        return crit_gens, crit_loads, crit_trans
    
    elif mode == "all_in_polygon": 
        print("All assets inside polygon are considered critical") 

        if bus_in_poly is None:
            raise ValueError("bus_in_poly must be provided for 'all_in_polygon' mode")
        
        gens_by_bus = grid.gens_by_bus

        crit_gens = []
        for b, gens_tup in gens_by_bus.items():
            if b in bus_in_poly:
                crit_gens.extend(gens_tup)

        crit_loads = [n for n in grid.nodes_load if n in bus_in_poly]
        crit_trans = [t for t in grid.trans_nodes if t in bus_in_poly]

        return CriticalAssets(crit_gens, crit_loads, crit_trans)

