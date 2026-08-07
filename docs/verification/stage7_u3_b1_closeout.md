# Stage 7 U3 B1 Closeout — 単相圧縮性流出および臨界状態component benchmark

## 1. Status

```text
Issue #127:                                      CLOSED / COMPLETED
Reference implementation:                       PR #131 / MERGED
Adapter comparison:                             PR #133 / MERGED
u3_b1_contract_locked:                          true
u3_b1_reference_implemented:                    true
u3_b1_adapter_implemented:                      true
u3_b1_component_benchmark_execution_complete:  true
u3_b1_component_benchmark_accepted:             true
```

U3 B1は、固定した単相CO₂上流状態からの圧縮性流出、臨界状態探索、非チョーク／チョーク判定、および保存量stream transferを対象とする**verification-only component benchmark**として完了した。

このcloseoutは、実配管の物理流出境界、二相臨界流、統合ブローダウン、物理Validation、設計利用またはproduction activationを承認しない。

## 2. Locked component law

上流停滞状態を

$$
(p_0,T_0,h_0,s_0)
$$

とし、候補圧力 $p$ に対して等エントロピー状態を構築する。

$$
s(p)=s_0
$$

$$
u_{\mathrm{ideal}}(p)
=\sqrt{2\left[h_0-h(p,s_0)\right]}
$$

$$
G_{\mathrm{ideal}}(p)
=\rho(p,s_0)u_{\mathrm{ideal}}(p)
$$

流量係数 $C_d$ と有効開口面積 $A_{\mathrm{eff}}$ を用いて、

$$
u_{\mathrm{eff}}=C_d u_{\mathrm{ideal}},
\qquad
G_{\mathrm{eff}}=C_d G_{\mathrm{ideal}}
$$

$$
\dot m=A_{\mathrm{eff}}G_{\mathrm{eff}}
$$

とする。正符号はmodeled domainから外向きである。

```text
mass transfer:             m_dot
momentum-stream transfer:  m_dot * u_eff
enthalpy transfer:         m_dot * h0
static pressure force:     excluded; deferred to FVM-face mapping
```

臨界圧力は、保持された単相候補経路上で理想質量流束を最大化する圧力として定義する。

$$
p_*=\underset{p}{\operatorname{arg\,max}}\;G_{\mathrm{ideal}}(p)
$$

```text
coarse search:       4097 pressure-ratio nodes
refinement:          deterministic golden-section maximization
final bracket width: <= 1 Pa
unchoked:            p_b > p_* + tolerance
choked:              p_b <= p_* + tolerance
```

## 3. Independent Reference authority

```text
PR:                              #131
Reference source head:           c7c25efae0e53a8b5f5ed164f9135238c6e005e0
main merge SHA:                  fa6c0ba14eb15dae482ee7766d03f7e1fca3574f
authoritative workflow run:      31051697864
artifact ID:                     8951665941
artifact ZIP SHA256:             b3ba4ed848c9d01a9c1232efa8fa97b46e80bf61185c151f2f6acde6440a4f94
fixed outcomes:                  17 / 17 MATCH
dedicated / related / full:      11 / 27 / 930 passed
skips / failures / errors:       0 / 0 / 0
final-head workflows:            15 / 15 SUCCESS
```

## 4. Independent Adapter authority

```text
PR:                              #133
Adapter source head:             5939f152180fbc6ce9a638eeca670b34e1a6650f
main merge SHA:                  e97be21de9b6cc62f527548e1047bc9d4ad759c1
authoritative workflow run:      31073576151
authoritative job:               92526482937
status:                          SUCCESS
artifact ID:                     8958246394
artifact name:                   stage7-u3-b1-adapter-31073576151
artifact ZIP SHA256:             b2b5b0ba68f58f72538c98a4570756360c5e8e3be87d3afdd797064464cf6aa2
internal SHA256 manifest:        12 / 12 verified
review findings addressed:       5 / 5
unresolved review threads:       0
final-head workflows:            16 / 16 SUCCESS
```

## 5. Independence boundary

```text
adapter imports Reference module:   false
shared property-path helper:        false
shared critical-search helper:      false
shared refinement helper:           false
shared transfer helper:             false
reference resolution mode:          recomputed_from_pinned_source_sha
pinned Reference source SHA:        c7c25efae0e53a8b5f5ed164f9135238c6e005e0
property backend:                   CoolProp 8.0.0
```

Historical Reference Artifact ID / ZIP SHA256はauthority証跡として保持する。Adapter workflowの実行可否はArtifact retentionへ依存せず、pinned Reference source SHAからReferenceを再構築する。

## 6. Fixed comparison result

```text
physical cases:                  12
guard cases:                      5
total cases:                     17
flux / transfer comparisons:     68
critical-pressure comparisons:    9
total comparisons:               77
comparison passes:              77 / 77
formal outcomes:                all match
```

```text
Adapter dedicated:              11 passed
related U3:                     38 passed
full repository:              941 passed
skips / failures / errors:       0 / 0 / 0
pytest deselected:               2
```

`deselected 2`は別workflow向け試験が選択対象外となったものであり、skip、failure、errorではない。

## 7. Critical-state result

固定単相ガス条件：

```text
upstream pressure:              1.0 MPa
upstream temperature:           320 K
critical pressure ratio:        0.5468849014513074
critical pressure:              546884.9014513075 Pa
critical temperature:           278.641212617351 K
critical density:               10.763564829778 kg/m^3
ideal critical mass flux:       2757.298423561355 kg/(m^2 s)
final search bracket width:      0.890336811077 Pa
```

流量係数別の有効臨界質量流束：

```text
Cd = 0.4:  1102.919369424542 kg/(m^2 s)
Cd = 0.8:  2205.838738849084 kg/(m^2 s)
```

## 8. Locked behavioral checks

```text
closed-element exact-zero identity:                 PASS
zero-pressure-drop exact-zero identity:             PASS
unchoked back-pressure ordering:                    PASS
below-critical plateau:                             PASS
area scaling ratio:                                 2.0 / PASS
Cd scaling ratio:                                   2.0 / PASS
critical pressure Cd-independence:                  PASS
B0 small-pressure-drop limiting comparison:         PASS
all expected guard outcomes:                        PASS
```

B0 limiting comparisonのrelative error：

```text
mass flow:             0.0001972791257517814
effective velocity:    6.571376381353641e-05
momentum stream:       0.0001315783258920566
energy transfer:       0.000197279125751925
```

これらはB1がB0を小圧力差極限として含むことを、固定contract tolerance内で確認するものである。実配管境界の妥当性を示すものではない。

## 9. Supported claims

```text
locked single-phase compressible component law is reproduced
independent Reference and Adapter paths agree within predeclared tolerances
critical-state search is deterministic for the fixed GAS_CRITICAL family
unchoked mass flow increases as fixed benchmark back pressure decreases
below the critical pressure, retained component transfers form a plateau
area and Cd scaling are retained
critical pressure is independent of Cd in the locked coefficient placement
closed and zero-pressure-drop stream-transfer identities are exact
B1 approaches the accepted B0 liquid limit for the fixed small-drop case
guard and out-of-scope inputs produce explicit formal outcomes
B1 component benchmark is accepted
```

## 10. Claims not supported

```text
physical discharge boundary approved
static pressure-force FVM-face mapping approved
finite-pipe coupling approved
two-phase choking accuracy approved
non-equilibrium flashing approved
receiver dynamics approved
friction / gravity / wall heat transfer approved
solid CO2 prediction approved
integrated pipeline blowdown approved
physical validation established
design sizing or design use accepted
production HEM activation approved
```

## 11. Approval boundary after B1

```text
u3_b1_contract_locked = true
u3_b1_reference_implemented = true
u3_b1_adapter_implemented = true
u3_b1_component_benchmark_execution_complete = true
u3_b1_component_benchmark_accepted = true

physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

## 12. Next controlled work

次の主作業は、**単相流出componentのFVM境界面mappingと有限配管coupling**である。実装前に、次のcontractを固定する。

```text
static pressure-force treatment
mass / momentum / energy sign convention
FVM face mapping
boundary-cell update
choking-state adoption rule
cumulative discharged mass
pipe inventory closure
reflected pressure wave
numerical stability
predeclared acceptance tolerances
Reference / Adapter independence
```

単相couplingが完了する前に、二相臨界流へ進まない。
