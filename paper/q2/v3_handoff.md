# Q2 V3 论文交接（VERIFIED）

状态：`VERIFIED`。2026-08-09，人工复核人（用户）明确接受 Q2 V3 的证据边界并批准升级；本材料不是 `FINAL`。

正式选型使用 n200 的纠正版汇总 `outputs/q2/tables/v3_n200_summary_v2.json`：P1 的 HPWL 中位数为 504410.5，优于 P0 的 543792.0；P2 为 505079.0。首次合法解时间中位数分别为 P0 0.023744 秒、P1 0.008188 秒、P2 0.170665 秒，因此 P2 同预算判定为 `report_only`，冻结 P1。

n300 留出只比较冻结的 P1 与 P0。P1 在 30 个同种子配对中均取得更低 HPWL，中位数为 776636.75；P0 为 831802.0。该结果不允许用于重新选型或继续调参。

论文图：[`v3_final_layouts.png`](../../outputs/q2/figures/v3_final_layouts.png)与[`v3_model_comparison.png`](../../outputs/q2/figures/v3_model_comparison.png)。源数据为 `outputs/q2/tables/v3_figure_layout_sources.csv` 与 `v3_figure_model_comparison.csv`。

边界：n100 只作开发证据；timeout 保留；P0 不是 ground truth；P1/P2 均不构成全局最优、收敛或文献领先证明；不得迁入 `outputs/q2/final/`。
