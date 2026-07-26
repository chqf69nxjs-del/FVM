from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'docs' / 'verification' / 'MASTER_VERIFICATION_INDEX.md'
text = path.read_text(encoding='utf-8')
marker = '## Current technical conclusion\n'
if marker not in text:
    raise RuntimeError('stale pre-PR #77 current-conclusion marker not found')
prefix, _ = text.split(marker, 1)
historical = '''## Historical checkpoint after PR #75 — superseded

At the PR #75 checkpoint, the prescribed-subcooled outlet boundary and its 195-sample
preflight had been software-verified, but that boundary had not yet been connected to a
pipeline FVM time step. The former "Current technical conclusion" and "Next gates" text
below this point described that then-current state.

That checkpoint is retained here only as historical context and is superseded by the
2026-07-26 current-state block and the PR #77/#79/#82/#84 continuation record above.
Subsequent merged work executed the fixed boundary-driven pipeline matrix, diagnosed the
4 MPa subthreshold crossing, completed the 32/64/128-cell mesh matrix, and fixed the
128-cell CFL contract with exact CFL 0.10 replay.

The current active operational gate is Issue #85, followed by the fixed low-CFL execution
in Issue #86. Gate P2, mesh-independent accuracy, CFL-independent crossing, near-saturation
acoustic continuity, post-crossing propagation, physical Validation, design use, and
production HEM activation remain unapproved.
'''
path.write_text(prefix.rstrip() + '\n\n' + historical, encoding='utf-8')
