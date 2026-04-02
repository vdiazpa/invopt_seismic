#seismic_experiment.py
from data_utils import GridData, DamageData, CriticalAssets
from inv_opt import model_build_solve

class SeismicPlanningExperiment:
    "High-level interface for Seismic InvOpt experiments."
    
    def _init_(
        self, 
        grid: GridData, 
        hard_frac: float,
        damage_states: DamageData, 
        critical_assets: CriticalAssets ):

        self.grid = grid
        self.damage_states = damage_states, 
        self.critical_assets = critical_assets,
        self.hard_frac = hard_frac,  


    def solve(
        self, 
        form: str = "risk_neutral", 
        tau: float = 0.5, 
        alpha: float = 0.95,
        lam: float = 1.0, 
        max_invest = None, 
        mip_gap: float = 0.01, 
        tee: bool = False, 
        print_vars: bool = True, 
        time_solve: bool = True):

        "Solve problem given formulation and experimental parameters"

        results = model_build_solve(
            form=form, 
            grid = self.grid, 
            hard_frac = self.hard_frac, 
            damage_state = self.damage_states, 
            crit_assets = self.critical_assets, 
            tau=tau, 
            alpha= alpha, 
            lam = lam, 
            max_invest = self.max_invest, 
            mip_gap=mip_gap, 
            tee=tee, 
            print_vars=print_vars, 
            time_solve=time_solve)
        
        return results