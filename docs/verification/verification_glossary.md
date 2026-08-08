# Verification Project Glossary

## 1. Purpose and use

本書は、Stage 7およびU3 verification workで使用する主要用語の意味と、各用語が支持する主張の境界を統一するための共通語彙表である。

次の原則を適用する。

1. 用語は、成立したevidenceが支持する最も狭い範囲で解釈する。
2. `IMPLEMENTED`、`VERIFIED`、`ACCEPTED`、`VALIDATED`、`APPROVED`を相互に置換しない。
3. `COMPLETE`は、その工程で予定した作業が完了したことを表し、物理精度や設計利用を自動的に承認しない。
4. `Guard`のexpected outcomeは、正常に拒否できたことを示す場合があり、必ずしもtest failureではない。
5. 本書は既存のlocked contract、equation、case condition、tolerance、formal flagまたはauthority resultを変更しない。
6. 本書と個別のlocked contract／closeout recordが競合する場合は、対象範囲に固有のlocked contract／closeout recordを優先する。

---

## 2. Project structure

| 用語 | このプロジェクトでの定義 | この用語だけでは意味しないこと |
|---|---|---|
| **Independent Verification Platform** | 商用コードまたは設計解析を、独立した物理モデル、数値実装、保存則監査およびevidenceから検証する社内基盤。 | 商用総合配管シミュレータの完全代替。 |
| **Stage** | 開発全体を大きく区切った作業段階。現在の主要開発はStage 7。 | Stage内の全Gateまたは全physical Validationの完了。 |
| **Gate** | Stage内で定義した技術的確認点または判定単位。 | 後続Gate、Validationまたはdesign useの承認。 |
| **Application Track A1** | 基盤solverを実用候補へ接続するためのapplication-oriented work track。 | U3 pilot全体の完成。 |
| **U3** | 最初のselected pilotであるpipeline depressurization／blowdown。 | integrated blowdown modelの承認。 |
| **U3 B0** | subcooled-liquid small-pressure-drop limitのverification component benchmark。 | choking、finite-pipe couplingまたはdesign use。 |
| **U3 B1** | single-phase compressible／critical-state discharge component benchmark。 | physical discharge boundary、two-phase chokingまたはfinite-pipe coupling。 |
| **U3 B2** | accepted B1 componentをconservative 1-D FVMの右端面へ接続し、face、one-stepおよびfinite-pipeを検証するbenchmark。 | B1そのものの再設計、two-phase dischargeまたはPhysical Validation。 |
| **controlled increment** | scope、変更path、claimsおよびevidenceを限定した一つの実装・検証単位。 | 後続工程を含む包括的な承認。 |
| **critical path** | 後続作業の開始条件となる、順番に成立させる必要がある主経路。現在のB2主経路は `Adapter → face parity → one-step parity → finite-pipe → closeout`。 | 並行研究課題の解決順序または全プロジェクトの固定日程。 |

---

## 3. Status and claim words

| 用語 | このプロジェクトでの定義 | この用語だけでは意味しないこと |
|---|---|---|
| **COMPLETE** | その工程に予定された実施事項が完了した状態。 | `ACCEPTED`、`VALIDATED`または`APPROVED`。 |
| **LOCKED** | 結果を見る前にcontract、case、tolerance、Guardおよび判定規則が固定された状態。 | 実装またはbenchmarkの成功。 |
| **IMPLEMENTED** | 対象sourceまたはReferenceがrepositoryの正式資産として実装された状態。 | Referenceとの一致、benchmark acceptanceまたは物理妥当性。 |
| **CHARACTERIZED** | 指定系列における挙動、傾向または感度を記録・分類した状態。 | 原因解明、independenceまたはaccuracy approval。 |
| **VERIFIED** | predeclared verification conditionに対して、実装または結果がReference、identity、保存則等と一致した状態。 | 現実のCO₂現象との一致。 |
| **ACCEPTED** | locked contractが要求するtested evidenceが成立し、formal closeoutで受理された状態。 | Physical Validation、design useまたはproduction activation。 |
| **VALIDATED** | モデル結果を適切な実験・実測データと比較し、定義された範囲で現実再現性を評価した状態。 | あらゆる条件での正確性またはdesign-use approval。 |
| **APPROVED** | 指定された原因、物理モデル、適用範囲または利用目的を、必要なevidenceに基づき正式に承認した状態。 | 明示されていない別用途への承認拡張。 |
| **NOT IMPLEMENTED** | 正式なrepository implementationまたはauthority-ready implementationがまだ存在しない状態。 | 構想、prototypeまたはstaging materialが存在しないこと。 |
| **NOT ESTABLISHED** | 成立を支持する必要十分なevidenceがまだない状態。 | 反証済みまたは不可能であること。 |
| **NOT APPROVED** | 調査または観測は存在し得るが、formal approval boundaryを越えていない状態。 | 現象が存在しないこと。 |
| **false formal flag** | 指定claimのcompletion boundaryが未成立であることを明示する状態。 | 将来も成立しないこと。 |
| **MERGED** | pull requestがmainへ正式に取り込まれた状態。 | Authority result、acceptanceまたはPhysical Validation。 |
| **Draft PR** | 変更を共有しているが、まだready-for-review／merge-readyを宣言していないpull request。 | 変更が不正確または廃棄予定であること。 |
| **mergeable** | 現在のbaseとのGit conflictなしにmerge可能な状態。 | CI success、review completionまたはapproval。 |
| **staging** | 実装候補またはpayloadが準備されているが、正式path、authority、reviewまたはmergeが未完了の状態。 | `IMPLEMENTED=true`。 |

### 3.1 Claim progression

次は同義ではなく、自動的にも昇格しない。

```text
IMPLEMENTED
≠ VERIFIED
≠ ACCEPTED
≠ VALIDATED
≠ APPROVED FOR DESIGN / PRODUCTION
```

例として、U3 B1がcomponent benchmarkとして`ACCEPTED`でも、physical discharge boundary、two-phase critical discharge、design useおよびproduction activationは別のapproval boundaryである。

---

## 4. Governance and evidence

| 用語 | このプロジェクトでの定義 | この用語だけでは意味しないこと |
|---|---|---|
| **Contract** | 実装およびauthority resultより前に、scope、equation interpretation、case matrix、tolerance、Guard、artifactおよびapproval boundaryを定める仕様。 | 実装結果またはacceptance。 |
| **locked contract** | authority result観測前に固定され、result-driven tuningを禁止したContract。 | Contract自体が物理的にvalidであること。 |
| **Reference** | Adapter under testとは別の経路でexpected valueまたはcomparison targetを作る実装・計算。 | 実験的真値または絶対的な物理正解。 |
| **Independent Reference** | AdapterとB2-specific mapping、one-step、ledgerまたはacoustic helperを共有しないReference。 | 上流component authorityまで共有禁止であること。B1は明示された範囲で共有可能。 |
| **Adapter** | accepted componentまたはinterfaceを、production-side solver pathへ接続する検証対象実装。 | 商用運用またはproduction activation。 |
| **implementation independence** | ReferenceとAdapterが、検証対象となる固有ロジックを共有しないこと。 | 言語、property backendまたは上流authorityを一切共有しないこと。 |
| **Authority / authoritative run** | exact source SHA、固定runtimeおよび正式workflowで生成され、closeout evidenceとして採用する実行。 | すべての将来claimへのauthority。 |
| **Artifact** | authority runが保持するJSON、CSV、figure、report、JUnit、contract copyおよびprovenance等のevidence package。 | Artifactの存在だけによるpassまたはacceptance。 |
| **provenance** | source SHA、checkout SHA、workflow run、runtime、dependency、property backend、Artifact ID等の生成来歴。 | 計算内容の正しさそのもの。 |
| **Git SHA** | sourceまたはmerge commitを一意に識別するGit object identifier。 | Artifact contentsの同一性。 |
| **SHA256** | Artifact ZIPまたはretained fileの内容同一性を確認するdigest。 | source code commitの識別。 |
| **JUnit** | dedicated、relatedおよびfull test outcomeを機械可読に保持するtest report。 | test caseの科学的十分性。 |
| **exact identity** | zero toleranceでbit-for-bitまたは数値的exactに保持することをContractで要求した関係。 | 近似的な物理accuracy。 |
| **Guard** | invalid、unsupportedまたはscope外の入力・状態を、predeclared formal outcomeで拒否する処理またはcase。 | unexpected test failure。 |
| **atomic Guard** | Guard時にflux、budget、solver state、timeまたはstep counterを部分更新せずに失敗させる性質。 | recovery後の物理状態を自動生成すること。 |
| **result-driven tuning** | authority resultを見た後に、passさせる目的でtolerance、case、equationまたはGuardを緩和すること。 | 明示的version updateとhistorical evidenceを伴う正当なContract改訂。 |
| **central record** | projectのformal current stateを示すsnapshot、master indexおよびexecution log。 | 個別Artifactの完全代替。 |
| **central record synchronization** | merged authorityとformal flagsをcentral recordsへ反映し、実態と記録を一致させる作業。 | 新しいtechnical resultの生成。 |
| **closeout** | authority、Artifact、review、formal flags、limitationsおよびcentral recordsを揃え、工程を正式に閉じる作業。 | scope外claimの承認。 |
| **traceability** | `Theory → numerical formulation → implementation → test → evidence`を辿れる状態。 | 各層が自動的に正しいこと。 |
| **expected-head merge** | authorityを取得したexact head SHAを指定してmergeし、無検証変更の混入を防ぐ手順。 | merge後の後続作業の成功。 |
| **review thread = 0** | 未解決のinline review threadが残っていない状態。 | review内容が存在しなかったこと、またはCI success。 |

---

## 5. FVM and B2 boundary coupling

| 用語 | このプロジェクトでの定義 | この用語だけでは意味しないこと |
|---|---|---|
| **FVM** | Finite Volume Method。セルinventoryを、cell faceを通るconservative fluxの差で更新する数値法。 | mesh／CFL independenceまたはphysical accuracy。 |
| **conserved state** | solverが直接保持する `rho`、`rho*u`、`rho*E`、`rho*xv`。 | 圧力、温度等が独立保存されること。 |
| **primitive state** | conserved stateとEOSから復元する `rho`、`u`、`p`、`e`、`T`、`xv`、`alpha`、`c`等。 | stagnation state。 |
| **static state** | adjacent cellの局所的なthermodynamic／kinematic state。 | 流速をゼロにした全状態。 |
| **stagnation state** | static stateを等エントロピー的に停止させたとみなす全状態。B2では `h0=h+u^2/2`、`s0=s`から`p0,T0`を復元する。 | receiver stateまたはtank state。 |
| **stagnation reconstruction** | adjacent conserved stateからstatic `p,T,h,s,c`を評価し、`h0,s0`を介して`p0,T0`を復元する処理。 | B1 lawの変更。 |
| **face** | 隣接control volume間、またはcontrol volumeと外部境界間の数値面。 | 実在するvalve／orifice geometry。 |
| **right external face** | modeled pipeの右端にある外向き法線`+x`の外部境界面。 | receiver dynamics。 |
| **face mapping** | B1 transfer tupleをFVM right-face fluxへ変換するB2固有処理。 | finite-pipe response全体。 |
| **direct external-face flux override** | ghost-state numerical fluxを最終的なB2 fluxで右外部面だけ直接置換する方式。 | 内部Rusanov fluxまたはinternal-interface lawの変更。 |
| **ghost state** | boundary外側に構築する仮想conserved state。B2ではarray／state check用に有限値を保つが、discharge mappingには使用しない。 | B2 transfer tupleを表すphysical state。 |
| **Rusanov flux** | 左右stateと最大波速から構築するfirst-order numerical flux。 | B2 right-face final flux。右外部面ではoverrideされる。 |
| **internal-interface override** | valve等の内部面で既存fluxを置換する処理。 | right external-face override。 |
| **boundary budget** | applied left／right external numerical fluxを時間積分し、domain inventoryとのclosureを監査する会計。 | physical loss model。 |
| **conservative update** | `U_new = U - dt/dx*(F_right-F_left)`に基づく保存量更新。 | positivityまたはphase scopeが自動保証されること。 |
| **mass flux** | faceを通る単位面積当たり質量transfer。 | total momentum flux。 |
| **advective momentum stream** | 質量移流に伴う運動量transfer、B2では`m_dot*u_eff`。 | static pressure force。 |
| **static pressure force** | faceのopen／closed areaへ作用するpressure contribution。 | 質量transferまたはenergy transfer。 |
| **total momentum rate** | advective momentum stream、open-area pressure force、closed-area pressure forceの和。 | momentum conservationが内部body forceなしで成立すること。 |
| **energy transfer** | B1が返す`m_dot*h0`に基づくoutward total-energy transfer。 | wall heat transferまたはreceiver energy balance。 |
| **closed identity** | opening zeroで`[F_rho,F_rho_u,F_rho_E,F_rho_xv]=[0,p_i,0,0]`をexactに保持する関係。 | momentum flux全体がzeroであること。 |
| **zero-drop identity** | exact-zero adjacent velocityかつback pressureとadjacent static pressureが同一のlocked caseで、stream transfer zeroと`[0,p_i,0,0]`を保持する関係。 | 任意のmoving stateまたはround-trip coordinateに対する一般的B1 predicate変更。 |
| **face parity** | Adapterのformal outcomeおよびface transfer／fluxがIndependent Referenceとpredeclared tolerance内で一致すること。 | solver state updateまたはfinite-pipe coupling。 |
| **one-step** | actual solver pathで一回だけconservative updateを行う検証段階。 | long-time stabilityまたはwave propagation。 |
| **one-step parity** | Adapterを適用した一回のsolver update、budgetおよびpost-stateがIndependent Reference balanceと一致すること。 | finite-pipe benchmark acceptance。 |
| **positivity handling** | trial update後のfinite state、`rho>0`、`e>0`等を確認し、不成立時にpredeclared deterministic halvingを行う処理。 | tolerance relaxationまたはsilent clipping。 |
| **deterministic halving** | 同一trial ruleのまま`dt`を1/2に縮小する再試行。B2では最大12回。 | physics、caseまたはtoleranceの変更。 |
| **finite-pipe coupling** | 複数cellの有限長pipeへB2 right-face boundaryを接続し、時間発展、inventoryおよびwave propagationを実行すること。 | physical Validationまたはlong-time blowdown accuracy。 |

---

## 6. Conservation, inventory, and waves

| 用語 | このプロジェクトでの定義 | この用語だけでは意味しないこと |
|---|---|---|
| **inventory** | domain内に保持されるmass、momentum、total energyまたはvapor massの空間積分値。 | 累積流出量。 |
| **ledger** | stepごとのrate、cumulative transfer、pipe inventoryおよびresidualを保持する会計表。 | actual finite-pipe execution。Reference ledgerはtarget定義の場合がある。 |
| **mass inventory closure** | `M_pipe(t)+M_out(t)-M_pipe(0)`がlocked tolerance内であること。 | momentumまたはenergy closure。 |
| **energy inventory closure** | `E_pipe(t)+E_out(t)-E_pipe(0)`がlocked tolerance内であること。 | wall heat transferを含む実設備energy balance。 |
| **momentum impulse** | boundary momentum rateまたはpressure forceを時間積分した量。 | momentumがmass／energyと同じsimple inventory identityを持つこと。 |
| **vapor identity** | declared single-phase B2 scopeで`rho*xv`およびvapor inventoryがexact zeroを保持すること。 | two-phase modelのaccuracy。 |
| **acoustic reference** | requested probeに対するdirect／reflected arrival time、pressure signおよびvelocity signの独立target。 | actual wave amplitudeのValidation。 |
| **rarefaction** | outlet depressurizationによってpipe内へ伝播する膨張波。 | two-phase flashing front。 |
| **direct rarefaction** | right boundaryからprobeへ最初に到達するoutlet起因のrarefaction。 | left-wall reflection。 |
| **rigid-wall reflection** | direct waveがleft reflective boundaryで反射し、probeへ戻るevent。 | 実設備端部の完全反射性。 |
| **probe** | pressure／velocity historyを評価するpredeclared pipe coordinate。 | cell centerそのもの。必要に応じて固定補間を使う。 |
| **event extraction rule** | fixed time window、centered pressure slopeおよびpressure／velocity signでarrival eventを決めるpredeclared rule。 | resultを見た後のwindow変更。 |

---

## 7. Numerical sensitivity and unresolved phenomena

| 用語 | このプロジェクトでの定義 | この用語だけでは意味しないこと |
|---|---|---|
| **CFL** | explicit updateの時間刻みをcell widthと最大characteristic speedに対して表す無次元数。 | time-step independence。 |
| **mesh** | domainのcontrol-volume分割。 | physical geometry fidelity。 |
| **mesh characterization** | fixed mesh sequenceでmetricの変化を記録・比較すること。 | mesh independenceまたはformal convergence order。 |
| **CFL characterization** | fixed CFL sequenceでmetricの変化を記録・比較すること。 | CFL independence。 |
| **mesh independence** | さらにmeshを細分化しても、定義metricがpredeclared範囲で変化しないことを示すclaim。 | mesh sequenceを実行しただけで成立すること。 |
| **CFL independence** | CFLを縮小しても、定義metricがpredeclared範囲で変化しないことを示すclaim。 | CFL sensitivityを観測・記録しただけで成立すること。 |
| **crossing** | phase classifier上でsingle-phase regionからphase boundaryまたはopen-two-phase regionへ遷移するevent。 | physical nucleationまたは実験的flashing onset。 |
| **crossing candidate time / position** | fixed extraction ruleで最初のcrossing候補として記録した時刻・位置。 | root causeまたはindependent solution。 |
| **crossing depth** | phase boundaryをどの程度越えたかを表すdiagnostic metric。 | crossing eventの存在だけ。現在はCFL-sensitive／non-monotone。 |
| **phase chatter** | phase classificationが短い時間・局所領域で繰り返し切り替わる挙動。 | 物理的振動または数値原因の確定。 |
| **root cause approved** | competing hypothesesをevidenceで排除し、主要原因をformalに承認した状態。 | diagnosis、correlationまたは候補原因の提示だけ。 |
| **near-saturation acoustic continuity** | saturation近傍でsingle-phase／two-phase acoustic treatmentの連続性を評価する課題。 | two-phase acoustic accuracy bandの承認。 |

---

## 8. Physical models and application boundary

| 用語 | このプロジェクトでの定義 | この用語だけでは意味しないこと |
|---|---|---|
| **HEM** | Homogeneous Equilibrium Model。相間で局所熱力学平衡を仮定する二相モデル。 | non-equilibrium flashingの再現。 |
| **HNE / non-equilibrium flashing** | phase changeの遅れ、metastabilityまたはrelaxationを扱う将来の非平衡モデル領域。 | 現在実装・accepted済みであること。 |
| **critical discharge / choking** | downstream pressureをさらに下げてもmass fluxが増加しない流出状態。 | two-phase chokingまたはphysical Validation。 |
| **two-phase critical discharge** | two-phase stateを含むcritical discharge model／benchmark。 | U3 B1 single-phase chokingから自動的に承認されること。 |
| **Verification** | 指定equation、algorithmおよびContractをsoftware／numerical implementationが正しく実行しているかを評価すること。 | 現実の物理現象との一致。 |
| **Validation** | model outputを実験・field dataと比較し、現実再現性を評価すること。 | software implementationの独立Verification。 |
| **Physical Validation** | uncertaintyを伴う適切な実験・実測との比較により、物理modelの適用可能性を評価すること。 | design useまたはproduction approval。 |
| **commercial-code cross-validation** | 同一または対応条件で商用コードと比較し、差異、model-formおよびimplementation dependenceを分析すること。 | 商用コードを絶対的真値とみなすこと。 |
| **applicability envelope** | pressure、temperature、phase、geometry、time scale等について、evidenceが支持する利用範囲。 | envelope外への外挿承認。 |
| **uncertainty envelope** | input、property、model-form、numericalおよびmeasurement uncertaintyを含む結果範囲。 | 単一のdeterministic error bound。 |
| **design-use acceptance** | engineering design decisionへ利用可能とformalに承認された状態。 | Verification benchmark acceptanceだけでの自動昇格。 |
| **production activation** | verification-only pathではなく、正式なproduction calculation pathとして有効化すること。 | codeがrepositoryに存在するだけでの有効化。 |

---

## 9. Current B2 terminology checkpoint

2026-08-09のcentral recordに対応するB2 statusは次のとおりである。

```text
u3_b2_contract_locked = true
u3_b2_reference_implemented = true

u3_b2_fvm_adapter_implemented = false
u3_b2_finite_pipe_execution_complete = false
u3_b2_verification_benchmark_accepted = false
single_phase_fvm_discharge_mapping_verified = false
single_phase_finite_pipe_coupling_verified = false

physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

現在のcontrolled orderは次である。

```text
B2 FVM Adapter
→ face parity
→ one-step conservative parity
→ finite-pipe execution
→ inventory / impulse / acoustic verification
→ fixed mesh / CFL characterization
→ B2 closeout
```

Two-phase critical discharge、HNE、Physical Validation、commercial-code cross-validation、design useおよびproduction activationは、このsingle-phase B2 completion boundaryより後の別工程である。
