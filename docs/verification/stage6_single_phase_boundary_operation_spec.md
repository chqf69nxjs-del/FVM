# Stage 6 single-phase boundary operation and valve verification specification

## 1. Purpose

この文書は、Stage 6として以下の二項目をsoftware / numerical verificationするための事前仕様である。

1. controlled pressure step / ramp
2. single-phase valve operation

Stage 6では、時間依存入力および部品操作を加えたときに、入力履歴、波の向き、到達時刻、flux、保存収支、artifactが一貫して追跡できることを確認する。

この仕様PRではsolver physics、boundary implementation、valve implementation、runtime runnerを変更しない。

## 2. Guardrails

Stage 6は以下ではない。

- physical Validationではない。
- design-use acceptanceではない。
- 実タンク、実配管、実弁の設備性能評価ではない。
- ESDイベント、pump trip、flashing、two-phase dischargeのverificationではない。
- `LinearPressureRamp`やKv則を実設備の完全な表現として承認するものではない。
- `n = 50`または任意のStage 6 meshをdesign meshとして承認するものではない。

維持するmetadata:

- `software_path_verification = true`
- `numerical_verification = true`
- `validation = false`
- `design_evaluation = false`
- `acceptance_gate = false`
- `property_backend_design_status = not_approved_for_design_use`

## 3. Existing implementation path

### 3.1 Controlled pressure input

既存コードには以下が存在する。

- `PressureTankBoundary`
- `ConstantPressure`
- `LinearPressureRamp`
- `flow_direction = bidirectional / outlet_only / inlet_only`
- `velocity_policy = copy / zero / fixed`

`LinearPressureRamp`は`p_initial_pa`から`p_final_pa`へ、`t_start_s`と`duration_s`で線形遷移する。

Stage 6では、最初の対象を右端の`PressureTankBoundary`とし、以下を明示する。

- right boundaryのみ時間依存圧力を与える。
- left boundaryはbase-state-compatibleな境界を用いる。
- 初期状態は一様静止状態を基本とする。
- 入力圧力履歴とnumerical boundary-face responseを別々に記録する。

### 3.2 Single-phase valve

既存コードには以下が存在する。

- `KvLiquidValve`
- `ConstantOpening`
- `LinearRampOpening`
- `ValveOutletBoundary`
- `InternalValveInterface`

Stage 6の主対象は`InternalValveInterface`とする。理由は以下である。

- 二側面fluxを明示的に持つ。
- finite opening時にmass / energy / vapor-mass fluxを両側で一致させる設計である。
- zero opening時に両側が独立reflective wallへ退化する。
- valve body forceによりmomentum flux差を許容する設計が明示されている。

`ValveOutletBoundary`は補助対象とし、境界弁としての単体確認に限定する。

## 4. V-011 controlled pressure step / ramp

### 4.1 Baseline problem

一様静止単相CO2管路に対し、右端圧力をbase pressureから小さな圧力差だけ変化させる。

baseline candidate:

| item | value |
|---|---:|
| pipe length | 100 m |
| diameter | 0.30 m |
| initial pressure | 8.0 MPa |
| initial temperature | 280 K |
| initial velocity | 0 m/s |
| pressure change magnitude | 1 kPa |
| ramp start | after initial hold |
| ramp duration | several acoustic time steps |
| probes | x/L = 0.25, 0.50, 0.75 |
| phase change | none |

初回実装はsmall-amplitude rampを主対象とする。zero-duration mathematical stepはsecondary caseとし、最初からprimary regression gateにはしない。

### 4.2 Expected response

圧力境界変化は左向きの圧力波を生成する。

小振幅線形音響の期待:

- wave speedはlocal sound speedに近い。
- probe到達時刻はboundary-to-probe distance / c0に整合する。
- 圧力変化の符号は入力圧力変化と整合する。
- velocity perturbationの符号は左向き波のcharacteristic relationと整合する。
- ramp durationが長いほど高周波成分は小さくなる。

### 4.3 Required diagnostics

入力履歴:

- requested boundary pressure
- actual schedule pressure
- ramp fraction
- start / end time

boundary telemetry:

- numerical mass / momentum / energy / vapor-mass flux
- diagnostic boundary-face pressure / velocity
- fixed-pressure residual relative to requested schedule

probe diagnostics:

- pressure / velocity history
- `A_plus` / `A_minus`
- first-arrival time
- observed propagation direction
- amplitude ratio versus imposed pressure change

health / budget:

- completed without exception
- reached target time
- all histories finite
- positive p/T/rho/c
- remained single phase
- mass / energy / vapor-mass balance including boundary flux
- required budget fields present

### 4.4 Test matrix

Phase A: ramp-duration observation

- duration = short
- duration = medium
- duration = long

Phase B: sign observation

- pressure increase
- pressure decrease, while remaining safely single phase and positive pressure

Phase C: mesh/CFL observation

- n = 50 / 100 / 200 at CFL 0.5
- n = 100 at CFL 0.25 / 0.5

Lower CFL is not treated as truth. Finest mesh is not an exact solution.

### 4.5 Completion criteria

V-011 COMPLETE requires:

- specification
- runner
- input / boundary / probe telemetry
- pure tests
- installed-CoolProp execution
- mesh/CFL observation
- CI-light regression
- formal report / manifest
- reproducible commands

## 5. V-012 single-phase valve operation

### 5.1 Scope

対象:

- single-phase liquid Kv law
- prescribed opening schedule
- internal valve between two finite-volume cells
- constant-opening cases
- controlled opening ramp
- controlled closing ramp

対象外:

- choked flow
- cavitation / flashing at the valve
- two-phase discharge coefficient
- actuator dynamics
- real valve hysteresis
- ESD event acceptance

### 5.2 Baseline problems

A. constant opening under a known pressure difference

- verify `Q` against the implemented Kv equation
- verify sign and reverse-flow policy
- verify face velocity and Mach cap

B. opening ramp

- opening 0 -> 1
- verify monotonic opening history
- verify flow response follows the prescribed law

C. closing ramp

- opening 1 -> 0
- verify through-flow decays
- verify zero opening reduces to hydraulic separation / reflective walls
- this is a component-operation problem, not yet an ESD event verification

### 5.3 Required diagnostics

schedule:

- opening fraction
- ramp start / duration
- initial / final opening

valve state:

- p_left / p_right
- delta p
- target Q from Kv law
- actual common mass flux-derived Q
- face velocity
- Mach cap activation flag

interface flux:

- left-segment mass / momentum / energy / vapor-mass flux
- right-segment mass / momentum / energy / vapor-mass flux
- mass-flux mismatch
- energy-flux mismatch
- vapor-mass-flux mismatch
- momentum-flux difference

budget and loss:

- total mass balance
- total energy balance
- vapor-mass balance
- `max((p_left-p_right)Q, 0)` hydraulic-loss diagnostic
- explicit statement that the current loss proxy is diagnostic and is not removed from `rhoE`

### 5.4 Expected behavior

Finite opening:

- mass flux is common across both valve sides.
- energy flux is common across both valve sides under the current upwind total-enthalpy construction.
- vapor-mass flux is common across both sides.
- momentum flux may differ because the valve body exerts force.

Zero opening:

- through mass / energy / vapor-mass flux is zero within numerical tolerance.
- both sides reduce to independent reflective walls.
- pressure on the two sides need not become equal.

Closing ramp:

- opening is monotonic non-increasing.
- target Q follows the implemented Kv law.
- flow response approaches zero as opening approaches zero.
- wave generation is expected, but Stage 6 does not yet judge a full ESD event.

### 5.5 Test matrix

Constant-opening law tests:

- opening = 0
- opening = 0.25
- opening = 0.5
- opening = 1.0

Pressure-difference sign tests:

- forward pressure drop
- reverse pressure drop with reverse flow disabled
- reverse pressure drop with reverse flow enabled

Operation tests:

- opening ramp
- closing ramp
- zero-duration closure as secondary observation only

Mesh/CFL tests:

- n = 50 / 100 / 200 at CFL 0.5
- n = 100 at CFL 0.25 / 0.5

### 5.6 Completion criteria

V-012 COMPLETE requires:

- specification
- pure Kv / schedule / interface tests
- component-operation runner
- valve telemetry artifact
- mass / energy / vapor-mass flux matching checks
- zero-opening wall-degeneration checks
- mesh/CFL observation
- CI-light regression
- formal report / manifest
- reproducible commands

## 6. Artifact requirements

Controlled pressure case:

- `*_config.json`
- `*_metrics.json`
- `*_pressure_schedule.csv`
- `*_probe_history.csv`
- `*_boundary_history.csv`
- `*_final_profile.csv`
- `*_report.md`

Valve case:

- `*_config.json`
- `*_metrics.json`
- `*_valve_history.csv`
- `*_probe_history.csv`
- `*_interface_flux_history.csv`
- `*_final_profile.csv`
- `*_report.md`

Comparison artifacts:

- mesh/CFL summary CSV and JSON
- pressure / velocity / characteristic plots
- schedule versus response plots
- valve opening / Q / dp plots
- interface flux mismatch plots
- formal report and SHA256 manifest

## 7. Implementation plan

PR-A: Stage 6 specification only

- this document
- repository implementation survey
- MASTER VERIFICATION INDEX update
- no solver or runtime changes

PR-B: controlled pressure ramp

- runner and telemetry
- pure and installed-CoolProp tests
- baseline artifacts

PR-C: internal valve operation

- valve-history and two-sided flux telemetry
- constant-opening and ramp cases
- pure and installed-CoolProp tests

PR-D: mesh/CFL, CI-light, formalization

- both V-011 and V-012 mesh/CFL observation
- regression bands after observed results
- GitHub Actions
- formal report / manifest
- completion review

## 8. Stop conditions

直ちに停止して仕様または実装を再確認する条件:

- non-finite history
- non-positive p/T/rho/c
- unexpected phase change
- missing required budgets
- schedule mismatch
- incorrect wave direction
- valve mass / energy / vapor-mass flux mismatch
- zero openingでnonzero through-flow
- untracked Mach clipping
- test通過目的だけのregression-band緩和

## 9. Completion status

この仕様書の追加だけではStage 6は完了しない。

- V-011: `IN_PROGRESS` after specification merge
- V-012: `IN_PROGRESS` after specification merge
- Stage 6: `IN_PROGRESS`

次の実装対象はcontrolled pressure ramp runnerである。
