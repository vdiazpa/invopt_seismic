            
import pandas as pd

def extract_raw_lines(raw_path):

    colnames = []
    data_frames = {}
    k = 0
    p = 1
    current_rows = []
    attribute_list = []
    current_section = None

    with open(raw_path, 'r', errors='ignore') as f:
        for lineno, line in enumerate(f, start=1):
            stripped = line.strip()
            upper = stripped.upper()

            if 'BEGIN TWO_TERMINAL' in upper:
                # flush the last section before breaking
                if current_section is not None and current_rows:
                    data_frames[current_section] = pd.DataFrame(current_rows, columns=attribute_list)
                break
           
            # Detect BEGIN <SECTION> DATA anywhere in the line
            if "BEGIN" in upper and "DATA" in upper:
                # flush previous section (if it had rows)
                if current_section is not None and current_rows:
                    data_frames[current_section] = pd.DataFrame(current_rows, columns=attribute_list)
                    current_rows = []

                k = 1
                attribute_list = []
                current_section = upper.split('BEGIN ', 1)[1].split(' DATA', 1)[0].strip()
                print(f"Beggining {current_section} section")
                p = 1
                continue   # go to next line

            k -= 1

            if k == 0:
                try:
                    if "@" in line:
                        parts = line.split("@", 1)[1].strip()
                    elif line.strip().startswith("!"):
                        parts = line.strip().lstrip("!").strip()
                    else:
                        parts = line.strip()
                    # normalize and split into attribute names
                    parts = parts.lstrip("!").strip()
                    attribute_list = [attr.strip().strip("'\"") for attr in parts.split(",") if attr.strip()]
                except Exception as e:
                    # fallback: skip this attribute line and log (prevents IndexError)
                    print(f"Warning parsing attribute line {lineno}: {e}; line={line!r}")
                    attribute_list = []
                colnames.append(attribute_list)
                print(f"appending {current_section} attributes:", attribute_list)
                p -= 1
                continue

            # data lines
            if p < 1 and k < 0:
                row = [x.strip() for x in line.split(',')]

                # pad/trim row to match number of attributes
                if attribute_list:
                    n = len(attribute_list)
                    if len(row) < n:
                        row += [""] * (n - len(row))
                    elif len(row) > n:
                        row = row[:n]

                current_rows.append(row)

    # flush last section if file ended without BEGIN TWO_TERMINAL
    if current_section is not None and current_rows:
        data_frames[current_section] = pd.DataFrame(current_rows, columns=attribute_list)

    return data_frames

from pathlib import Path

raw_path = Path(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\240busWECC_2018_PSS.raw")
data_frames = extract_raw_lines(raw_path)

out_dir = raw_path.parent
for section, df in data_frames.items():
    safe_name = section.replace("", "_")
    out_file = out_dir/ f"{safe_name}.csv"
    df.to_csv(out_file, index=False)
    print(f"Saved {section} data to {out_file}")

# from pathlib import Path
# raw_path = Path(r"C:\Users\vdiazpa\Downloads\240busWECC_2018_PSS_processed.raw")
