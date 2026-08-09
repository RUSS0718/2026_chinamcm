# Q1 V3 n200 正式汇总（VERIFIED）

## 运行范围与证据来源

- 注册集合：7 个配置 × 20 个种子 = 140 条；种子为 2201--2220。
- 正式命令：`D:\Anaconda\envs\CA-py310\python.exe -B -m src.v3 run --problem q1 --execute`。
- 汇总命令：`D:\Anaconda\envs\CA-py310\python.exe -B -m src.v3 summary --problem q1 --input outputs/q1/_runtime/v3_n200 --output outputs/q1/tables/v3_n200_summary.json`。
- 正式运行根：`outputs/q1/_runtime/v3_n200`；此前 workers=1 的 28 条记录在独立归档中，已作废，不参与本汇总。
- 注册核验：registered=140、discovered=140、missing=0、重复 marker=0、解析错误=0。
- 运行时快照：[`v3_n200_execution_manifest.json`](../tables/v3_n200_execution_manifest.json)。其中 execution runner SHA-256 为 `c5701e2a1c429f67aa20141e5c114741d2e50ab3151875a4ee160e39d1e19bb0`，execution overall 为 `67cae4dceb0bcd8b0c01d21f6513782ba3fd8bb70dfcba659bcb4179ad02d2ef`，基线 commit 为 `832e8bde7d9a857c4023693f1a67249e25f07d5d`。
- 运行时 Q1 core code hash：`3191e8fa3cfd8aaa7948395b9026ff11bb50871a09425b05f1d85c6a8a6a5aaa`；`n200.blocks` data hash：`bed652bf55c2034b04a1c1bbe97ad617e027c11736bf069727a63baf575720ef`。
- 运行后分析代码分层：当前 runner SHA-256 `a26b2992fc35a1bb0490cbf60c3f04d3deffdd7418c4e8611f6de5ba44295263`，当前 shared overall `cf20b1d19a0ed2a75494e8065479b88f8262890dba5f9898aa734b29a1561b6c`。该分层 hash 只约束本次汇总分析，不冒充运行时 hash。

## 七配置完整表

详见 [`v3_n200_candidate_summary.csv`](../tables/v3_n200_candidate_summary.csv)。每行均为 20/20 记录、0 缺失、20 条审计匹配记录和 legal_rate=1.0。

| 配置 | area 最小 | area 中位数 | area 最大 | area IQR | area p90 | aspect 最小 | aspect 中位数 | aspect 最大 | aspect IQR | aspect p90 | success | timeout |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Q1-G | 284016.0 | 284016.0 | 284016.0 | 0.0 | 284016.0 | 123.27083333333333 | 123.27083333333333 | 123.27083333333333 | 0.0 | 123.27083333333333 | 20 | 0 |
| Q1-SP | 219177.0 | 227832.5 | 235296.0 | 4777.25 | 231072.4 | 1.0020833333333334 | 1.0648091133004924 | 1.2712264150943395 | 0.11932814288678095 | 1.1824422913408144 | 0 | 20 |
| Q1-BT | 194555.0 | 199229.5 | 202383.0 | 2859.75 | 201168.9 | 3.5836909871244633 | 4.433394605129114 | 5.886486486486486 | 0.8536875288268311 | 5.300878692377544 | 0 | 20 |
| Q1-BT-D | 394524.0 | 495628.0 | 676512.0 | 119118.0 | 627994.4 | 6.337209302325581 | 8.551946676083695 | 10.301801801801801 | 1.592821525303476 | 10.1226048362412 | 0 | 20 |
| Q1-BT-directed-only | 394524.0 | 495628.0 | 676512.0 | 119118.0 | 627994.4 | 5.988372093023256 | 8.551946676083695 | 10.301801801801801 | 1.592821525303476 | 10.1226048362412 | 0 | 20 |
| Q1-BT-dedup-only | 193110.0 | 199922.5 | 203308.0 | 2779.75 | 202926.9 | 3.4522821576763487 | 4.520086291692747 | 5.886486486486486 | 0.7752754096472074 | 5.397856558494683 | 0 | 20 |
| Q1-BT-both | 394524.0 | 495628.0 | 676512.0 | 119118.0 | 627994.4 | 6.337209302325581 | 8.551946676083695 | 10.301801801801801 | 1.592821525303476 | 10.1226048362412 | 0 | 20 |

所有配置的 status 计数合计为 success=20、timeout=120、no_feasible=0、crash=0。timeout 是有限预算观测，不是最优性证明。

## 主候选结论

主排名只包含预注册的四个主候选 Q1-G、Q1-SP、Q1-BT、Q1-BT-D；三个消融配置不进入排名。四个主候选均通过 hard gate（legal_rate≥0.90、audit_match_runs=20、missing_runs=0），机械排名选中 Q1-BT。该选择只表示注册规则下的暂定选择，不依赖 P2 稳定性字段；`p2_stability_gain=false` 仅表示 Q1-BT-D 未满足 P2 稳定性改善条件，不替代人工复核。

## P2 与消融结论

消融配置单独记录 completeness 和比较，不参与主排名。Q1-BT-D 相对 Q1-BT 的 `p2_legal_noninferior=true`，但 `p2_area_noninferior=false`、`p2_stability_gain=false`，因此 `p2_ablation=report_only`。Q1-BT-D area 中位数为 495628.0，而 Q1-BT 为 199229.5。directed-only、dedup-only、both 的完整性与指标见 JSON/CSV；没有把任何消融配置晋级为主候选。

## 协议偏差与阶段边界

140 条 marker 均未记录 `first_feasible_evaluation`；汇总将其明确标为 `not_recorded_protocol_deviation`，顶层 `protocol_deviations` 记录 7 个配置，未将缺失值推断为 1 或其他数值。2026-08-09，人工复核人（用户）明确接受该协议偏差、运行/分析 hash 分层和机械选型边界，批准本阶段为 `VERIFIED`，但不是 `FINAL`。n300 留出验证见独立报告。

论文图：[代表布局](../figures/v3_final_layouts.png)与[模型比较](../figures/v3_model_comparison.png)；对应源数据为 `v3_figure_layout_sources.csv` 与 `v3_figure_model_comparison.csv`。
