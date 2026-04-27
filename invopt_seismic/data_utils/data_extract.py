#data_extract.py
import pandas as pd

def load_wecc_data_raw(gen_csv:str, bus_csv:str, branch_csv:str, load_csv = None):
    """Load WECC data from CSV files.

    Args:
        gen_csv (str): Path to the generators CSV file.
        bus_csv (str): Path to the buses CSV file.
        branch_csv (str): Path to the branches CSV file.

    Returns:
        dicts and data to feed the optimization model.
        """
    print(f"Handling raw data type input...\n")

    gen_data  = pd.read_csv(gen_csv) 
    bus_data  = pd.read_csv(bus_csv)
    line_data = pd.read_csv(branch_csv)

    #Create nodes with load set and demand dict
    nodes_load   = []
    nodes_noload = []
    demand       = {}

    bus  = 'I'
    gbus = 'I'
    fbus = 'I'
    tbus = 'J'
    reac = 'X'
    bus_kv = 'BASKV' 

    # ----------- Gens
    gen_data['ID'] = gen_data['ID'].str.replace(' ', '')                          # remove spaces from ID
    gen_data['ID'] = gen_data['ID'].str.replace("'", "", regex = False)           # remove ' from ID
    gen_data['GEN UID']  = ['' for _ in range(len(gen_data))]
    gen_data['GEN UID']  = gen_data['I'].astype(str) + '_' + gen_data['ID']       # Create unique ID for gens
    gens = gen_data["GEN UID"].to_list()
    unit_capacity  = { gens[i]: gen_data['PT'][i] for i in range(len(gens))  }


    # ----------- Buses
    nodes = bus_data[bus].to_list()
    nodes = [int(x) for x in nodes]
    bus_data[bus] = nodes
    all_nodes = bus_data[bus]

    print("Number of buses:", len(all_nodes))

    # ----------- Lines
    m_line_data = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\m-file-data\branch_data.csv")
    m_line_data['x']  = m_line_data['x'].round(5)
    line_data['CKT']  = line_data['CKT'].str.replace(' ', '')                 # remove ' from CKT name
    line_data['CKT']  = line_data['CKT'].str.replace("'", "", regex = False)  # remove spaces from ID

    others   = [i for i in range(1, 490, 4)]
    reac_ids = [i for i in range(2, 491, 4)]
    others.append([0,1,2,3])
    reac_ids.append([0,1,2,3])
    xfmr_data = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\trans_data_raw.csv", skiprows = lambda x: x not in others)
    xfmr_data_reac = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\trans_data_raw.csv", skiprows = lambda x: x not in reac_ids)
    xfmr_reactances = xfmr_data_reac['NOMV1']
    xfmr_data['X'] = xfmr_reactances
    xfmr_data.rename(columns = {"@!   R1-2": 'I', "X1-2": 'J', 'R2-3': 'CKT'}, inplace = True)
    xfmr_data['CKT'] = xfmr_data['CKT'].str.replace(' ', '')                 # remove ' from CKT name
    xfmr_data['CKT'] = xfmr_data['CKT'].str.replace("'", "")                 # remove ' from CKT name

    cols = ['I', 'J', 'CKT', 'X']
    all_lines_df = pd.concat([line_data[cols], xfmr_data[cols]], ignore_index = True) #merges transformer and line raw data with atributes of interest

    # Get capacities from m file
    #k = 902 - 574 + 1
    #m_line_data  = m_data.iloc[:k]                           # Only first 329 entries are lines, rest are transformers
    
    all_lines_df['X'] = all_lines_df['X'].round(5)   
    m_dict = {(row.fbus, row.tbus, row.x): row.rateA for _, row in m_line_data.iterrows()}
    all_lines_df['rateA_m'] = all_lines_df.apply(lambda row: m_dict.get((row.I, row.J, row.X), float('nan')), axis=1)

    m_cap_by_bus = m_line_data.groupby(['fbus', 'tbus'])['rateA'].max().to_dict()

    mask = all_lines_df['rateA_m'].isna()
    all_lines_df.loc[mask, 'rateA_m'] = all_lines_df.loc[mask].apply(lambda r: m_cap_by_bus.get((r.I, r.J), float('nan')), axis = 1)

    missing = all_lines_df['rateA_m'].isna()      # ID 3 missing transformer capacities in m file
    all_lines_df.loc[missing, 'rateA_m'] = 10000  # Assign capacity to missing values

    all_lines_df['line_id'] = [ str(all_lines_df['I'][i]) + '_' + str(all_lines_df['J'][i]) + '_' + str(all_lines_df['CKT'][i]) for i in range(len(all_lines_df)) ] # create unique id for lines

    line_capacity  = dict(zip(all_lines_df['line_id'], all_lines_df['rateA_m'].astype(float)))
    line_endpoints = dict(zip(all_lines_df['line_id'], zip(all_lines_df[fbus], all_lines_df[tbus])))
    line_reactance = dict(zip(all_lines_df['line_id'], all_lines_df[reac].astype(float)))
    lines = all_lines_df['line_id'].tolist()

    # ------------ Loads 
    load_data = pd.read_csv(load_csv)

    for i in range(len(load_data)):
        if load_data["IP"][i] >= 0: 
            nodes_load.append(load_data["I"][i])
            demand[load_data["I"][i]] = load_data["IP"][i]
        #demand[load_data["I"][i]] = abs(load_data["IP"][i])

    total_demand = sum(demand.values())
    nodes_noload = list(set(all_nodes) - set(nodes_load))
    ref_bus = max(demand, key=demand.get)  # Reference bus has higheest load

    bus_data[bus]  = bus_data[bus].apply(lambda x: int(x))      # Make sure bus IDs are int
    gen_data[gbus] = gen_data[gbus].apply(lambda x: int(x))   

    print("Total system demand:", round(total_demand,1), "MW")
    
    # ========================================================== Costs (millions)

    gen_data_capex = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\gen_data_with_types.csv", header=0)

    hardening_cost = {}            
    for i in range(len(all_nodes)): 
        if 0 <= bus_data[bus_kv][i] <= 69:
            hardening_cost[bus_data[bus][i]] = 9.4
        elif 69 < bus_data[bus_kv][i] <= 115:
            hardening_cost[bus_data[bus][i]] = 10.6
        elif 115 < bus_data[bus_kv][i] <= 138:
            hardening_cost[bus_data[bus][i]] = 11.6
        elif 138 < bus_data[bus_kv][i] <= 161:
            hardening_cost[bus_data[bus][i]] = 12.6
        elif 161 < bus_data[bus_kv][i] <= 230:
            hardening_cost[bus_data[bus][i]] = 14.0
        elif 230 < bus_data[bus_kv][i] <= 345:
            hardening_cost[bus_data[bus][i]] = 21.1
        elif 345 < bus_data[bus_kv][i] <= 500:
            hardening_cost[bus_data[bus][i]] = 30.8

    import random

    for i, gen in gen_data_capex.iterrows():
        cost =  round(gen['capex']*gen['PT']*1000 *(1/1000000)*0.2,5)
        hardening_cost[gen_data['GEN UID'][i]] = float(random.randint(9, 30))
  # Change Unit to MW, Scale to millions< multuiply by 0.25 to disaggregate capacity at each unit

    # for g in range(len(gens)): 
    #     if gen_data['PT'][g] <= 200:
    #         hardening_cost[gen_data['GEN UID'][g]] = 2
    #     elif 200 < gen_data['PT'][g] <= 800:
    #         hardening_cost[gen_data['GEN UID'][g]] = 5
    #     elif gen_data['PT'][g] > 800:
    #         hardening_cost[gen_data['GEN UID'][g]] = 10

    print(hardening_cost)

    # ========================================================== Maps
    line_to_bus = pd.DataFrame(0, index=lines, columns=all_nodes, dtype = int)
    bus_to_unit = pd.DataFrame(0, index=gens , columns=all_nodes, dtype = int)

    for lid, (i,j) in line_endpoints.items():
        line_to_bus.loc[lid, i] = -1
        line_to_bus.loc[lid, j] =  1

    for i in range(len(gens)):
        bus_to_unit.loc[(gen_data["GEN UID"][i], gen_data[gbus][i])] = 1
   
    # Dictionary to map direction of line respect to bus
    line_to_bus_dict = {(lid, b): line_to_bus.loc[lid, b] for lid in lines for b in all_nodes if line_to_bus.loc[lid, b] != 0}

    gens_by_bus = {}

    for b in bus_to_unit.columns:                                                                     #bus: tuple([gens_connected])
        gbb = []
        for g in bus_to_unit.index:
            if bus_to_unit.loc[g,b] == 1:
                gbb.append(g)
            if len(gbb) !=0:
                gens_by_bus[b] = tuple(gbb)

    lines_by_bus = { b: tuple(l for l in lines if (l, b) in line_to_bus_dict) for b in all_nodes }     #bus: tuple([lines_adjacent])

    # Dictionary to map nodes to lines adjacent & count number of lines adjacent to node
    lines_adj = {}
    bus_nlines_adj= {}
    for col in line_to_bus.columns:
        lines_adj[col] = []
        bus_nlines_adj[col] = 0
        for idx, line in enumerate(line_to_bus.index):
            if line_to_bus.loc[line, col] != 0:
                bus_nlines_adj[col] +=1
                lines_adj[col].append(lines[idx])

    gen_buses = list(set(gen_data['I']))
    load_nodes_nolines = []
    gen_nodes_nolines  = []
    unserved_load = 0
    for key in bus_nlines_adj:
        if bus_nlines_adj[key] == 0: 
            if key in nodes_load:
                load_nodes_nolines.append(key)
                unserved_load += demand[key]
            if key in gen_buses:
                gen_nodes_nolines.append(key)

    # Dictionary to map units to buses
    unit_to_bus_dict = {}  
    gen_buses = []
    for idx, unit in enumerate(bus_to_unit.index):  
        for col in bus_to_unit.columns:  
            if bus_to_unit.loc[unit, col] != 0:
                unit_to_bus_dict[unit] = col  
                if col not in gen_buses:
                    gen_buses.append(col)

    trans_nodes = list(set(all_nodes) - set(nodes_load) - set(gen_buses))

    print("Number of Load Buses:", len(nodes_load))
    print("Number of Generators: ", len(gens))
    print("Number of Transmission Nodes: ", len(trans_nodes), "\n")

    return {
        'gens': gens,
        'lines': lines,
        'all_nodes': list(all_nodes),
        'nodes_load': nodes_load,
        'nodes_noload': nodes_noload,
        'trans_nodes': list(trans_nodes),
        'bus_to_unit': bus_to_unit, 
        'line_to_bus': line_to_bus, 
        'nlines_adj': bus_nlines_adj,
        'demand': demand,  
        'unit_capacity': unit_capacity,
        'line_capacity': line_capacity,
        'line_endpoints': line_endpoints,
        'line_reactance': line_reactance,
        'line_to_bus_dict': line_to_bus_dict,
        'gens_by_bus': gens_by_bus,
        'lines_by_bus': lines_by_bus,
        'unit_to_bus_dict': unit_to_bus_dict,
        'lines_adj': lines_adj,
        'hardening_cost': hardening_cost,
        'ref_bus': ref_bus,
        }


def load_wecc_data_m(gen_csv:str, bus_csv:str, branch_csv:str):
    """Load WECC data from CSV files. 

    Args:
        gen_csv (str): Path to the generators CSV file.
        bus_csv (str): Path to the buses CSV file.
        branch_csv (str): Path to the branches CSV file.

    Returns:
        dicts and data to feed the optimization model.
        """
    
    gen_data  = pd.read_csv(gen_csv) 
    bus_data  = pd.read_csv(bus_csv)
    line_data = pd.read_csv(branch_csv)

    #Create nodes with load set and demand dict
    nodes_load   = []
    nodes_noload = []
    demand       = {}

    bus  = 'bus_i'
    gbus = 'bus'
    fbus = 'fbus'
    tbus = 'tbus'
    reac = 'x'
    bus_kv = 'baseKV'

     # ----------- Buses
    nodes = bus_data[bus].to_list()
    nodes =[int(x) for x in nodes]
    bus_data[bus] = nodes
    all_nodes = bus_data[bus]

     # ----------- Gens
    gen_data['GEN UID']  = ['' for _ in range(len(gen_data))]
    nodes = bus_data[bus].to_list()
    nodes =[int(x) for x in nodes]
    fuel_type = list(set([str(x) for x in gen_data["fuel_type"]]))

    counts = { (b, t): 1 for b in all_nodes for t in fuel_type } #Add gen name: bus_fueltype_count 
    for g in range(len(gen_data)):
        gen_name = ''
        bus_i  = int(gen_data.at[g, 'bus'])
        type   = str(gen_data.at[g, 'fuel_type'])
        gen_name = str(bus_i) + '_' + str(type) + '_' + str(counts[(bus_i, type)])
        counts[(bus_i, type)] += 1
        gen_data.at[g, 'GEN UID'] = gen_name

    gens = gen_data["GEN UID"].to_list()
    unit_capacity  = { gen_data['GEN UID'][i]: gen_data['Pmax'][i] for i in range(len(gens))  }
        
    # ----------- Lines    
    # k = 902 - 574 + 1
    # line_data  = line_data.iloc[:k]                           # Only first 329 entries are lines, rest are transformers
    line_data['CKT'] = line_data.groupby([fbus, tbus]).cumcount() # Created a unique ID for parallel lines
    line_data['line_id'] = (line_data[fbus].astype(str) + '_' + line_data[tbus].astype(str) + '_' + line_data['CKT'].astype(str) )
    line_capacity  = dict(zip(line_data['line_id'], line_data['rateA'].astype(float)))
    line_endpoints = dict(zip(line_data['line_id'], zip(line_data[fbus], line_data[tbus])))
    line_reactance = dict(zip(line_data['line_id'], line_data[reac].astype(float)))
    lines = line_data['line_id'].tolist()

    # ----------- Loads  
    for i in range(len(all_nodes)):
        if bus_data["type"][i] == 1.0 and bus_data["Pd"][i] != 0:
            nodes_load.append(bus_data["bus_i"][i])
            demand[bus_data["bus_i"][i]] = abs(bus_data["Pd"][i])
        else:
            demand[bus_data["bus_i"][i]] = 0
            nodes_noload.append(bus_data["bus_i"][i])
    
    ref_bus = max(demand, key=demand.get)  # Reference bus has higheest load

    bus_data[bus] = bus_data[bus].apply(lambda x: int(x))      # Make sure bus IDs are int
    gen_data[gbus] = gen_data[gbus].apply(lambda x: int(x))   

    print(f"\nHandling m data type input")

    # ----------- Costs (millions)  
    hardening_cost = {} 
    for i in range(len(all_nodes)): 
        if 0 <= bus_data[bus_kv][i] <= 69:
            hardening_cost[bus_data[bus][i]] = 9.4
        elif 69 < bus_data[bus_kv][i] <= 115:
            hardening_cost[bus_data[bus][i]] = 10.6
        elif 115 < bus_data[bus_kv][i] <= 138:
            hardening_cost[bus_data[bus][i]] = 11.6
        elif 138 < bus_data[bus_kv][i] <= 161:
            hardening_cost[bus_data[bus][i]] = 12.6
        elif 161 < bus_data[bus_kv][i] <= 230:
            hardening_cost[bus_data[bus][i]] = 14.5
        elif 230 < bus_data[bus_kv][i] <= 345:
            hardening_cost[bus_data[bus][i]] = 21.1
        elif 345 < bus_data[bus_kv][i] <= 500:
            hardening_cost[bus_data[bus][i]] = 30.8

    # Create line-to-bus (incidence matrix) & Bus-to-unit (adjacency matrix) Maps
    line_to_bus = pd.DataFrame(0, index=lines, columns=all_nodes, dtype = int)
    bus_to_unit = pd.DataFrame(0, index=gens , columns=all_nodes, dtype = int)

    for lid, (i,j) in line_endpoints.items():
        line_to_bus.loc[lid, i] = -1
        line_to_bus.loc[lid, j] =  1

    for i in range(len(gens)):
        bus_to_unit.loc[(gen_data["GEN UID"][i], gen_data[gbus][i])] = 1

    # Dictionary to map direction of line respect to bus
    line_to_bus_dict = {(lid, b): line_to_bus.loc[lid, b] for lid in lines for b in all_nodes if line_to_bus.loc[lid, b] != 0}

    gens_by_bus = {}

    for b in bus_to_unit.columns:
        gbb = []
        for g in bus_to_unit.index:
            if bus_to_unit.loc[g,b] == 1:
                gbb.append(g)
            if len(gbb) !=0:
                gens_by_bus[b] = tuple(gbb)

    lines_by_bus = { b: tuple(l for l in lines if (l, b) in line_to_bus_dict) for b in all_nodes }     #bus: tuple(lines_adjacent)

    # Dictionary to map nodes to lines adjacent & count number of lines adjacent to node
    lines_adj = {}
    bus_nlines_adj= {}
    for col in line_to_bus.columns:
        lines_adj[col] = []
        bus_nlines_adj[col] = 0
        for idx, line in enumerate(line_to_bus.index):
            if line_to_bus.loc[line, col] != 0:
                bus_nlines_adj[col] +=1
                lines_adj[col].append(lines[idx])

    # line_to_bus.to_csv(f"linetobus_WECC_{ext}.csv", header=1)
    # bus_to_unit.to_csv(f"bustounit_WECC_{ext}.csv", header=1)

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

    trans_nodes = list(set(all_nodes) - set(nodes_load) - set(gen_buses))
    print(trans_nodes)

    print("\nNumber of Load Buses:", len(nodes_load))
    print("Number of Generators: ", len(gens))
    print("Number of Transmission Nodes: ", len(trans_nodes), "\n")

    return {
        'gens': gens,
        'lines': lines,
        'all_nodes': list(all_nodes),
        'nodes_load': nodes_load,
        'nodes_noload': nodes_noload,
        'trans_nodes': list(trans_nodes),
        'demand': demand,  
        'unit_capacity': unit_capacity,
        'line_capacity': line_capacity,
        'line_endpoints': line_endpoints,
        'line_reactance': line_reactance,
        'line_to_bus_dict': line_to_bus_dict,
        'gens_by_bus': gens_by_bus,
        'lines_by_bus': lines_by_bus,
        'unit_to_bus_dict': unit_to_bus_dict,
        'lines_adj': lines_adj,
        'hardening_cost': hardening_cost,
        'ref_bus': ref_bus,
        }


def load_rts_data():
    
    # Read data
    gen_data  = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\RTS_data\\gen_data.csv", header=0)
    bus_data  = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\RTS_data\\bus_data.csv", header=0)
    line_data = pd.read_csv("C:\\Users\\vdiazpa\\Documents\\quest_planning\\quest_planning\\seismic_model\\RTS_data\\branch_data.csv", header=0)

    nodes_load = []
    nodes_noload = []
    demand = {}

    # ----------- Gens
    gens = gen_data["GEN UID"].to_list()
    unit_capacity  = {gens[i]: gen_data["PMax MW"][i] for i in range(len(gens))}

    # ----------- Lines
    lines = [line_data["UID"][i] for i in range(len(line_data))]
    line_reactance = {lines[i]: line_data["X"][i] for i in range(len(lines))}
    line_capacity  = {lines[i]: line_data["Cont Rating"][i] for i in range(len(lines))}
    line_endpoints = {lines[i]: (line_data['From Bus'][i], line_data['To Bus'][i]) for i in range(len(lines))}

    # ----------- Buses/Loads
    all_nodes = bus_data["Bus ID"].unique()

    for i in range(len(all_nodes)):
        if bus_data["Bus Type"][i] == "PV" and bus_data["MW Load"][i] != 0:
            nodes_load.append(bus_data["Bus ID"][i])
            demand[bus_data["Bus ID"][i]] = bus_data["MW Load"][i]
        else:
            demand[bus_data["Bus ID"][i]] = 0
            nodes_noload.append(bus_data["Bus ID"][i])

    nodes_noload = list(set(all_nodes) - set(nodes_load))
    ref_bus = max(demand, key=demand.get)  # Reference bus has highest load

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

    # Create line-to-bus (adjacency matrix) and bus-to-unit (adjacency matrix) Maps
    line_to_bus = pd.DataFrame(0, index=lines, columns=all_nodes, dtype = int)
    bus_to_unit = pd.DataFrame(0, index=gens, columns=all_nodes, dtype = int)

    for lid, (i,j) in line_endpoints.items():
        line_to_bus.loc[lid, i] = -1
        line_to_bus.loc[lid, j] =  1

    for i in range(len(gens)):
        bus_to_unit.loc[(gen_data["GEN UID"][i], gen_data["Bus ID"][i])] = 1

    # Dictionary to map direction of line respect to bus
    # line_to_bus_dict = {}
    # for idx, line in enumerate(line_to_bus.index):
    #     for col in line_to_bus.columns:
    #         line_to_bus_dict[(lines_list[idx], col)] = line_to_bus.loc[(line, col)]

    # Dictionary to map direction of line respect to bus
    line_to_bus_dict = {(lid, b): line_to_bus.loc[lid, b] for lid in lines for b in all_nodes if line_to_bus.loc[lid, b] != 0}

    gens_by_bus = {}

    for b in bus_to_unit.columns:
        gbb = []
        for g in bus_to_unit.index:
            if bus_to_unit.loc[g,b] == 1:
                gbb.append(g)
            if len(gbb) !=0:
                gens_by_bus[b] = tuple(gbb)

    lines_by_bus = { b: tuple(l for l in lines if (l, b) in line_to_bus_dict) for b in all_nodes }     #bus: tuple(lines_adjacent)

    # Dictionary to map nodes to lines adjacent & count number of lines adjacent to node
    lines_adj = {}
    bus_nlines_adj= {}
    for col in line_to_bus.columns:
        lines_adj[col] = []
        bus_nlines_adj[col] = 0
        for idx, line in enumerate(line_to_bus.index):
            if line_to_bus.loc[line, col] != 0:
                bus_nlines_adj[col] +=1
                lines_adj[col].append(lines[idx])

    # line_to_bus.to_csv(f"linetobus_WECC_{ext}.csv", header=1)
    # bus_to_unit.to_csv(f"bustounit_WECC_{ext}.csv", header=1)

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

    return {
        'gens': gens,
        'lines': lines,
        'all_nodes': list(all_nodes),
        'nodes_load': nodes_load,
        'nodes_noload': nodes_noload,
        'demand': demand,  
        'unit_capacity': unit_capacity,
        'line_capacity': line_capacity,
        'line_endpoints': line_endpoints,
        'line_reactance': line_reactance,
        'line_to_bus_dict': line_to_bus_dict,
        'trans_nodes': list(trans_nodes),
        'gens_by_bus': gens_by_bus,
        'lines_by_bus': lines_by_bus,
        'unit_to_bus_dict': unit_to_bus_dict,
        'lines_adj': lines_adj,
        'ref_bus': ref_bus,
        }

