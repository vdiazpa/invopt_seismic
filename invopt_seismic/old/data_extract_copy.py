
import pandas as pd

def load_wecc_data_rev(gen_csv:str, bus_csv:str, branch_csv:str, ext: str, load_csv = None):
    """Load WECC data from CSV files and identify critical components.

    Args:
        gen_csv (str): Path to the generators CSV file.
        bus_csv (str): Path to the buses CSV file.
        branch_csv (str): Path to the branches CSV file.

    Returns:
        data dict type object with dicts and data to feed the optimization model.
        """
    
    gen_data  = pd.read_csv(gen_csv) 
    bus_data  = pd.read_csv(bus_csv)
    raw_line_data = pd.read_csv(branch_csv)

    gen_data['GEN UID']  = ['' for _ in range(len(gen_data))]

    #Create nodes with load set and demand dict
    nodes_load   = []
    nodes_noload = []
    demand       = {}

    bus  = 'I'
    gen_data['GEN UID']  = gen_data['I'].astype(str) + '_' + gen_data['ID']
    gens = gen_data["GEN UID"].to_list()
    nodes = bus_data[bus].to_list()


    nodes =[int(x) for x in nodes]
    bus_data[bus] = nodes
    all_nodes = bus_data[bus]
    unit_capacity  = { gens[i]: gen_data['PT'][i] for i in range(len(gens)) }

    m_data = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\m-file-data\branch_data.csv")

    k = 902 - 574 + 1
    m_line_data  = m_data.iloc[:k]                           # Only first 329 entries are lines, rest are transformers
    m_tranf_data = m_data.iloc[k:].reset_index(drop=True)    # transofrmer data in .m file is after line 329


    from collections import Counter

    m_triples   = list(zip(m_line_data.fbus, m_line_data.tbus, m_line_data.x.round(5)))
    raw_triples = list(zip(raw_line_data.I, raw_line_data.J, raw_line_data.X.round(5)))

    m_count   = Counter(m_triples)
    raw_count = Counter(raw_triples)

    matched     = m_count & raw_count 
    only_in_m   = m_count - raw_count      # extras in m
    only_in_raw = raw_count - m_count      # extras in raw

    m_line_data['x'] = m_line_data['x'].round(5)
    raw_line_data['X'] = raw_line_data['X'].round(5)

    print("Matched triples:",  sum(matched.values())) 
    print("Unmatched in m:",   only_in_m)
    print("Unmatched in raw:", only_in_raw)

    # are there any lines with same fbus, tbus, x but different rateA?
    group_cols = ['fbus', 'tbus', 'x']
    rate_unique = m_line_data.groupby(group_cols)['rateA'].transform('nunique')
    conflict_mask = rate_unique > 1
    conflicting_lines = m_line_data[conflict_mask].sort_values(group_cols + ['rateA'])
    print(conflicting_lines) 

    #create dict: key = (fbus, tbus, x) , value = rateA
    m_dict= {(row.fbus, row.tbus, row.x): row.rateA for _, row in m_line_data.iterrows()}

    # add new column with rateA from m file
    raw_line_data['rateA_m'] = raw_line_data.apply(lambda row: m_dict.get((row.I, row.J, row.X), float('nan')), axis=1)
    print(raw_line_data[raw_line_data['rateA_m'].isna()])  # lines not found in m file, 13 lines 

    # Add capacity to remaining lines. 
    m_cap_by_bus = m_line_data.groupby(['fbus', 'tbus'])['rateA'].max().to_dict()
    mask = raw_line_data['rateA_m'].isna()
    raw_line_data.loc[mask, 'rateA_m'] = raw_line_data.loc[mask].apply(lambda r: m_cap_by_bus.get((r.I, r.J), float('nan')), axis = 1)


    raw_line_data.to_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\branch_data_raw_with_rateA_m_all.csv", index=False)

# load_wecc_data_rev(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\gen_data_raw.csv", 
#                    r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\bus_data_raw.csv", 
#                    r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\branch_data_raw.csv", ext = 'raw', 
#                 load_csv = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\load_data_raw.csv" )

