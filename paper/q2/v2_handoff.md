# Q2 V2 论文手交接清单

- 问题：Q2
- 阶段：V2 n100 开发粗筛
- 当前状态：REVIEWING
- 更新日期：2026-08-08
- 主责建模师：蔡乔夕（P1/P2）、钟江铭（P0 接入）
- 交叉复核：钟江铭（待人工签字）

本文件是论文手接收 Q2 V2 材料的唯一入口。论文手可据此起草方法和开发结果段落，但不得把本阶段数字写成 n200 正式选型、最终模型或竞赛最终结论。

## 交接物索引

| 交接物 | 文件 | 用途 |
|---|---|---|
| V1 问题分析 | [`outputs/q2/reports/v1_problem_analysis.md`](../../outputs/q2/reports/v1_problem_analysis.md) | 目标、候选、约束和回退路线 |
| V2 模型与运行报告 | [`outputs/q2/reports/v2_model_report.md`](../../outputs/q2/reports/v2_model_report.md) | 公式、实现、实际协议、开发结果和风险 |
| 四配置汇总 | [`outputs/q2/tables/v2_n100_current_summary.csv`](../../outputs/q2/tables/v2_n100_current_summary.csv) | P0、P1、P2-OFF、P2-ON 汇总数字 |
| 配对差值 | [`outputs/q2/tables/v2_n100_current_paired_differences.csv`](../../outputs/q2/tables/v2_n100_current_paired_differences.csv) | P1-P0、P2-ON-P2-OFF 的逐 seed 差值 |
| 完整运行明细 | [`outputs/q2/tables/v2_n100_current_run_details.csv`](../../outputs/q2/tables/v2_n100_current_run_details.csv) | 40 条运行状态、参数、指标和路径 |
| 比较快照 | [`outputs/q2/tables/v2_n100_current_comparison_snapshot.json`](../../outputs/q2/tables/v2_n100_current_comparison_snapshot.json) | 代码哈希、预算、种子和输入表 |
| 建模入口 | [`src/Q2/__main__.py`](../../src/Q2/__main__.py) | 单次与批量运行 |
| 汇总入口 | [`src/Q2/summarize.py`](../../src/Q2/summarize.py) | 从四份冻结明细重建交接表 |
| Q2 测试 | [`tests/test_q2.py`](../../tests/test_q2.py) | 轮廓、HPWL、审计、初始化和可复现性 |

## 可直接转写的方法口径

设模块总面积为 `A_B`，题面死区比例为 `d=0.15`，固定正方形边长为

```text
L = sqrt(A_B * (1 + d)).
```

轮廓为 `(0,0,L,L)`。模块可以旋转 0/90 度，边界接触合法，正面积重叠非法。模块引脚位于旋转后矩形中心，Terminal 使用 `.pl` 中的绝对坐标，不随轮廓变化。

单个网络的半周长线长为

```text
HPWL_net = (max x_pin - min x_pin) + (max y_pin - min y_pin),
HPWL = sum_net HPWL_net.
```

搜索采用严格可行性优先：不可行布局之间比较轮廓溢出；进入合法域后比较 HPWL。最终候选由共享评价器和独立审计分别复算。

## 符号、参数与单位

| 符号/字段 | 含义 | 单位/方向 |
|---|---|---|
| `A_B` / `module_area` | 模块总面积 | 坐标单位² |
| `d` / `dead_space_ratio` | `deadspace/module_area` | 无量纲；本阶段固定 0.15 |
| `rho` | `deadspace/area=d/(1+d)` | 无量纲；本阶段为 0.15/1.15 |
| `L` / `outline_side` | 固定正方形边长 | 坐标单位 |
| `HPWL` | 所有网络 HPWL 之和 | 坐标单位；越小越好 |
| `first_feasible_evaluation` | 首次得到合法解时的累计评价次数 | 次；越小越好 |
| `runtime` | 单次墙钟时间 | 秒 |

冻结开发协议：实例 `n100`，种子 `2101-2110`，每次最多 30000 次评价、60 秒、4 次重启；优化器代码哈希见比较快照。

## 当前可引用的开发观察

以下数字只能标注为“n100 开发粗筛”：

- 四个配置均为 10/10 合法，正式评价与独立审计均为 10/10 一致。
- P0、P1、P2-OFF、P2-ON 的中位 HPWL 分别为 `297261.0`、`263293.5`、`263293.5`、`248082.75`。
- P1 在 10/10 个配对 seed 上低于 P0，配对差值中位数为 `-33967.5`，相对差值中位数为 `-11.4268%`。
- P2-ON 在 10/10 个配对 seed 上低于 P2-OFF，配对差值中位数为 `-15541.25`，相对差值中位数为 `-6.0178%`，合法率未下降。

## 数字追溯

| 数字 | 直接来源 | 运行证据 |
|---|---|---|
| 四配置合法率、最好值和中位数 | `v2_n100_current_summary.csv` | `v2_n100_current_run_details.csv` 对应 40 条记录 |
| P1-P0 配对差值 | `v2_n100_current_paired_differences.csv` 的 `P1-minus-P0` | P0/P1 当前批次的逐 seed 布局与日志 |
| P2 ON/OFF 配对差值 | 同表的 `P2-ON-minus-P2-OFF` | P2-OFF/P2-ON 当前批次的逐 seed 布局与日志 |
| 代码哈希、种子、预算 | `v2_n100_current_comparison_snapshot.json` | 四份 `*_current_config_snapshot.json` |

## 论文中暂时禁止的表述

- 不得写“P2 是最终模型”“P2 已通过正式选型”或“P2 总体显著优于 P1/P0”。
- 不得把 n100 数字写入最终摘要、最终结论或 n200/n300 结果表。
- 不得把 `timeout` 写成失败或不可行；P0 十次 timeout 均保留了合法布局。
- 不得忽略成对并行运行对墙钟吞吐的影响；正式时间比较须等待冻结的 n200 顺序运行协议。

## 需要论文手确认的事项

1. Q2 方法章节是否采用“P0 独立基线—P1 稳健主干—P2 超图软初始化”的叙述顺序。
2. n100 开发观察是否只放入“模型开发/初步实验”，并明确标记 `REVIEWING`。
3. 正式结果图和统计检验留到 n200/V3 后制作，本阶段不提前绘制论文正式图。
4. Q3 若复用 P2，必须注明 Q2 当前只在 `d=0.15` 验证，不能外推到更小死区边界。

## 下一阶段

- 由交叉复核人核对公式、配置、40 条明细和两组配对差值并签字；
- 冻结 n200 的主预算、顺序运行方式、机器/线程与候选；
- n200 正式比较通过后，才决定 Q2 最终采用 P1 或 P2，并更新论文确定数字。
