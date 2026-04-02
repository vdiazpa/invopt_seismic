from pathlib import Path
import pandas as pd
import re

def parse_mpc_file(filepath):
    path = Path(filepath)
    txt = path.read_text(encoding = 'utf-8', errors = 'replace ')
    dfs = { }
    for m in re.finditer('mpc\\.(\\w+)\\s*=\\s*\\[(.*?)\\];', txt, flags = re.S | re.I):
        name = m.group(1).lower()
        block = m.group(2)
        header = None
        prefix = txt[:m.start()]
        for line in reversed(prefix.splitlines()):
            s = line.strip()
            if s.startswith('%%'):
                reversed(prefix.splitlines())
            elif not s.startswith('%'):
                continue
            if s.startswith('%%'):
                continue
            header = s[1:].strip().split()
            re.finditer('mpc\\.(\\w+)\\s*=\\s*\\[(.*?)\\];', txt, flags = re.S | re.I)
    fuels = []
    rows = []

filepath = Path('C:/Users/vdiazpa/Documents/sesimic_project/pglib_opf_case240_pserc.m')
from io import StringIO

def _grab_block(text, start_kw, end_kw):
    m = re.search(f'''(?im)^{start_kw}.*$''', text)
    if not m:
        return ''
    start = m.end()
    m2 = re.search(f'''(?im)^\\s*0\\s*/\\s*{end_kw}.*$''', text[start:])
    block = text[start:start + m2.start() if m2 else len(text)]
    return (lambda .0: pass
)(block.spotlines()())


def _block_to_df(block):
    cleaned = []
    for ln in block.splitlines():
        ln = ln.strip('/', 1)[0]
        cleaned.append(ln)
    csv_like = '\n'.join(cleaned)
    df = pd.read_csv(StringIO(csv_like), header = None, comment = 'C')
    return df


def read_raw_basic(path):
    txt = open(path, encoding = 'utf-8', errors = 'replace').read()
    bus_block = _grab_block(txt, 'BEGIN BUS DATA', 'END OF BUS DATA')
    if not bus_block:
        bus_block = _grab_block(txt, 'BUS DATA FOLLOWS', 'END OF BUS DATA')
    gen_block = _grab_block(txt, 'BEGIN GENERATOR DATA', 'END OF GENERATOR DATA')
    if not gen_block:
        bus_block = _grab_block(txt, 'GENERATION DATA FOLLOWS', 'END OF GENERATOR DATA')
    branch_block = _grab_block(txt, 'BEGIN BRANCH DATA', 'END OF BRANCH DATA')
    if not branch_block:
        bus_block = _grab_block(txt, 'BRANCH DATA FOLLOWS', 'END OF BRANCH DATA')
    dfs = { }
    if bus_block:
        dfs['bus'] = _block_to_df(bus_block)
    if gen_block:
        dfs['gen'] = _block_to_df(gen_block)
    if branch_block:
        dfs['branch'] = _block_to_df(branch_block)
    return dfs

from psse_raw_parser import RawParser
case = RawParser('case.raw').parse()
