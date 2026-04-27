#run_dcopf.py
from invopt_seismic.data_utils.data_extract import load_wecc_data_raw
from invopt_seismic.data_utils.structures import as_grid_data
from invopt_seismic.opt.dcopf import solve_dc_opf, extract_solution

def main():
    data = load_wecc_data_raw(
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\gen_data_raw.csv",
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\bus_data_raw.csv",
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\branch_data_raw_with_rateA_m_all.csv",
        load_csv=r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\load_data_raw.csv")
    grid = as_grid_data(data)

    m, res, obj = solve_dc_opf(grid, solver="gurobi", tee=False)
    print("DCOPF objective:", round(obj, 2))

    df = extract_solution(m)
    df.to_csv(r"\Users\vdiazpa\Documents\DCOPF_solution.csv", index=False)

if __name__ == "__main__":
    main()