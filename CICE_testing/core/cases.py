"""Stable case IDs, organised configuration paths and unchanged run archives."""
import json
import re
from pathlib import Path


def classification(name):
    if name == 'dyntens_box01': return 'box01_tests', 'B0', name
    if name == 'dyntens01': return 'global_tests', 'G0', name
    match = re.fullmatch(r'dt_(b67|b6)_(s1|s2|m2)', name)
    if match:
        band = '67' if match[1] == 'b67' else '6'
        return 'box01_tests', 'B3', 'dt_b3_band'+band+'_'+match[2]
    for prefix, stage in [('dt_b4_', 'B4'), ('dt_b5_', 'B5'), ('dt_b63_', 'B6.3'),
                          ('dt_b64_', 'B6.4'), ('dt_b65f_', 'B6.5-F'),
                          ('dt_b65_', 'B6.5'), ('dt_b66_', 'B6.6')]:
        if name.startswith(prefix): return 'box01_tests', stage, name
    if re.fullmatch(r'dt_b3_band(?:67|6)_(?:s1|s2|m2)', name):
        return 'box01_tests', 'B3', name
    raise ValueError('unclassified case: '+name)


def organised_path(repo, name):
    root, stage, canonical = classification(name)
    return Path(repo)/root/stage/canonical


def case_path(repo, name):
    """Read either layout; create organised cases when the registry is present."""
    repo=Path(repo)
    nested=organised_path(repo,name); legacy=repo/name
    if legacy.exists() and nested.exists():
        raise ValueError('ambiguous legacy/organised case: '+name)
    if legacy.exists(): return legacy
    if nested.exists() or (repo/'box01_tests/cases.json').is_file(): return nested
    return legacy


def diagnostic_cases(repo):
    repo=Path(repo)
    paths=list(repo.glob('dt_b63*/ice_in'))+list(repo.glob('box01_tests/B6.3/dt_b63*/ice_in'))
    return sorted(paths)


def retarget_text(text, moves, rename=None):
    # Longest paths first. Boundaries prevent rewriting similarly named cases.
    for old,new in sorted(moves.items(),key=lambda item:len(item[0]),reverse=True):
        text=re.sub(re.escape(old)+r'(?=$|[/\s\"\'\)\]}:])',lambda m:new,text)
    if rename:
        old,new=rename
        text=re.sub(r'(?m)^(\s*setenv\s+ICE_CASENAME\s+)'+re.escape(old)+r'(?=\s|$)',
                    lambda m:m[1]+new,text)
        text=re.sub(r'(?m)^(#PBS\s+-N\s+)'+re.escape(old)+r'(?=\s|$)',
                    lambda m:m[1]+new,text)
    return text


def verify_input_hash(case, filename, expected):
    """Accept only a recorded, reproducible path edit to an immutable input."""
    from .reporting import sha256
    case=Path(case); current=case/filename
    if sha256(current)==expected: return True
    ledger=case/'case-migration/record.json'
    if not ledger.is_file(): return False
    record=json.loads(ledger.read_text())
    entry=record['files'].get(filename)
    original=case/'case-migration/original'/filename
    if not entry or not original.is_file() or sha256(original)!=expected: return False
    if entry['before_sha256']!=expected or sha256(current)!=entry['after_sha256']: return False
    transformed=retarget_text(original.read_bytes().decode(),record['moves'],record.get('rename'))
    return current.read_bytes()==transformed.encode()
