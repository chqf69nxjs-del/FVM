# AGENTS.md

# 液化ガス管路システム信頼性評価ツール 開発ルール

このリポジトリは、液化ガス、主に LCO₂ を対象とした一次元管路過渡解析・信頼性評価ツールの開発用リポジトリである。

対象は、陸上貯蔵タンクから輸送船内タンクへ液化ガスを移送する管路システムであり、ESD弁急閉、ポンプ急停止、高所部フラッシング、飽和近傍二相化などの過渡現象を評価する。

---

## 1. 基本方針

* 主ソルバは保存形有限体積法 FVM とする。
* MOC は主ソルバではなく、単相水撃・圧力波到達時刻確認用の verification solver とする。
* DVCM は主評価モデルではなく、legacy comparison proxy として扱う。
* HEM / HNE 系モデルを、液化ガスの二相化・フラッシング・相変化遅れ評価の主候補とする。
* 実在 LCO₂ 物性が未承認の結果を、設計評価結果と呼ばない。
* surrogate_lco2 による結果は、開発確認・試評価・識別ケース用として扱う。

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

将来拡張として、非凝縮性ガス用に `rho*Ync` を追加する可能性がある。

### HEM

HEM は局所熱力学平衡を仮定するモデルである。
即時平衡に基づく二相化応答を評価するために用いる。

### HNE

HNE は有限緩和時間により、平衡状態への遅れを表すモデルである。
緩和時間 `tau` の値や相関式は、勝手に確定値として扱わないこと。

### DVCM

DVCM は古典的な空洞発生評価との比較用 proxy とする。
完全な MOC-DVCM ソルバとして扱わないこと。

---

## 4. 物性計算モジュールの方針

物性 backend とは、FVM ソルバから呼び出され、圧力、温度、密度、内部エネルギーなどの状態量から、LCO₂ の物性値を返す物性計算モジュールである。

想定する backend は以下である。

* `surrogate_lco2`: 開発・動作確認用
* `coolprop_co2`: CoolProp による実在物性候補
* `refprop_co2`: REFPROP による高精度物性候補
* `reference_table_lco2`: 承認済み基準 CSV による設計評価候補

CoolProp や REFPROP が利用できない環境では、テストを失敗させるのではなく、明示的に skip すること。

---

## 5. 設計評価に関する禁止事項

以下を行ってはならない。

* surrogate_lco2 の結果を設計評価結果と呼ぶ。
* validation 未完のモデル結果を、設計上確定した評価として扱う。
* DVCM proxy を HEM/HNE と同等の熱力学モデルとして説明する。
* HNE の緩和時間 `tau` を根拠なく固定する。
* 物性 backend の design-use status を明記せずに結果を出力する。
* 概念図を解析結果図のように扱う。

---

## 6. テスト・Verification 方針

変更後は、可能な範囲で以下を確認する。

```bash
PYTHONPATH=src pytest -q
```

追加・変更した機能に対して、少なくとも以下の観点を確認する。

* 既存テストが壊れていないこと
* 保存性に関する budget residual が悪化していないこと
* backend 名が出力・レポートに残ること
* surrogate と実在物性 backend の扱いが混同されないこと
* CoolProp 未導入環境では関連テストが skip されること

---

## 7. レポート・可視化方針

レポートは原則として日本語中心で作成する。

ただし、以下は英語表記を残してよい。

* 変数名
* ファイル名
* backend 名
* case 名
* HEM / HNE / DVCM
* onset time
* active length
* max alpha
* max xv

レポート生成では、以下を必ず意識する。

* 概念図と解析結果図を混同しない。
* 解析結果図には case、model、backend、version を明記する。
* reviewer report、engineer report、technical appendix を分ける。
* コメントは解析データから読み取れることだけを書く。
* いきなり定量表を出さず、まず解析対象と評価指標を説明する。

---

## 8. 開発作業の進め方

1回の作業は小さく分けること。

望ましい作業単位の例：

* 物性 backend インターフェースの整理
* CoolProp backend の最小実装
* 飽和線 verification の追加
* reference CSV schema の追加
* report 出力への backend 名追加
* README / docs の更新

避けるべき作業：

* 複数の物理モデルを同時に大きく変更する
* ソルバ構造とレポート構造を同時に大きく変更する
* テストなしで挙動を変える
* 既存の検証ケースを無断で削除する

---

## 9. Codex / Agent への指示

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

不明点がある場合は、勝手に物理モデルを決めず、設計メモまたは TODO として残すこと。

---

## 10. 現在の優先作業

現在の優先順位は以下である。

1. 現行コード構成の棚卸し
2. 物性計算モジュールの共通インターフェース整理
3. CoolProp backend の最小実装
4. 物性 verification test の追加
5. reference CSV acceptance gate の整備
6. Case C/D/E/A の実在物性再評価
7. 動的ポンプモデルの検討
8. Validation 計画の具体化

---
