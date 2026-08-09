# Q1 V3：n300 留出验证报告

- 问题：Q1
- 阶段：`VERIFIED`
- 基本执行：`luna_worker`
- 阶段验收：Codex 主代理
- 人工复核人：用户（2026-08-09 明确批准）
- 更新日期：2026-08-09
- 运行范围：冻结候选 `Q1-BT`、主随机基线 `Q1-SP` 与确定性参考基线 `Q1-G` 的 n300 留出验证
- 直接结论：90/90 条注册结果完整；冻结候选 `Q1-BT` 在 30 个同 seed 配对中均优于两组基线
- 边界：本报告不在 n300 重新选型或调参，不声称全局最优或文献领先；`VERIFIED` 不等于 `FINAL`

## 1. 冻结协议

| 项目 | 冻结值 |
|---|---|
| 实例 | `n300` hard blocks |
| 留出种子 | `3301--3330`，每配置 30 个且不补种子 |
| 配置 | `Q1-G`、`Q1-SP`、`Q1-BT` |
| 冻结候选 | `Q1-BT` |
| 基线 | `Q1-SP` 为主随机基线；`Q1-G` 为确定性参考基线 |
| 消融 | 无；n300 不继续机制选型 |
| 单次预算 | 最多 100000 evaluations、600 s、4 restarts |
| 并发 | 外层 workers=8；每 run 单进程、threads=1 |
| RNG | `random.Random`，CPython MT19937 |
| 选择规则 | `selection_locked=true`、`reselection_allowed=false` |

最终联合注册清单为 [`outputs/v3_n300_frozen_manifest_v3.json`](../../v3_n300_frozen_manifest_v3.json)，协议名为 `v3_n300_holdout_v3`。该清单的 SHA-256 为 `211ee99686cf92268e1ca68cf0130e693505408aac2a8d96ecbb0950f4a02e73`；Q1 code manifest hash 为 `297975034e94b5cdfa7afb1cf1b28a968efba20a792ce0f3f6ebdff3c566851b`，data manifest hash 为 `03a4b40545d0c13c136160fa998568f8ab823b8e88f29f65d848699b1fa5666d`。

## 2. 实际命令与协议演变

正式运行命令：

```text
D:\Anaconda\envs\CA-py310\python.exe -B -m src.n300 run --problem q1 --execute --output tmp/n300_q1_run_results_v2.json
```

汇总命令：

```text
D:\Anaconda\envs\CA-py310\python.exe -B -m src.n300 summary --problem q1 --input outputs/q1/_runtime/v3_n300_holdout --output outputs/q1/tables/v3_n300_holdout_summary.json
```

运行初期的联合清单曾额外注册 Q1 消融配置。用户明确 n300 只保留候选和基线后，运行在 `Q1-BT-D` 启动前被收紧为 `Q1-G/Q1-SP/Q1-BT`；8 个无完整 marker 的 `Q1-BT` 中断目录被可恢复地移入 `tmp/`，随后按相同配置、种子、预算和算法 hash 续跑。最终没有创建 `Q1-BT-D` 运行目录或结果。

Q1 的 90 条正式 marker 在当前 v3 规范下重新通过注册指纹与完整性校验。旧 `outputs/v3_n300_frozen_manifest.json` 与 `outputs/v3_n300_frozen_manifest_v2.json` 仅保留为 superseded 追溯，不是当前注册口径。

## 3. 完整性与状态

| 配置 | 注册/发现 | 缺失 | legal | audit 一致 | success | timeout | no_feasible | crash |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Q1-G | 30/30 | 0 | 30/30 | 30/30 | 30 | 0 | 0 | 0 |
| Q1-SP | 30/30 | 0 | 30/30 | 30/30 | 0 | 30 | 0 | 0 |
| Q1-BT | 30/30 | 0 | 30/30 | 30/30 | 30 | 0 | 0 | 0 |
| 合计 | 90/90 | 0 | 90/90 | 90/90 | 60 | 30 | 0 | 0 |

不存在重复或未注册完整 marker。`Q1-SP` 的 30 条 `timeout` 均保留合法布局；timeout 表示达到 600 s 墙钟上限，不等于求解失败、收敛或最优性证明。

## 4. 面积结果

面积越低越好。

| 配置 | min area | median area | IQR | p90 | max area | median aspect ratio | median evaluations | median runtime/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Q1-G | 439680 | 439680 | 0 | 439680 | 439680 | 190.8333 | 1 | 152.4756 |
| Q1-SP | 352656 | 362602.5 | 9649.5 | 372034.9 | 376002 | 1.0761 | 13640.5 | 600.0194 |
| Q1-BT | 299466 | **310704.5** | **6212.25** | **315339.6** | **317955** | 5.2460 | 100000 | 420.8615 |

相对 median area：

- `Q1-BT` 比主随机基线 `Q1-SP` 低 `14.3126%`；
- `Q1-BT` 比确定性参考基线 `Q1-G` 低 `29.3339%`。

长宽比不是本轮第一目标；`Q1-SP` 的长宽比更接近 1，而 `Q1-BT` 以更小面积换取了更长的包围盒。论文若同时强调紧凑度和形状，应分别报告两项指标，不能用面积结论替代长宽比结论。

## 5. 同 seed 配对

定义 `candidate-baseline = area(Q1-BT) - area(baseline)`，负值表示 `Q1-BT` 更好。

| 比较 | 配对数 | Q1-BT 胜/平/负 | 差值 min | 差值 median | 差值 IQR | 差值 max | 差值 mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| Q1-BT vs Q1-SP | 30 | 30/0/0 | -66968 | -51421 | 12201.5 | -35987 | -52544.8667 |
| Q1-BT vs Q1-G | 30 | 30/0/0 | -140214 | -128975.5 | 6864.25 | -121725 | -129403.7333 |

该配对结果支持“冻结候选在本次 n300 留出种子上稳定优于内部基线”。它不支持跨机器、跨预算、跨实例或相对公开文献达到先进水平的外推。

## 6. 协议偏差与限制

1. 90 条记录均未记录 `first_feasible_evaluation`；汇总明确标记为 `not_recorded_protocol_deviation`，没有补写或推断该字段。
2. `Q1-SP` 未完成 100000 evaluations，因此它与 `Q1-BT` 的结果首先是等墙钟 incumbent 比较，不是等完成评价次数的收敛比较。
3. n300 只做冻结留出验证；没有运行 Q1 消融，也没有依据 n300 重新选择候选。
4. 本结果仅覆盖当前 hard-block 数据、旋转规则、评价器、机器和预算。
5. 2026-08-09，人工复核人（用户）接受留出锁定、配对比较和协议偏差边界，批准阶段为 `VERIFIED`；仍不得迁入 `outputs/q1/final/` 或写成全局最优、文献领先结论。

## 7. 证据与验证

- 正式汇总：[`v3_n300_holdout_summary.json`](../tables/v3_n300_holdout_summary.json)，SHA-256 `b547002cb232389253ac272df165dd39b3a58c58d6e18bb68110369a5d8a6bb1`
- 运行根：`outputs/q1/_runtime/v3_n300_holdout`，90 个 `events.jsonl`、90 个 layout、90 个冻结 sidecar、90 个 orchestrator sidecar
- 运行器：[`src/n300.py`](../../../src/n300.py)
- 回归测试：[`tests/test_n300.py`](../../../tests/test_n300.py)
- 当前验证命令：`D:\Anaconda\envs\CA-py310\python.exe -B -m unittest tests.test_n300 tests.test_v3 -q`
- 当前验证结果：35 tests，`OK`
- 论文图：[代表布局](../figures/v3_final_layouts.png)与[模型比较](../figures/v3_model_comparison.png)
