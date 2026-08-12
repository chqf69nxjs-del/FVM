# Stage 7 U3 B2 A1 finite-compression Increment 5 enthalpy-identity correction

## Status

`MODEL_REVIEW_ONLY / NUMERICAL_IDENTITY_CORRECTION / FIXED_BEFORE_RERUN`

This note corrects one redundant numerical identity gate observed in the first Increment 5 diagnostic. It does not change the Hugoniot equation, the fixed pressure nodes, the density root, B1, the compatibility-root tolerance, the Weak Compression scope, the diagnostic `chi` cap, or any formal project state.

## First diagnostic authority

```text
source Git SHA:
dc9c117a720ba14814e4ff23660d16fe2b7e4736

workflow run:
31651694424

job:
94297206783

artifact:
9162803881

artifact name:
u3-b2-a1-finite-compression-increment-5-31651694424

GitHub artifact SHA256:
b80161157cbd7e1e3f95df662fc7185caef15d57390e137bb89932ff134edead
```

The diagnostic successfully reproduced the exact step-483 state without mutation and found the diagnostic-only isentropic extrapolation root at:

```text
requested chi:
1.03690185546875e-6

pressure offset:
196.73964847624302 Pa

compatibility residual:
7.973340586733824e-9 kg/s
```

The Hugoniot density search found one density sign-change bracket and completed 64 density bisection iterations at every fixed `chi` node. It then rejected each state only because:

```text
abs(H_e - H_h) > 1.0e-8 J/kg
```

## Observed closures

Across the fixed Hugoniot scan, the completed density roots retained:

```text
minimum absolute H_e residual:
approximately 1.9e-12 J/kg

maximum observed absolute H_e residual at the selected density roots:
well below 1.0e-6 J/kg

raw abs(H_e - H_h):
approximately 6.39e-8 to 9.06e-8 J/kg
```

Thus the primary internal-energy and enthalpy Hugoniot equations individually closed inside the fixed `1.0e-6 J/kg` tolerances. The failure came only from the stricter redundant equivalence comparison.

## Identity analysis

Define the CoolProp enthalpy identity residual at each state:

```text
I = h - e - p v
```

For finite-precision EOS properties:

```text
H_e - H_h = I_i - I_P
```

Therefore a raw `H_e - H_h` comparison also measures the difference between the two independently returned CoolProp property identities. Requiring the raw difference to be below `1.0e-8 J/kg` was stricter than the observed EOS identity consistency and duplicated information already tested by the individual Hugoniot closures.

## Corrected gate

Continue to require without change:

```text
abs(H_e) <= 1.0e-6 J/kg
abs(H_h) <= 1.0e-6 J/kg
```

Record without using as a direct pass/fail gate:

```text
raw_difference = H_e - H_h
```

Add:

```text
I_i = h_i - e_i - p_i v_i
I_P = h_P - e_P - p_P v_P

identity_accounted_difference
= (H_e - H_h) - (I_i - I_P)
```

and require:

```text
abs(identity_accounted_difference) <= 1.0e-10 J/kg
```

The raw difference, both EOS identity residuals, and the corrected difference must all be retained in the evidence.

This correction does not turn a failed Hugoniot energy state into a successful one. Both physical Hugoniot forms must still independently close inside their original tolerances.

## Rerun boundary

Rerun the same diagnostic from the same step-483 authority. No solver step may be attempted and no finite-compression flux may be applied.

All formal states remain false regardless of result.
