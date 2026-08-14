# AGENTS.md

# 液化ガス管路システム解析検討ツール 開発ルール

このリポジトリは、液化ガス、主にLCO₂を対象とした一次元管路過渡解析・信頼性評価のための**解析検討ツール**を開発するリポジトリである。

本プロジェクトの目的は、有限長液体CO₂配管における過渡圧力波、減圧、フラッシング、および気液二相化を、明示された適用範囲・制限・fail-closed条件のもとで解析検討できる実用的な計算ツールを開発することである。

対象には、陸上貯蔵タンクから輸送船内タンクへ液化ガスを移送する管路システム、ESD弁急閉、ポンプ急停止、高所部フラッシング、飽和近傍二相化、および配管減圧・blowdownを含む。

圧力伝播やフラッシング現象の完全な解明、全物理領域に対する包括的Verification、または全面的なPhysical Validationそのものを、Working Vertical Sliceの完成条件とはしない。

---

## 1. 基本方針

* 主ソルバは保存形有限体積法FVMとする。
* MOCは主ソルバではなく、単相水撃・圧力波到達時刻確認用のverification solverとする。
* DVCMは主評価モデルではなく、legacy comparison proxyとして扱う。
* HEM / HNE系モデルを、液化ガスの二相化・フラッシング・相変化遅れ評価の主候補とする。
* HEMは平衡フラッシングのbaseline、HNE / relaxation modelは相変化遅れの比較検討候補として扱う。
* Working vertical slice firstを基本とし、その後のPhysics refinement / Verificationは具体的なリスクと利用目的に応じて限定的に行う。
* 実在LCO₂物性が未承認の結果を、設計評価結果と呼ばない。
* surrogate_lco2による結果は、開発確認・試評価・識別ケース用として扱う。
* 計算成功だけで、Verification、Acceptance、Validation、またはApprovalへ昇格させない。

---

## 2. コード構成の考え方

基本構成は以下を想定する。

```text
src/
  liquid_gas_transient/
    solver/
    properties/
    models/
    cases/
    verification/
tests/
verification/
docs/
```

ただし、既存構成を大きく壊す変更は避けること。
構成変更が必要な場合は、まず小さな差分で行い、理由を明記する。

---

## 3. 物理モデルに関する注意

### FVM

保存変数は基本的に以下を想定する。

```text
rho
rho*u
rho*E
rho*xv
```

将来拡張として、非凝縮性ガス用に`rho*Ync`を追加する可能性がある。

### HEM

HEMは局所熱力学平衡を仮定するモデルである。
即時平衡に基づく二相化応答を評価するために用いる。

### HNE

HNEは有限緩和時間により、平衡状態への遅れを表すモデルである。
緩和時間`tau`の値や相関式は、勝手に確定値として扱わないこと。

### DVCM

DVCMは古典的な空洞発生評価との比較用proxyとする。
完全なMOC-DVCMソルバとして扱わないこと。

---

## 4. 物性計算モジュールの方針

物性backendとは、FVMソルバから呼び出され、圧力、温度、密度、内部エネルギーなどの状態量から、LCO₂の物性値を返す物性計算モジュールである。

想定するbackendは以下である。

* `surrogate_lco2`: 開発・動作確認用
* `coolprop_co2`: CoolPropによる実在物性候補
* `refprop_co2`: REFPROPによる高精度物性候補
* `reference_table_lco2`: 承認済み基準CSVによる設計評価候補

CoolPropやREFPROPが利用できない環境では、テストを失敗させるのではなく、明示的にskipすること。

---

## 5. 設計評価に関する禁止事項

以下を行ってはならない。

* surrogate_lco2の結果を設計評価結果と呼ぶ。
* validation未完のモデル結果を、設計上確定した評価として扱う。
* DVCM proxyをHEM/HNEと同等の熱力学モデルとして説明する。
* HNEの緩和時間`tau`を根拠なく固定する。
* 物性backendのdesign-use statusを明記せずに結果を出力する。
* 概念図を解析結果図のように扱う。
* Working Toolの完成を、physics modelのVerificationまたはPhysical Validation完成と表現する。
* 現象の完全解明を、ツールのWorking Vertical Slice完成条件へ暗黙に追加する。

---

## 6. テスト・Verification方針

変更後は、可能な範囲で以下を確認する。

```bash
PYTHONPATH=src pytest -q
```

追加・変更した機能に対して、少なくとも以下の観点を確認する。

* 既存テストが壊れていないこと
* 保存性に関するbudget residualが悪化していないこと
* backend名が出力・レポートに残ること
* surrogateと実在物性backendの扱いが混同されないこと
* CoolProp未導入環境では関連テストがskipされること
* solver crash、nonfinite、positivity loss、scope departure、root failureなどが明示的に分類されること
* 適用範囲外では、根拠なく計算を継続せずfail closedできること

Verificationは、各Incrementで事前に定義した保存性、有限性、再現性、数値安定性、状態遷移、fail-closed動作などの受入条件に限定して実施する。

受入条件を満たした後、追加Verificationは次のいずれかが明示された場合に限る。

* 実際にsolver crash、nonfinite、positivity loss、保存性違反などが発生した。
* 適用範囲内で結果の不連続、branch chatter、または再現性喪失が発生した。
* 新しい入力条件、物理領域、または利用目的へscopeを拡張する。
* 工学的な比較・判断を逆転させる可能性がある。
* 代表ValidationまたはAcceptanceへ進むための前提として必要である。

「さらに調べれば安心できる」という理由だけで、無期限にVerificationを追加しない。

---

## 7. レポート・可視化方針

レポートは原則として日本語中心で作成する。

ただし、以下は英語表記を残してよい。

* 変数名
* ファイル名
* backend名
* case名
* HEM / HNE / DVCM
* onset time
* active length
* max alpha
* max xv

レポート生成では、以下を必ず意識する。

* 概念図と解析結果図を混同しない。
* 解析結果図にはcase、model、backend、versionを明記する。
* reviewer report、engineer report、technical appendixを分ける。
* コメントは解析データから読み取れることだけを書く。
* いきなり定量表を出さず、まず解析対象と評価指標を説明する。
* 圧力波frontとflashing / phase frontを可能な範囲で区別して記録する。
* 結果がWorking Slice、Verified、Validated、またはApprovedのどの状態かを明記する。

---

## 8. 開発作業の進め方

1回の作業は小さく分けること。

望ましい作業単位の例：

* 物性backendインターフェースの整理
* CoolProp backendの最小実装
* 飽和線verificationの追加
* reference CSV schemaの追加
* report出力へのbackend名追加
* README / docsの更新
* post-crossing continuationの限定increment
* HEM / HNE比較用の最小prototype

避けるべき作業：

* 複数の物理モデルを同時に大きく変更する
* ソルバ構造とレポート構造を同時に大きく変更する
* テストなしで挙動を変える
* 既存の検証ケースを無断で削除する
* 単相Verificationを完了させるまで二相流検討を全面停止する
* 完全性を理由として、Working Vertical Sliceの成立後も無期限に同じ検証を細分化する

---

## 9. Codex / Agentへの指示

作業を行う場合は、以下を最後に必ず報告すること。

```text
変更内容:
- ...

テスト結果:
- ...

確認したファイル:
- ...

残課題:
- ...

設計評価上の注意:
- ...
```

不明点がある場合は、勝手に物理モデルを決めず、設計メモまたはTODOとして残すこと。

文書や結果を参照する場合は、branch、SHA、status、authority種別を可能な範囲で明記すること。`main`の正式状態とdevelopment branchの最新状態を混同しないこと。

---

## 10. 現在のプロジェクト方向

現在の最上位目的は、圧力伝播、減圧、フラッシング、および気液二相化を解析検討できる実用ツールを、限定scopeから段階的に成立させることである。

現在の優先方向は次のとおりである。

1. Working Tool v0-Bを、計算実行・出力・保存・再現性の基盤として固定する。
2. 既存のHEM liquid-to-two-phase crossing仕様とpipeline depressurization prototypeを再利用する。
3. first crossing後のpressure-wave / flashing couplingを追跡できる限定incrementを構成する。
4. 保存性、finite / positivity、再現性、および代表的なCFL / mesh依存性を、次のphysics領域へ進むためのtargeted gateとして確認する。
5. HEMを平衡baselineとして保持し、HNE / relaxation modelによる相変化遅れ比較へ早期に着手する。
6. U3 B0 / B1 / B2で整備したphysical discharge boundaryを、二相過渡解析へ段階的に接続する。
7. 代表benchmarkおよびPhysical Validationは、Working Vertical Slice成立後に利用目的へ応じて追加する。
8. 適用範囲外、固体CO₂領域、非凝縮性ガス、未承認相関などは、guard、制限、またはfail-closed条件として明示する。

最新の進捗と正式authorityは、この節ではなく次を参照すること。

- `README.md`
- `docs/verification/project_document_authority_map.md`
- `docs/verification/stage7_real_problem_application_strategy.md`
- `docs/verification/stage7_current_gate_snapshot.md`
- `docs/verification/MASTER_VERIFICATION_INDEX.md`
- `docs/verification/stage7_execution_log.md`

---
