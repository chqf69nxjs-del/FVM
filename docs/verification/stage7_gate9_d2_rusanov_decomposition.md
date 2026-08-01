# Stage 7 Gate 9 D2 — production Rusanov flux厳密分解・第1増分

## 状態

```text
Issue:                         #110
前提D1:                        PR #116でmainへマージ済み
増分:                          D2 / CFL 0.10 identity column
production flux式:             変更なし
分解用EOS呼出し:               なし
分解用wave-speed再計算:        なし
property backend:              coolprop_co2
backend design-use status:     VERIFICATION_ONLY_NOT_APPROVED_FOR_DESIGN_USE
CFL 0.05 / 0.025実行:          未着手
D3 acoustic history:           未着手
D4 event window:               未着手
Gate 9 execution complete:     false
```

## 1. 目的

D1では、保持済みの`PipelineCaseResult`を後処理してもCFL `0.10`のsolver結果が
変化しないことを確認した。ただし、D1の`RAW_POST_FVM`保存変数は、保持されて
いるcell値から再構成したものであり、Gate 9契約のRusanov再構成guardを判定する
ためのbitwiseなproduction入力ではない。

D2では、既存Rusanov fluxが実際に評価される位置で、production fluxを計算した
直後に次の配列を読み取り専用で取得する。

```text
U_left
U_right
F_left
F_right
a_max
production Rusanov flux
```

診断分解には、このproduction評価位置で取得した値だけを使う。EOSの再呼出し、
音速の再計算、数値fluxの置換、状態の補正、time stepの切詰め、formal stop後の
継続は行わない。

## 2. 物性backendの追跡性

本増分の固定ケースは、純CO2のCoolProp経路を使用する。機械可読な
`summary.json`には、以下を明示的に保存する。

```text
property_backend_name:
  coolprop_co2

property_backend_design_status:
  VERIFICATION_ONLY_NOT_APPROVED_FOR_DESIGN_USE
```

これは、結果がsurrogateや別backendから生成されたものではないことをartifact
だけで識別可能にするためのprovenanceである。同時に、このbackendを使ったことが
physical validationやdesign-use acceptanceを意味しないことを固定する。

## 3. 読み取り専用observer

`flux.py`のproduction Rusanov式は変更しない。

\[
F_{\mathrm{prod}}
= \frac{1}{2}(F_L+F_R)
- \frac{1}{2}a_{\max}(U_R-U_L)
\]

`F_prod`を従来どおり計算した後、任意のobserverへ入力・中間量・出力の独立copyを
渡す。各copyはnon-writeableに設定する。observerは`ContextVar`によりcontext-local
かつ既定無効であり、context終了時には以前のobserver状態を復元する。

この構造では、observerは次を行えない。

```text
production fluxの差替え
solver stateの書換え
EOS結果の書換え
wave speedの再決定
boundary stateの変更
formal outcomeの変更
```

`FvmSolver`のconstructor、保存則更新式、CFL計算、phase classifier、quality
projection、sound-speed evaluator、prescribed boundary、formal stop logicには変更を
加えない。

## 4. 診断分解

各対象interfaceについて、取得済みproduction配列から次を計算する。

\[
F_{\mathrm{central}}=\frac{1}{2}(F_L+F_R)
\]

\[
F_{\mathrm{dissipative}}
=-\frac{1}{2}a_{\max}(U_R-U_L)
\]

\[
F_{\mathrm{reconstructed}}
=F_{\mathrm{central}}+F_{\mathrm{dissipative}}
\]

normalized residualはGate 9契約どおり、

\[
r = \max_i
\frac{|F_{\mathrm{reconstructed},i}-F_{\mathrm{prod},i}|}
{\max(1,
|F_{\mathrm{reconstructed},i}|,
|F_{\mathrm{prod},i}|,
|F_{\mathrm{central},i}|,
|F_{\mathrm{dissipative},i}|)}
\]

とする。固定guardは、

```text
r <= 5e-13
```

である。超過した場合は
`RUSANOV_DECOMPOSITION_RECONSTRUCTION_FAILURE`相当のD2 failureとして扱い、
flux、state、threshold、toleranceを変更して修復しない。

## 5. interface mapping

固定32-cell・2-ghost-cellケースでは、extended flux配列との対応を次のように固定
する。

| Gate 9 interface | observed flux index | left cell | right cell |
|---|---:|---:|---:|
| `27|28` | 29 | 27 | 28 |
| `28|29` | 30 | 28 | 29 |
| `29|30` | 31 | 29 | 30 |
| `30|31` | 32 | 30 | 31 |
| `RIGHT_BOUNDARY` | 33 | 31 | prescribed ghost state |

interface評価時刻は各accepted stepの`time_before_s`とする。記録にはstepの`dt`を
保存し、production fluxが隣接cellへ与える`dt/dx`寄与も保持する。

```text
left adjacent cell:   -(dt/dx) F_prod
right adjacent cell:  +(dt/dx) F_prod
```

右境界では右側が内部cellではないため、prescribed ghost stateは保存するが、
right internal-cell incrementは`None`とする。

## 6. 第1増分の実行境界

本増分では、Gate 8のimmutable referenceであるCFL `0.10`列のみを実行する。
次の値を完全一致で再現することを要求する。

```text
formal outcome:      ACCEPTED_FIRST_CROSSING
candidate step:      125
candidate time:      0.0007999325695335248 s
candidate cell:      29
maximum q_eq:        3.773646403587342e-06
```

診断OFFとONでは、次を完全一致させる。

```text
formal outcome / failure reason
step count / final time
candidate metadata
final state SHA256 / run signature
full time history
full pressure history
full accepted conservative-state history
```

想定されるD2証拠量は次のとおりである。

```text
production Rusanov evaluations:  125
focused interfaces per step:     5
focused interface records:       625
```

## 7. 第1増分の結果

CFL `0.10`で、125回のproduction Rusanov array評価と、対象5 interface × 125 stepの
625件を取得した。

```text
maximum normalized residual:      0.0
locked residual tolerance:        5e-13
Rusanov reconstruction guard:     PASS
diagnostic OFF/ON identity:       PASS
retained-history SHA before/after: identical
```

この結果は、production評価位置で取得した`central`成分と`dissipative`成分の和が、
既存solverのproduction Rusanov fluxを契約内で再構成することを示す。また、observer
を有効化しても固定CFL `0.10`のformal pathが変化しないことを示す。

ただし、residualが0であることは、Rusanov法のphysical accuracy、数値散逸の小ささ、
またはcrossing結果の妥当性を証明するものではない。これは診断分解のsoftware
identityを示す証拠である。

## 8. 明示的に未実施の範囲

本D2第1増分には次を含めない。

```text
CFL 0.05 / 0.025のinterface history
candidate前8・候補step・候補後8 accepted stepsの抽出
first / second projectionの厳密な中間配列
acoustic trialおよび最大12回halving history
cross-CFL correlation label
root-cause approval
mitigation authorization
physical validation
design-use acceptance
production activation
```

CFL `0.10`の1列だけから、Rusanov dissipationが非単調なcrossing-depth系列の原因で
あるという因果主張は行わない。

## 9. 結論

D2第1増分により、既存計算を変更せず、実際のproduction Rusanov評価を
`central`成分と`dissipative`成分へ厳密に分解して記録する経路を確立した。

次の作業は、D3で既存sound-speed evaluatorのtrial・halving履歴を観測し、D4で
crossing候補前後のevent-aligned stageを厳密に保持した後、CFL `0.10 / 0.05 /
0.025`を同一契約で比較することである。

```text
Gate_9_execution_complete = false
crossing_depth_root_cause_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
