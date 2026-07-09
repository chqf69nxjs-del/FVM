# Discrimination Cases D/E/A — Ver.0.7.0

## Purpose

Case C was pressure-wave dominated, so HEM/HNE/DVCM differences were small. Ver.0.7.0 introduces three discrimination cases and a layered report format.

## Report hierarchy

1. Reviewer one-page summary
2. Engineer report
3. Technical appendix / CSV / x-t fields

## Cases

| Case | Role |
|---|---|
| Case D | High-point flashing discrimination |
| Case E | Near-saturation ESD closure discrimination |
| Case A | Pump trip discrimination with current quasi-steady pump boundary |

## Model roles

| Model | Role |
|---|---|
| HEM | Instantaneous equilibrium upper-side comparison |
| HNE | Delayed phase-change main candidate |
| DVCM | Legacy cavity-volume proxy, not a full MOC-DVCM solver |

## Limitation

The cases are intentionally configured to make model differences visible. They are software/physics discrimination tests, not design reference calculations.
