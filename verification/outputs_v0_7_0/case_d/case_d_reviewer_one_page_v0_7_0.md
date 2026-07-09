# Case D レビュアー用1枚サマリ — Ver.0.7.0

## 1. 何を見るケースか

**高所部フラッシング識別ケース**  
高所部・下流側で二相化が見えるようにした、手法差確認用ケース。

## 2. 結論

HEMは即時平衡のため広く強く二相化し、HNEは遅れにより弱く出る。DVCMは空洞proxyとして出るが、連続二相音速低下は表さない。

このケースは **手法差を見せる識別ケース**であり、設計採用値ではありません。基準物性は surrogate / amplified discrimination setting です。

## 3. 主要結果

| Model | max alpha/cavity | max xv/equiv | min c/proxy [m/s] | max inventory | unit | max visible length [m] |
|---|---|---|---|---|---|---|
| hem | 0.03069 | 0.02328 | 689.1 | 121.9 | kg vapor | 706.2 |
| hne_tau050 | 0.007449 | 0.005617 | 735 | 39.98 | kg vapor | 743.8 |
| dvcm_legacy | 0.007447 | 0.005616 | 750 | 0.04308 | m3 cavity proxy | 706.2 |

## 4. 一目で見る図

![case_d_alpha_xt_hem_hne_dvcm_v0_7_0](case_d_alpha_xt_hem_hne_dvcm_v0_7_0.png)

## 5. 読み方

- **HEM**: 即時平衡。二相化を強め・早めに出す上限側比較。
- **HNE**: 相変化遅れあり。主評価候補。
- **DVCM**: 従来モデルの空洞 proxy。位置比較には有用だが、連続二相音速低下は表さない。

詳細は担当者用レポートを参照してください。
