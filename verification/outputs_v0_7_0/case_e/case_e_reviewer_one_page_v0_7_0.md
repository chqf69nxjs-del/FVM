# Case E レビュアー用1枚サマリ — Ver.0.7.0

## 1. 何を見るケースか

**飽和近傍ESD急閉識別ケース**  
飽和近傍でESD急閉した場合の、HEM即時平衡とHNE遅れの差を見せるケース。

## 2. 結論

Case Cよりも二相化指標が大きく、HEMとHNEの差が一読で見える。DVCMは空洞発生位置の参考比較として有用。

このケースは **手法差を見せる識別ケース**であり、設計採用値ではありません。基準物性は surrogate / amplified discrimination setting です。

## 3. 主要結果

| Model | max alpha/cavity | max xv/equiv | min c/proxy [m/s] | max inventory | unit | max visible length [m] |
|---|---|---|---|---|---|---|
| hem | 0.03319 | 0.02519 | 684.2 | 97.64 | kg vapor | 700 |
| hne_tau050 | 0.006049 | 0.00456 | 737.8 | 26.03 | kg vapor | 700 |
| dvcm_legacy | 0.00801 | 0.006041 | 750 | 0.0345 | m3 cavity proxy | 700 |

## 4. 一目で見る図

![case_e_alpha_xt_hem_hne_dvcm_v0_7_0](case_e_alpha_xt_hem_hne_dvcm_v0_7_0.png)

## 5. 読み方

- **HEM**: 即時平衡。二相化を強め・早めに出す上限側比較。
- **HNE**: 相変化遅れあり。主評価候補。
- **DVCM**: 従来モデルの空洞 proxy。位置比較には有用だが、連続二相音速低下は表さない。

詳細は担当者用レポートを参照してください。
