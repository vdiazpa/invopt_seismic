import pandas as pd
import pyomo.environ as pyo
from pyomo.environ import SolverFactory

from ..data_utils.structures import GridData

def build_dc_opf(grid: GridData):
    m = pyo.ConcreteModel()

    gens       = grid.gens
    demand     = grid.demand
    ref_bus    = grid.ref_bus
    lines      = grid.lines
    all_nodes  = grid.all_nodes
    nodes_load = grid.nodes_load

    m.PowerGenerated = pyo.Var(gens, within=pyo.NonNegativeReals)
    m.LoadShedding   = pyo.Var(nodes_load, within=pyo.NonNegativeReals)
    m.VoltAngle      = pyo.Var(all_nodes, within=pyo.Reals, bounds=(-180, 180))
    m.PowerFlow      = pyo.Var(lines, within=pyo.Reals)

    m.UnitCap = pyo.Constraint(gens, rule=lambda m,g: m.PowerGenerated[g] <= grid.unit_capacity[g])

    m.Flow = pyo.Constraint(
        lines,
        rule=lambda m,l: m.PowerFlow[l] * grid.line_reactance[l]
                         == m.VoltAngle[grid.line_endpoints[l][0]] - m.VoltAngle[grid.line_endpoints[l][1]])

    m.RefBus = pyo.Constraint(expr=m.VoltAngle[ref_bus] == 0)
    m.FlowUB = pyo.Constraint(lines, rule=lambda m,l: m.PowerFlow[l] <=  grid.line_capacity[l])
    m.FlowLB = pyo.Constraint(lines, rule=lambda m,l: m.PowerFlow[l] >= -grid.line_capacity[l])

    def nodal_balance(m, b):
        thermal = sum(m.PowerGenerated[g] for g in grid.gens_by_bus.get(b, ()))
        flows   = sum(m.PowerFlow[l] * grid.line_to_bus_dict[(l, b)] for l in grid.lines_by_bus[b])
        shed    = m.LoadShedding[b] if b in nodes_load else 0.0
        return thermal + flows + shed == demand.get(b, 0.0)
    m.NodalBalance = pyo.Constraint(all_nodes, rule=nodal_balance)

    m.ShedUB = pyo.Constraint(nodes_load, rule=lambda m,b: m.LoadShedding[b] <= demand[b])

    m.Obj = pyo.Objective(expr=sum(5000 * m.LoadShedding[b] for b in nodes_load), sense=pyo.minimize)

    return m


def solve_dc_opf(grid: GridData, solver="gurobi", tee=False):
    m = build_dc_opf(grid)
    res = SolverFactory(solver).solve(m, tee=tee)
    obj = pyo.value(m.Obj)
    return m, res, obj


def extract_solution(m) -> pd.DataFrame:
    rows = []
    for v in m.component_data_objects(pyo.Var, active=True):
        rows.append({
            "var": v.parent_component().name,
            "index": str(v.index()),
            "value": None if v.value is None else float(v.value)})
    return pd.DataFrame(rows)