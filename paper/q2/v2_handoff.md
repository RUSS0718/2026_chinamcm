# Q2 V2 论文手交接清单

- 问题：Q2
- 阶段：V2 `n100` 修复验收
- 当前状态：`REVIEWING`
- 更新日期：2026-08-08
- 实现负责人：蔡（P1/P2）；钟江铭（P0 接入与交叉复核）
- 论文手交叉复核：钟江铭，待人工签字

本清单是 Q2 V2 修复材料的唯一论文交接入口。当前数字只能用于方法章节草稿、开发记录和待复核清单，不得写成 n200 正式选型、最终模型或竞赛最终结论。

## 交接物索引

| 材料 | 文件 | 用途 |
|---|---|---|
| V1 问题分析 | [`outputs/q2/reports/v1_problem_analysis.md`](../../outputs/q2/reports/v1_problem_analysis.md) | 目标、候选、约束和回退路线 |
| V2 修复报告 | [`outputs/q2/reports/v2_model_report.md`](../../outputs/q2/reports/v2_model_report.md) | 公式、实现、协议、结果和风险 |
| 主组明细（50 条） | [`outputs/q2/tables/v2_n100_repaired_fix2_run_details.csv`](../../outputs/q2/tables/v2_n100_repaired_fix2_run_details.csv) | 五组 × 十个 seed 的完整记录 |
| 主组汇总 | [`outputs/q2/tables/v2_n100_repaired_fix2_summary.csv`](../../outputs/q2/tables/v2_n100_repaired_fix2_summary.csv) | 合法率、状态、HPWL、IQR、预算和运行时间 |
| 主组配对差值 | [`outputs/q2/tables/v2_n100_repaired_fix2_paired_differences.csv`](../../outputs/q2/tables/v2_n100_repaired_fix2_paired_differences.csv) | `P1-P0`、`P1-A2-BASE`、`P2-ON-P2-OFF` |
| 主组比较快照 | [`outputs/q2/tables/v2_n100_repaired_fix2_comparison_snapshot.json`](../../outputs/q2/tables/v2_n100_repaired_fix2_comparison_snapshot.json) | 代码/数据哈希、预算、种子和配置 |
| 随机压力明细（20 条） | [`outputs/q2/tables/v2_n100_repaired_fix2_a2_stress_run_details.csv`](../../outputs/q2/tables/v2_n100_repaired_fix2_a2_stress_run_details.csv) | A2/P1 随机初始化诊断 |
| 随机压力汇总 | [`outputs/q2/tables/v2_n100_repaired_fix2_a2_stress_summary.csv`](../../outputs/q2/tables/v2_n100_repaired_fix2_a2_stress_summary.csv) | 合法率、`no_feasible` 和首次合法评价 |
| 运行入口 | [`src/Q2/__main__.py`](../../src/Q2/__main__.py) | 单次/批量运行与快照 |
| 汇总入口 | [`src/Q2/summarize.py`](../../src/Q2/summarize.py) | 五组主实验和两组压力实验的门槛检查 |
| Q2 测试 | [`tests/test_q2.py`](../../tests/test_q2.py) | SA、预算、初始化消融和哈希覆盖 |

## 可直接转写的方法口径

模块总面积为 `A_B`，死区比例固定为 `d=0.15`，固定正方形轮廓边长为

```text
L = sqrt(A_B * (1 + d)).
```

模块允许 `0/90` 度旋转；边界接触合法，正面积重叠非法。引脚为旋转后模块矩形中心，Terminal 采用 `.pl` 的绝对坐标。网络 HPWL 为各网络 x/y 半周长之和。

搜索轨迹可以临时接受不可行状态；最佳解保存采用严格的可行性优先：先比较合法性，再在合法解中比较 HPWL。正式评价和独立审计分别复算最终布局。

P0-GROUND 使用独立 Sequence Pair 与经典几何 SA。四个 restart 都从合法 shelf 编码，只随机化已有行内次序；前 100 个邻域样本标定初温到接受率 `0.9`，样本计入 `30000` 次评价预算；降温为 `T(k)=T0*(10^-3)^(k/max(N-1,1))`，固定罚强度 `10.0`。P0 的角色是可信独立参考基线，不是 ground truth 或精确最优。

主实验配置如下：

| 配置 | 候选 | 自适应约束 | 超图初始化 | 初始化 |
|---|---|---:|---:|---|
| P0-GROUND | Q2-SP/classic-SA | OFF | OFF | shelf |
| A2-BASE | Q2-BT/Fast-SA | OFF | OFF | shelf |
| P1 | Q2-BT/Fast-SA | ON | OFF | shelf |
| P2-OFF | Q2-HG/Fast-SA | ON | OFF | shelf |
| P2-ON | Q2-HG/Fast-SA | ON | ON | shelf |

P2-OFF 只使用中性行内顺序，P2-ON 只将该顺序换成当前超图顺序；合法 shelf 几何直接作为第一评价，B*-Tree 状态只用于后续搜索。两者的行成员、旋转、`init_seed`、`search_seed` 保持一致。P1 与 P2-OFF 的确定性字段和最终布局逐 seed 一致，是本轮组件隔离的硬门槛。

## 协议快照

- 实例：`n100`
- seeds：`1101–1110`
- 每次评价预算：`30000`
- 时间安全上限：`180 s`
- restart：`4`
- 顺序：单进程、单线程、顺序运行
- RNG：`random.Random`（MT19937）
- fix2 全部 70 条运行代码哈希：`5182e532feca7ba4337692b112b06f181d6f79ee85596eacf83c9109b14fb709`
- n100 数据哈希：`6be0918f672ac3bbdf8300aaeddedf4f348a2b1a1ea74f5975cc084ba0b2ec13`

代码快照使用仓库相对路径、LF 规范字节，覆盖 Q2、Q1 Sequence Pair/B*-Tree、解析器、评价器、审计器和几何模块；fix2 的 70 条运行使用同一代码哈希，每个配置快照另存逐文件 SHA-256 和运行环境。

## 当前可引用的 n100 开发观察

五个主组均为 10/10 合法、10/10 正式评价与审计一致、10/10 完成 30000 次评价：

| 配置 | 最好 HPWL | 中位 HPWL | IQR | 中位运行时间/s |
|---|---:|---:|---:|---:|
| P0-GROUND | 288250.0 | 291242.75 | 1505.625 | 146.5522 |
| A2-BASE | 247846.0 | 253640.75 | 7956.75 | 77.6709 |
| P1 | 246188.5 | 254170.25 | 6568.875 | 78.4244 |
| P2-OFF | 246188.5 | 254170.25 | 6568.875 | 77.7416 |
| P2-ON | 245513.0 | 249481.0 | 5036.0 | 76.5186 |

配对中位差值为：`P1-P0=-36271.25`（10/10 seed 更低）、`P1-A2-BASE=-275.25`（6/10 更低）、`P2-ON-P2-OFF=-5427.25`（8/10 更低）。P1 与 P2-OFF 的差值逐 seed 全为 `0.0`。

随机初始化压力组必须一并保留：`A2-BASE-RANDOM` 为 0/10 合法、10/10 `no_feasible`；`P1-RANDOM` 为 1/10 合法，其余 9 次 `no_feasible`，唯一合法 seed 1104 的首次合法评价为 6439。压力结果只说明初始化风险，不是生产候选排名。

## 论文中暂时禁止的表述

- “P0 是 ground truth、全局最优或精确最优”；
- “P1/P2 已通过最终选型”或“P2 总体显著优于 P1”；
- 将 n100 开发观察写入最终摘要、最终结论或 n200/n300 结果表；
- 把 `no_feasible` 或 `timeout` 改写成数学不可行证明；
- 把本轮 P2 描述成包含 Terminal 空间牵引或局部精确修复。

## 交叉复核清单

1. 钟江铭复核 P0 seed 1101–1110 的布局、HPWL、评价数、接受数、初始 HPWL 和四个 restart 记录。
2. 逐 seed 检查 P1/P2-OFF 的布局、正式评价、独立审计、种子轨迹完全相同。
3. 检查所有 70 条布局的共享评价器和独立审计结果，确认压力组失败状态被保留。
4. 确认全量 `unittest` 19/19 通过，并在 `REVIEWING` 状态下核对报告、汇总表、快照和代码入口参数一致。
5. n200 前另行冻结主预算、机器/线程、顺序运行方式和 RNG；本轮不运行 n200/n300。

P0 seed `1101`、`1102` 已在 `tmp/v2_n100_p0_determinism_fix2_20260808/` 临时目录使用最终代码完整复跑；布局、HPWL、评价/接受轨迹和 restart 种子字段逐 seed 一致，运行时间与路径不参与比较。

完成人工复核后，若任何公式、参数、数据、代码哈希或关键数字发生变化，必须退回 `REVIEWING` 并重跑受影响的实验。
