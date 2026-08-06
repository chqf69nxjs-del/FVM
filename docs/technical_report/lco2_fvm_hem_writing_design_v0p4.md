# 液化CO₂配管過渡解析 技術報告書 — 執筆設計表 v0.4

## 0. 文書情報

```text
対象範囲:             Stage 1〜Gate 9、U3 B0、U3 B1
構成:                 16章
第12章:               working prose integrated
全文執筆:             NOT COMPLETE
physical validation:  NOT ESTABLISHED
approved design use:  PROHIBITED
```

## 0.1 執筆原則

```text
研究上の問い
→ 固定contract
→ authoritative evidence
→ supported claim
→ prohibited claim
→ next controlled work
```

定量値はevidence matrixに登録してから本文へ使用する。概念図と解析結果図を区別し、解析結果図にはcase、model、backend、version、source SHA、run / artifactを残す。

## 0.2 章別設計

| 章 | 中心メッセージ | 主なsource | Claim limit |
|---:|---|---|---|
| 1 | 液化CO₂過渡には段階的verificationが必要 | application strategy / literature | current toolの実用承認を示さない |
| 2 | 共通基盤は一次元保存形FVM | governing source / Gate records | 3-Dまたは全物理を含むと書かない |
| 3 | phase classification、projection、sound speedを分離 | PR #54–#72 / Gate 5–7 | projectionをnucleation modelとしない |
| 4 | first-order Rusanov / CFLをcontrolとして固定 | source / Gate contracts | 高次精度を承認済みとしない |
| 5 | Stage 1〜U3 B1は不確かさを順に分離 | master / snapshot | COMPLETEをphysical validationと混同しない |
| 6 | 単相wave / reflection / boundary controlを確認 | archived master | physical accuracy claim禁止 |
| 7 | raw crossingとaccepted recoveryを確認 | PR #70–#72 | physical nucleation claim禁止 |
| 8 | prescribed-boundary pipeline analogueを実行 | PR #74–#91 | physical orificeと呼ばない |
| 9 | fixed continuationとlocalized chatterを診断 | Gate 6–7 | root cause claim禁止 |
| 10 | Gate 8–9でCFL-sensitive depthをcharacterize | Gate 8–9 closeout | independence / root cause claim禁止 |
| 11 | B0液体limit componentを独立比較 | B0 closeout | physical boundary claim禁止 |
| 12 | B1単相圧縮性・臨界状態componentを独立比較 | B1 closeout / artifact | two-phase / physical boundary claim禁止 |
| 13 | 公知文献との関係を整理 | literature registry | literatureをcurrent validationに代用しない |
| 14 | 現在の適用限界を明示 | snapshot / approval flags | 適用可能度を主観スコア化しない |
| 15 | FVM coupling、高所、pump tripの順序を固定 | B1 closeout / application strategy | date commitmentまたは飛び級承認禁止 |
| 16 | 成立・未成立・次段階を均衡して結論 | chapters 1–15 | physical/design/production claim禁止 |

## 0.3 第12章の構成

```text
12.1 目的とverificationの意味
12.2 対象範囲と除外範囲
12.3 locked component law
12.4 critical-state search and choking rule
12.5 Reference / Adapter independence
12.6 fixed matrix and authoritative execution
12.7 quantitative result
12.8 B0 limiting behavior and guards
12.9 supported / prohibited claims
12.10 next controlled work
12.11 conclusion and provenance
```

## 0.4 執筆完了条件

- 全定量値がevidence matrixへ登録済み。
- 図表captionにprovenanceとclaim limitがある。
- B0 / B1をphysical boundaryと表現していない。
- Gate 9 root causeを承認していない。
- physical validation、design use、production activationがfalse。
- 章番号とcross-referenceがv0.4 contractに一致する。
