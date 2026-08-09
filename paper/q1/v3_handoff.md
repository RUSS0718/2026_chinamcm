# Q1 V3 论文交接（VERIFIED）

## 证据包

- 正式运行记录：`outputs/q1/_runtime/v3_n200`。
- 运行时快照：`outputs/q1/tables/v3_n200_execution_manifest.json`。
- 机器可读汇总：`outputs/q1/tables/v3_n200_summary.json`。
- 七配置表：`outputs/q1/tables/v3_n200_candidate_summary.csv`。
- 汇总报告：`outputs/q1/reports/v3_n200_summary.md`。
- 注册核验：140/140 discovered，0 missing，0 duplicate marker。
- 运行时 hashes：core `3191e8fa3cfd8aaa7948395b9026ff11bb50871a09425b05f1d85c6a8a6a5aaa`；data `bed652bf55c2034b04a1c1bbe97ad617e027c11736bf069727a63baf575720ef`；execution runner `c5701e2a1c429f67aa20141e5c114741d2e50ab3151875a4ee160e39d1e19bb0`；execution overall `67cae4dceb0bcd8b0c01d21f6513782ba3fd8bb70dfcba659bcb4179ad02d2ef`。
- 汇总分析 hashes：runner `a26b2992fc35a1bb0490cbf60c3f04d3deffdd7418c4e8611f6de5ba44295263`；overall `cf20b1d19a0ed2a75494e8065479b88f8262890dba5f9898aa734b29a1561b6c`。分析 hash 不得回写为运行时 hash。

## 可供论文复核的结果表述

在预注册的 n200、100000 evaluations、180 s、4 restarts、20 个 seed 条件下，Q1-G、Q1-SP、Q1-BT、Q1-BT-D 四个主候选均通过 legal/audit hard gate；机械排名暂选 Q1-BT，其 area 为 194555.0--202383.0（中位数 199229.5、IQR 2859.75、p90 201168.9），aspect ratio 为 3.5836909871244633--5.886486486486486（中位数 4.433394605129114）。Q1-G 的 20 条记录为 success，其余六配置共 120 条记录均为 timeout；timeout 仅是有限预算观测，不得写成最优性证明。

三个消融配置（directed-only、dedup-only、both）独立报告完整性与比较，不进入主候选排名。Q1-BT-D 的 legal 非劣条件通过，但 area 非劣和稳定性改善条件未通过，故仅 `report_only`；其 area 为 394524.0--676512.0（中位数 495628.0），不能据此替代 Q1-BT。

## 需要复核的偏差与限制

所有 140 个 n200 marker 均未记录 `first_feasible_evaluation`。结果以 `not_recorded_protocol_deviation` 明确记录，不能补写或推断该指标。运行与分析 hashes 分层保存；shared manifest 后续变化不得改写运行时快照。2026-08-09，人工复核人（用户）接受该偏差以及 n300 独立留出报告，批准本交接为 `VERIFIED`，但不是 `FINAL`，也不涵盖 Q2、Q3 或 Q4。

论文图：[`v3_final_layouts.png`](../../outputs/q1/figures/v3_final_layouts.png)与[`v3_model_comparison.png`](../../outputs/q1/figures/v3_model_comparison.png)。
