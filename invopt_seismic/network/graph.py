#graph.py
import networkx as nx
from ..data_utils.structures import GridData, DamageData

def build_nx_graph_from_grid(grid: GridData):

    G = nx.Graph()
    G.add_nodes_from(grid.all_nodes)

    for line, (i,j) in grid.line_endpoints.items(): 
        G.add_edge(i,j, line=line)

    return G

def build_nx_graph_from_ds(grid: GridData, damage_states:DamageData, scenario=None):
    """
    Build a NetworkX graph drom DamageState object
    """

    if scenario is None:
        raise ValueError("scenario must be provided for DamageState")
        
    G = nx.Graph()
    G.add_nodes_from(grid.all_nodes)

    active_lines = [l for l, s in damage_states.ds_branch[scenario].items() if s == 0] # 1 is failed. 

    for line in active_lines:
        i, j = grid.line_endpoints[line]
        G.add_edge(i, j, line=line)

    return G
