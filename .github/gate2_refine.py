from pathlib import Path
import re

root = Path(__file__).resolve().parents[1] / 'docs' / 'verification'

master_path = root / 'MASTER_VERIFICATION_INDEX.md'
master = master_path.read_text(encoding='utf-8')
master = master.replace(
    '- prescribed-subcooled outlet boundary Increment 1: `IMPLEMENTED; SOFTWARE-VERIFIED;\n  MERGED` in PR #75',
    '- prescribed-subcooled outlet boundary Increment 1: `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` in PR #75',
)
master = master.replace(
    '- fixed 128-cell CFL-sensitivity contract and exact CFL 0.10 replay: `IMPLEMENTED;\n  SOFTWARE-VERIFIED; MERGED` in PR #84',
    '- fixed 128-cell CFL-sensitivity contract and exact CFL 0.10 replay: `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` in PR #84',
)
needle = '- prescribed-subcooled outlet boundary Increment 1: `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` in PR #75\n'
extra = (
    needle
    + '- boundary-path preflight: `195 / 195 ACCEPTED LIQUID_CANDIDATE`\n'
    + '- first-order liquid-to-open-two-phase software crossing: `VERIFIED`\n'
    + '- frozen Case A/B retained as the first-order crossing regression control\n'
)
if '- boundary-path preflight: `195 / 195 ACCEPTED LIQUID_CANDIDATE`' not in master.split('## Stage 7 milestone index', 1)[0]:
    if needle not in master:
        raise RuntimeError('master PR #75 current-state line not found')
    master = master.replace(needle, extra, 1)
master_path.write_text(master, encoding='utf-8')

log_path = root / 'stage7_execution_log.md'
log = log_path.read_text(encoding='utf-8')
expanded_support = '''The HEM verification path on recorded substantive development `main`
`827d99bce97cea2785aa3334b3f5e950389c9aad` now supports:

- guarded pure-CO2 `rho/e` thermodynamic evaluation;
- explicit phase classification and raw boundary-region transition detection;
- an independently defined equilibrium sound-speed candidate;
- first-order Rusanov/CFL operation on liquid and open-two-phase accepted states;
- exact uniform open-two-phase preservation;
- dynamic transported/equilibrium-quality synchronization;
- projection activation and true no-op behavior;
- mixed liquid/open-two-phase accepted-state recovery;
- actual raw liquid-to-open-two-phase crossing from an all-liquid initial state;
- post-crossing projection, EOS recovery, second-projection no-op, and vapor-budget closure;
- deterministic repeated Case A crossing and exact matched-time all-liquid Case B;
- frozen first-order Case A/B software-regression controls;
- a prescribed-subcooled outlet with 195/195 accepted boundary preflight samples;
- a fixed boundary-driven 2/3/4 MPa pipeline first-crossing matrix;
- a fixed 4 MPa forensic diagnosis retaining the raw observation without threshold tuning;
- a fixed 32/64/128-cell mesh-sensitivity matrix at CFL 0.10;
- a fixed 128-cell CFL contract with exact CFL 0.10 baseline replay and traceable artifacts.

'''
pattern = r'The HEM verification path on recorded substantive development `main`\n`827d99bce97cea2785aa3334b3f5e950389c9aad` now supports:\n\n.*?\n\n(?=The current evidence does not support the following claims:)'
log, count = re.subn(pattern, expanded_support, log, count=1, flags=re.DOTALL)
if count != 1:
    raise RuntimeError(f'expected one current-support replacement, observed {count}')
needle = 'actual_first_order_fvm_crossing_verified = true\n'
replacement = (
    needle
    + 'case_a_frozen = true\n'
    + 'case_b_frozen = true\n'
)
if 'case_a_frozen = true' not in log:
    if needle not in log:
        raise RuntimeError('approval boundary insertion point not found')
    log = log.replace(needle, replacement, 1)
log_path.write_text(log, encoding='utf-8')
