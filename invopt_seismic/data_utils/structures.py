
# data_utils.py
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any

@dataclass(frozen=True)
class GridData:
    gens: List[Any]
    lines: List[Any]
    demand: Dict[Any, float]
    ref_bus: Any
    all_nodes: List[Any]
    lines_adj: Dict[Any, List[Any]]
    nodes_load: List[Any]
    gens_by_bus: Dict[Any, Tuple[Any, ...]]
    trans_nodes: List[Any]
    lines_by_bus: Dict[Any, Tuple[Any, ...]]
    nlines_adj: Dict[Any, int]
    line_capacity: Dict[Any, float]
    unit_capacity: Dict[Any, float]
    line_reactance: Dict[Any, float]
    hardening_cost: Dict[Any, float]
    line_endpoints: Dict[Any, Tuple[Any, Any]]
    line_to_bus_dict: Dict[Tuple[Any, Any], int]
    unit_to_bus_dict: Dict[Any, Any]

@dataclass(frozen=False)
class DamageData:
    ds_gens:   Dict[str, Dict[Any, int]]
    ds_loads:  Dict[str, Dict[Any, int]]
    ds_trans:  Dict[str, Dict[Any, int]]
    ds_branch: Dict[str, Dict[Any, int]]

@dataclass
class CriticalAssets:
    gens:   List[Any]
    loads:  List[Any]
    trans:  List[Any]

def as_grid_data(data: dict) -> GridData:
    return GridData(**{k: data[k] for k in GridData.__annotations__.keys()})      # only pick the keys GridData declares

def as_damage_data(ds_gens: dict, ds_loads: dict, ds_trans: dict, ds_branch: dict) -> DamageData:
    return DamageData(ds_gens=ds_gens, ds_loads = ds_loads, ds_trans=ds_trans, ds_branch=ds_branch)     
