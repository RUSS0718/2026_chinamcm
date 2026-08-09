# Q2 V3：n300 留出验证报告

- 问题：Q2
- 阶段：`REVIEWING`
- 基本执行：`luna_worker`
- 阶段验收：Codex 主代理
- 人工复核人：待团队指定
- 更新日期：2026-08-09
- 运行范围：冻结候选 `P1` 与主基线 `P0` 的 n300 留出验证
- 直接结论：60/60 条最终注册结果完整；`P1` 在 30 个同 seed 配对中均取得更低 HPWL
- 边界：`P2` 只保留 n200 消融证据，没有进入 n300 性能汇总；本报告不重新选型、不声称收敛、全局最优、文献领先、`VERIFIED` 或 `FINAL`

## 1. 配置与冻结协议

| 配置 | 实际候选 | SA/约束 | 超图初始化 | 本轮角色 |
|---|---|---|---:|---|
| P0 | `Q2-SP` | classic SA，adaptive OFF | OFF | 独立主基线，不是 ground truth |
| P1 | `Q2-BT` | Fast-SA，adaptive ON | OFF | n200 冻结候选 |

| 项目 | 冻结值 |
|---|---|
| 实例 | `n300.blocks/.nets/.pl` |
| 留出种子 | `3301--3330`，每配置 30 个且不补种子 |
| 单次预算 | 最多 30000 evaluations、600 s、4 restarts |
| 初始化 | `shelf` |
| 候选调度 | P0 与 P1 串行分组；组内 seed 并发 |
| 并发 | 外层 workers=8；每 run 单进程、threads=1 |
| RNG | `random.Random`，CPython MT19937 |
| 选择规则 | `selection_locked=true`、`preselected=P1`、`reselection_allowed=false` |
| n300 消融 | 无 |

最终联合注册清单为 [`outputs/v3_n300_frozen_manifest_v3.json`](../../v3_n300_frozen_manifest_v3.json)，协议名为 `v3_n300_holdout_v3`。该清单的 SHA-256 为 `211ee99686cf92268e1ca68cf0130e693505408aac2a8d96ecbb0950f4a02e73`；Q2 code manifest hash 为 `16d2ad3e785d6b0ec3048cd58875bd4ce5ee9c72964adfa84e5199bc5acb576c`，data manifest hash 为 `d7ad31e667df750871ff48b49954f63ac10381a333b010a703350543e285d180`。

## 2. 实际命令与范围收紧

正式运行入口：

```text
D:\Anaconda\envs\CA-py310\python.exe -B -m src.n300 run --problem q2 --execute --output tmp/n300_q2_run_results_v2.json
```

汇总命令：

```text
D:\Anaconda\envs\CA-py310\python.exe -B -m src.n300 summary --problem q2 --input outputs/q2/_runtime/v3_n300_holdout --output outputs/q2/tables/v3_n300_holdout_summary.json
```

运行开始时使用的 v2 联合清单仍包含 `P2`。用户随后明确 n300 只运行冻结候选和主基线。由于候选组按 `P0 -> P1 -> P2` 串行调度，P0 与 P1 各 30 条已经完整结束；在 P2 首批只写入 8 个 `v3_freeze.json`、尚无任何 `events.jsonl`、layout 或 orchestrator sidecar 时，外层 runner 被明确终止。外层命令因此没有生成 `tmp/n300_q2_run_results_v2.json`，不能写成正常 exit 0。

8 个 P2 占位目录被可恢复地移入 `tmp/n300_q2_aborted_p2_batch_20260809/`，不纳入正式结果。当前 v3 清单只注册 P0/P1 共 60 条；现有 60 条 marker 在当前代码下重新通过注册指纹、合法性、formal audit 和完整性校验。旧 v1/v2 清单仅为 superseded 追溯，不是当前选型口径。

## 3. 完整性与状态

| 配置 | 注册/发现 | 缺失 | legal | audit 一致 | success | timeout | no_feasible | crash |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 | 30/30 | 0 | 30/30 | 30/30 | 0 | 30 | 0 | 0 |
| P1 | 30/30 | 0 | 30/30 | 30/30 | 30 | 0 | 0 | 0 |
| 合计 | 60/60 | 0 | 60/60 | 60/60 | 30 | 30 | 0 | 0 |

不存在重复、未注册或 P2 完整 marker。P0 的 30 条 timeout 均保留合法 incumbent；timeout 表示达到 600 s 墙钟上限，不等于失败、收敛或最优性证明。

## 4. HPWL 与效率结果

HPWL 越低越好。

| 配置 | min HPWL | median HPWL | IQR | p90 | max HPWL | median first feasible eval | median evaluations | median runtime/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 | 818990 | 831802 | 7482.875 | 840255.9 | 849827.5 | 1 | 12581 | 600.0223 |
| P1 | **758199** | **776636.75** | 11385.5 | **788598.75** | **795623** | 1 | 30000 | 300.2509 |

`P1` 的 median HPWL 比 `P0` 低 `6.6320%`。P1 的 IQR 大于 P0，但其最差值仍低于 P0 的最好值；这支持在本轮留出种子上 P1 的整体 HPWL 水平更低。

P1 完成全部 30000 evaluations；P0 在 600 s 内的 evaluations 范围为 12086--14825。P0 与 P1 的主要比较是相同墙钟上限下的最终 incumbent，同时也揭示 P0 单次评价路径明显更慢。

## 5. Checkpoint 与同 seed 配对

| 配置 | 25% checkpoint median HPWL | 50% | 75% | 100% | checkpoint 状态 |
|---|---:|---:|---:|---:|---|
| P0 | 835757 | 未到达 | 未到达 | 未到达 | missing |
| P1 | 793113.5 | 781363.5 | 777535.5 | 776636.75 | complete |

定义 `candidate-baseline = HPWL(P1) - HPWL(P0)`，负值表示 P1 更好。

| 比较 | 配对数 | P1 胜/平/负 | 差值 min | 差值 median | 差值 IQR | 差值 max | 差值 mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| P1 vs P0 | 30 | 30/0/0 | -75076 | -53217.75 | 13230.25 | -38824 | -54166.25 |

该配对结果支持“冻结候选在本次 n300 留出种子上稳定优于内部基线”。它不支持跨预算、跨模块形态或相对公开文献达到先进水平的外推。

## 6. 限制与后续门槛

1. P0 全部 timeout 且未完成 30000 evaluations；不能把结果写成等完成评价次数下的收敛比较。
2. P2 没有 n300 性能结果；其网络超图初始化价值只引用 n200 消融，不得根据 8 个占位 sidecar 推断任何指标。
3. v3 是在 P2 产生完整结果前完成的范围收紧；报告保留该时间顺序，不将其改写为原始运行一开始就只有两组。
4. n300 只验证冻结选择，不允许依据本批结果继续调参或重新选型。
5. 当前结果只覆盖 hard blocks、中心引脚、原始 terminal 坐标、正方形轮廓和当前机器/预算；不能直接与采用 soft modules、边界迁移 terminal 或其他轮廓定义的文献数字排名。
6. 当前阶段保持 `REVIEWING`，人工复核前不得迁入 `outputs/q2/final/`。

## 7. 证据与验证

- 正式汇总：[`v3_n300_holdout_summary.json`](../tables/v3_n300_holdout_summary.json)，SHA-256 `93ad632a06d6d28e3636efbf799477a465f4185bb9833c8611726dab15dbd3bc`
- 运行根：`outputs/q2/_runtime/v3_n300_holdout`，60 个 `events.jsonl`、60 个 layout、60 个冻结 sidecar、60 个 orchestrator sidecar
- 运行器：[`src/n300.py`](../../../src/n300.py)
- 回归测试：[`tests/test_n300.py`](../../../tests/test_n300.py)
- 当前验证命令：`D:\Anaconda\envs\CA-py310\python.exe -B -m unittest tests.test_n300 tests.test_v3 -q`
- 当前验证结果：35 tests，`OK`
