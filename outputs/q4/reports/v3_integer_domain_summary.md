# Q4 V3 整数声明域扩展汇总（VERIFIED）

## 结论边界

本报告只汇总 Q4 的几何、声明整数域与预算敏感性，不是 Q1--Q3 的 `n200` 选型，也不声称连续域结论、全域不可行或连续域全局最优。连续域开关为 `false`。2026-08-09，人工复核人（用户）接受声明整数域、exact/SA 一致性和 timeout 保留边界，批准阶段为 `VERIFIED`，但不是 `FINAL`。

## 执行证据

- 正式命令：`D:\Anaconda\envs\CA-py310\python.exe -B -m src.v3 run --problem q4 --execute`
- 输出根：`outputs/q4/_runtime/v3_integer_domain`
- 注册/发现：726/726；其中 exact 6 条、SA 720 条；缺失 0、重复 0、partial 0。
- 机器约束：外层 workers=8；每 run 单进程单线程；`OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1`、`OPENBLAS_NUM_THREADS=1`。
- 状态：exact `optimal=6`；SA `success=600`、`timeout=120`；`no_feasible=0`、`crash=0`。726 条的 formal、声明域审计均通过并计入合法率。
- 不可变执行清单：[v3_integer_domain_execution_manifest.json](../tables/v3_integer_domain_execution_manifest.json)。其中 execution runner 为 `8a156193b83a7d13fa40d0b708809626162dd9ce0ba39a42c6572ffae7a9c8d8`，记录正式运行时的 base commit `ad1495f8f08ec863850d4291484e355bbd403a13`。

## Exact

| 几何 | 声明域 | 状态 | 完整搜索 | lower bound | upper bound |
|---|---|---|---:|---:|---:|
| G- | 9x9 | optimal | 是 | 24 | 24 |
| G- | 12x12 | optimal | 是 | 24 | 24 |
| G0 | 9x9 | optimal | 是 | 24 | 24 |
| G0 | 12x12 | optimal | 是 | 24 | 24 |
| G+ | 9x9 | optimal | 是 | 28 | 28 |
| G+ | 12x12 | optimal | 是 | 28 | 28 |

`formal.area` 是布局紧包围盒目标面积；声明域合法性由 `domain_formal/domain_audit/domain_audit_match` 单列核验。`upper_area=36` 的完整性只限于声明整数域。

## SA 预算敏感性

每个几何×声明域×预算单元有 20 个 cold seeds（2201--2220），共 36 个单元。完整逐单元数据见 [v3_integer_domain_summary.csv](../tables/v3_integer_domain_summary.csv)，中文摘要见 [v3_integer_domain_summary_cn.json](../tables/v3_integer_domain_summary_cn.json)。每单元合法率均为 1.0，分母包含该单元全部 20 个注册运行。

面积中位数与同格 exact 参考的范围如下：

| 几何 | 域 | 面积中位数范围 | 面积最小--最大 | incumbent gap 中位数最大值 |
|---|---|---:|---:|---:|
| G- | 9x9 | 24--25 | 24--30 | 0.041667 |
| G- | 12x12 | 24--28 | 24--30 | 0.166667 |
| G0 | 9x9 | 24--28 | 24--30 | 0.166667 |
| G0 | 12x12 | 25--28 | 24--30 | 0.166667 |
| G+ | 9x9 | 28--30 | 28--30 | 0.071429 |
| G+ | 12x12 | 28--30 | 28--32 | 0.071429 |

timeout 运行保留在分母和状态计数中；`incumbent gap` 只相对同几何、同声明域的 exact 参考，timeout exact 仅作参考，不暗示全局最优。

## 专项验收结论

“两条路线一致”在本报告中严格定义为：同一几何、同一声明整数域下，SA 的注册运行最优面积等于 complete exact 的上下界；它不表示每个 seed 或每个预算单元都命中 exact。

| 几何 | 声明域 | exact 界 | SA 最好面积 | 最优值层面是否一致 |
|---|---|---:|---:|---|
| G- | 9x9 | 24/24 | 24 | 是 |
| G- | 12x12 | 24/24 | 24 | 是 |
| G0 | 9x9 | 24/24 | 24 | 是 |
| G0 | 12x12 | 24/24 | 24 | 是 |
| G+ | 9x9 | 28/28 | 28 | 是 |
| G+ | 12x12 | 28/28 | 28 | 是 |

核心题面几何 `G0` 的启发式与精确代表布局见 [V2 代表布局图](../figures/v2_representative_layouts.png)：exact 为 `4×6`、面积 24，SA seed 1108 为 `6×4`、面积 24。SA 命中相同面积只构成独立一致性验证；最优性证明仍只来自 exact 的 `complete=true` 和相等上下界。G-/G+ 仅用于已声明几何敏感性，不替代题面核心几何结论。

## 汇总层修复与哈希分层

正式 marker 没有 `config_id` 字段。汇总层在 `_validate_completed(plan)` 完整通过后从注册 plan fingerprint 注入 `config_id`，不信任 marker 提供值，未修改 runtime/marker。该修复通过回归测试：缺少 marker `config_id` 的真实格式可以汇总，伪造 sidecar 会 fail-closed。

- 执行代码：`51df5eac273ea439410170bda7198b38ed3c360bad647679442303aea02f7db3`
- 执行 runner：`8a156193b83a7d13fa40d0b708809626162dd9ce0ba39a42c6572ffae7a9c8d8`
- 汇总生成 runner：`17965f265464e1acd72667e2edd0e4d4c44c7c7b51e4ad5f295cc1aeb257e277`
- 本次整改前分析 runner：`cdba59be5cbf10dabceb37eb98f4dc686ed5f2362b2c906e96f2eed6bea901d2`
- 配置：`6153919d92e2740f8e07ffd59c13a958680dc0f32d0fc3995195d5b1db034ed4`
- 数据（canonical 空 external-data manifest）：`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- 整改后验证：Q4 注册检查通过，正式汇总可逐字节重建；全量回归 109 tests，`OK`。

## 限制与后续

G-/G0/G+、9x9/12x12 以及 `upper_area=36` 均为已声明的整数域。连续平移、题面外几何解释、SA 全局最优和 `no_feasible` 的全域推断均未执行或不成立。`VERIFIED` 仅覆盖上述声明域证据，不得扩大为 `FINAL`，也不得迁入 `outputs/q4/final/`。

论文图：[exact/SA 代表布局](../figures/v3_route_layouts.png)与[预算一致性](../figures/v3_exact_sa_consistency.png)；对应源数据为 `v3_figure_layout_sources.csv` 与 `v3_figure_exact_sa_consistency.csv`。
