# Q2 V2：P0 独立参考基线与 P1/P2 n100 修复验收报告

- 阶段：`VERIFIED`
- 更新：2026-08-09
- 当前负责人：蔡已完成 P1/P2 实现；钟江铭负责 P0 接入与交叉复核
- 范围：仅 Q2 V2 的 `n100` 修复验收；人工复核接受代码哈希 `5182e532…` 的历史运行快照，不包含 `n200/n300`，不标记 `FINAL`

本报告记录修复后的可复现实验材料。P0-GROUND 是独立的 Sequence Pair + 经典 SA 参考基线，目标是提供可信的比较地面，不是数学意义上的 ground truth、精确最优解或最终模型。

## 1. 固定问题定义

模块总面积记为 `A_B`，题面死区比例固定为 `d=0.15`，因此

```text
L = sqrt(A_B * (1 + d))
rho = d / (1 + d)
```

固定轮廓为 `(0, 0, L, L)`。模块允许 `0/90` 度旋转；边界接触合法，正面积重叠不合法。模块引脚取旋转后矩形中心，Terminal 使用 `.pl` 中的绝对坐标并直接参与 HPWL：

```text
HPWL_net = (max x_pin - min x_pin) + (max y_pin - min y_pin)
HPWL = sum_net HPWL_net
```

搜索轨迹允许临时接受不可行状态；最佳解保存采用严格的“合法优先、合法解中 HPWL 最小”规则。正式评价和独立 `audit_layout` 都必须重新计算同一布局。

## 2. 修复后的候选定义

| 配置 | 候选/SA | 自适应约束 | 超图初始化 | 初始化 |
|---|---|---:|---:|---|
| P0-GROUND | Q2-SP / classic SA | OFF | OFF | 合法 shelf |
| A2-BASE | Q2-BT / Fast-SA | OFF | OFF | 合法 shelf |
| P1 | Q2-BT / Fast-SA | ON | OFF | 合法 shelf |
| P2-OFF | Q2-HG / Fast-SA | ON | OFF | 合法 shelf |
| P2-ON | Q2-HG / Fast-SA | ON | ON | 合法 shelf |

另有两个只用于诊断初始化脆弱性的压力组：`A2-BASE-RANDOM`、`P1-RANDOM`。生产候选不采用随机初始布局。

### P0-GROUND 的协议

- 四个 restart 都从合法 shelf 编码为独立 Sequence Pair；只在保持行成员、旋转和容量不变的条件下随机化行内顺序。
- 每个 restart 派生独立的 `init_seed` 与 `search_seed`。
- 前 100 个邻域样本用于把初温标定到初始接受率 `0.9`，这些评价计入总预算。
- 其余搜索使用经典几何降温：`T(k)=T0*(10^-3)^(k/max(N-1,1))`，固定罚强度为 `10.0`。
- `sa_schedule=classic` 被强制记录；Q2-SP 不能误配 Fast-SA。

P1/P2 的消融只改变一个组件：合法 shelf 几何直接作为每个 restart 的第一评价，B*-Tree 状态只用于后续搜索；P2-OFF 使用中性行内顺序，P2-ON 仅替换为超图顺序。两组的行成员、旋转、restart 子种子和搜索随机流逐 seed 一致；P1 与 P2-OFF 的确定性字段和最终布局也逐 seed 完全一致。

## 3. 运行协议与可追溯性

- 实例：`n100`
- 种子：`1101–1110`，每组恰好 10 个唯一 seed
- 每次最多 `30000` 次评价，安全上限 `180 s`
- 四次 restart，单进程、单线程、顺序运行
- RNG：`random.Random`（MT19937）
- 新结果目录：`outputs/q2/_runtime/v2_n100_repaired_fix2/`
- 旧 `v2_n100_current_*` 和旧 `2101–2110` 结果原样保留，仅作为历史开发证据，不用于组件归因

fix2 的 70 条运行（五个主组和两组压力组）使用同一代码哈希：

```text
5182e532feca7ba4337692b112b06f181d6f79ee85596eacf83c9109b14fb709
```


数据哈希（n100 三个原始输入，LF 规范字节）：

```text
6be0918f672ac3bbdf8300aaeddedf4f348a2b1a1ea74f5975cc084ba0b2ec13
```

代码快照按仓库相对路径记录 Q2 源码、Q1 Sequence Pair/B*-Tree 依赖、解析器、评价器、审计器和几何模块；配置快照同时记录逐文件 SHA-256、Python/平台、执行方式、候选参数和数据文件 SHA-256。

## 4. 主实验结果

所有主组均完成 10/10 次、每次 30000 次评价；正式评价与独立审计逐行一致。

| 配置 | 合法 | audit 一致 | 完整预算 | 状态 | 最好 HPWL | 中位 HPWL | IQR | 中位首次合法评价 | 中位运行时间/s | 中位相对初始改进 |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| P0-GROUND | 10/10 | 10/10 | 10/10 | success 10/10 | 288250.0 | 291242.75 | 1505.625 | 1 | 146.9346 | 0.0 |
| A2-BASE | 10/10 | 10/10 | 10/10 | success 10/10 | 247846.0 | 253640.75 | 7956.75 | 1 | 77.6709 | -37644.25 |
| P1 | 10/10 | 10/10 | 10/10 | success 10/10 | 246188.5 | 254170.25 | 6568.875 | 1 | 78.4244 | -36271.25 |
| P2-OFF | 10/10 | 10/10 | 10/10 | success 10/10 | 246188.5 | 254170.25 | 6568.875 | 1 | 77.7416 | -36271.25 |
| P2-ON | 10/10 | 10/10 | 10/10 | success 10/10 | 245513.0 | 249481.0 | 5036.0 | 1 | 76.5186 | -13343.0 |

这里的“相对初始改进”按最终 HPWL 减去该 seed 的最佳初始 shelf HPWL 记录；P0 中位数为 `0.0` 不表示搜索无效，而表示经典 SA 的合法 shelf 已是该批次保存规则下的最佳值。

配对差值（候选减基线，HPWL 越小越好）如下：

| 配对 | 候选更好 seed 数 | 中位差值 | 中位相对差值 |
|---|---:|---:|---:|
| `P1-P0` | 10/10 | -36271.25 | -12.48816% |
| `P1-A2-BASE` | 6/10 | -275.25 | -0.10665% |
| `P2-ON-P2-OFF` | 8/10 | -5427.25 | -2.14274% |
| `P2-OFF-P1` | 10/10 完全相同 | 0.0 | 0.0% |

这些是 n100 开发观察，不是统计显著性或总体优越性证明。P1 与 A2-BASE 只有 6/10 seed 更好，P2-ON 有 8/10 seed 更好。

## 5. 随机初始化压力实验

| 配置 | 合法 | audit 一致 | 完整预算 | 状态 | 首次合法评价 |
|---|---:|---:|---:|---|---|
| A2-BASE-RANDOM | 0/10 | 10/10 | 0/10 | `no_feasible` 10/10 | 无 |
| P1-RANDOM | 1/10 | 10/10 | 1/10 | success 1、`no_feasible` 9 | seed 1104：6439 |

随机压力组保留了 20 条失败/成功明细，但不进入生产候选排序。它说明随机初始 B*-Tree 在本预算下可能无法稳定进入合法域，也说明 shelf 初始化是本轮协议的一部分，而不是可被忽略的实现细节。

## 6. 产物与复现入口

主组 50 条明细、汇总、配对差值和比较快照：

- `outputs/q2/tables/v2_n100_repaired_fix2_run_details.csv`
- `outputs/q2/tables/v2_n100_repaired_fix2_summary.csv`
- `outputs/q2/tables/v2_n100_repaired_fix2_paired_differences.csv`
- `outputs/q2/tables/v2_n100_repaired_fix2_comparison_snapshot.json`

压力组：

- `outputs/q2/tables/v2_n100_repaired_fix2_a2_stress_run_details.csv`
- `outputs/q2/tables/v2_n100_repaired_fix2_a2_stress_summary.csv`
- `outputs/q2/tables/v2_n100_repaired_fix2_a2_stress_paired_differences.csv`

五个主组和两组压力实验的配置快照、布局和事件日志分别位于 `outputs/q2/_runtime/v2_n100_repaired_fix2/`；此前批次和第一次工具超时留下的部分批次均保留，没有覆盖或删除。

典型主组命令（只替换 `--candidate/--config-id/--runtime-root/--run-id`）：

```text
python -B -m src.Q2 batch --instance n100 --candidates Q2-BT --config-id P1 --adaptive-constraints on --seeds 1101-1110 --max-evaluations 30000 --time-limit 180 --restarts 4 --raw data/raw/附件 --runtime-root outputs/q2/_runtime/v2_n100_repaired_fix2/P1 --table-root outputs/q2/tables --run-id v2_n100_repaired_fix2_p1 --require-full-evaluations
```

汇总入口：

```text
python -B -m src.Q2.summarize --p0 outputs/q2/tables/v2_n100_repaired_fix2_p0_ground_run_details.csv --a2-base outputs/q2/tables/v2_n100_repaired_fix2_a2_base_run_details.csv --p1 outputs/q2/tables/v2_n100_repaired_fix2_p1_run_details.csv --p2-off outputs/q2/tables/v2_n100_repaired_fix2_p2_off_run_details.csv --p2-on outputs/q2/tables/v2_n100_repaired_fix2_p2_on_run_details.csv --a2-base-random outputs/q2/tables/v2_n100_repaired_fix2_a2_base_random_run_details.csv --p1-random outputs/q2/tables/v2_n100_repaired_fix2_p1_random_run_details.csv --output-root outputs/q2/tables --run-id v2_n100_repaired_fix2 --seeds 1101-1110
```

## 7. 已完成验收与后续计划

- P0-GROUND：10/10 合法、10/10 审计一致、10/10 完整 30000 评价，且每个 seed 的最终 HPWL 不高于最佳初始 shelf；已满足“可信独立参考基线”的技术门槛。
- P1/P2：P1 与 P2-OFF 逐 seed 完全一致；P2-ON/OFF 的 shelf 行成员、旋转、restart 子种子和搜索随机流逐 seed 一致，只允许行内顺序不同。
- 70 条布局已用共享评价器和独立审计逐条复核；全量 `unittest` 通过 19/19。

### 人工复核结论与后续任务

1. 2026-08-09，指定人工复核人接受现有 70 条运行证据及代码哈希 `5182e532…` 的历史快照边界，批准本阶段为 `VERIFIED`。
2. P0 仍不得写成 ground truth、全局最优或最终模型；P1/P2 的 n100 观察不得写成 n200/n300 结论。
3. n200 前重新冻结主预算、顺序运行机器/线程和 RNG；n200/n300 不属于本批次，当前没有运行证据。

本次 `VERIFIED` 只覆盖上述历史快照与 V2 n100 证据。任何关键公式、参数、代码、数据或结论变化都必须退回 `REVIEWING` 并重跑受影响的验证。

## 8. P0 临时确定性复跑

在临时目录 `tmp/v2_n100_p0_determinism_fix2_20260808/` 复跑的 P0 seed `1101` 和 `1102` 均完成 30000 次评价、状态为 `success`、正式评价与独立审计一致，并使用最终代码哈希 `5182e532…`。与正式 P0 批次逐 seed 比较时，布局、HPWL、评价次数、proposal/accepted、四个 restart 初始记录、`init_seed/search_seed` 和初始改进字段一致；运行时间和临时路径不参与确定性判定。
