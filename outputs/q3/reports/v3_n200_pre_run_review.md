# Q3 V3 n200 正式运行前评估

- 阶段：`REVIEWING`
- 更新时间：2026-08-09
- 评估对象：Q3 V3 `n200`，`Q3-BIN → Q3-LIN → Q3-CONT-R`
- 当前结论：配置、入口、冻结清单和最小验证已具备正式运行条件；本文件不包含 n200 模型结果，也不替代人工验收。
- 明确边界：本轮尚未启动 Q3 n200 正式运行；不迁入 `outputs/q3/final/`，不创建 commit，不 push。

## 1. 需求与决策

本轮只处理 Q3 V3 n200 的正式运行准备。根据已确认的 Q2 V3 运行设置，将 Q3 内层 seed 并行度固定为 `workers=4`。这是一项已授权的运行配置决定，不把 Q2 的经验写成 Q3 已经完成的 4-vs-5 基准证明；当前没有 Q3 的 workers=4 与 workers=5 对照实验。

Q3 的外层路线仍按注册顺序串行执行，内层每次最多 4 个独立 seed 进程；每个进程保持单线程。候选、预算、种子、数据和输出根目录均由当前 V3 冻结清单生成，正式运行中不得按前一路线的结果改写后一路线配置。

## 2. 已检查的仓库和 Git 状态

已阅读 `README.md`、`建模协作/B题双人分工协作表.md`、`建模协作/协作验收完成表.md`、`outputs/v3_protocol_draft.md` 以及 Q3 V1/V2 报告，并核对当前 Git 提交和远端分支记录。

当前 checkout：

| 项目 | 已核对值 |
|---|---|
| 分支 | `v3-temp`，跟踪 `origin/v3-temp` |
| HEAD | `b3ac17ddf54db8e9f2931d915c3ae7349930a967`（`q2(v3): 提交n200 P2正式运行证据`） |
| 远端核对 | 此前已用 `git ls-remote` 核对 `V3` 与 `v3-temp` 指向同一 `b3ac17d...`；本轮不 push |
| Q2 V3 | P0/P1/P2 共 60 条 n200 记录，仍为 `REVIEWING` |
| Q3 V3 | n200 正式运行尚未开始 |
| Q3 运行根 | `outputs/q3/_runtime/v3_n200/` 当前不存在，未混入旧运行产物 |

工作区的未提交变更仅限本轮 Q3 workers/运行接口、冻结清单、协议和对应测试；未修改 `data/raw/`，未清理或覆盖无关文件。

## 3. workers=4 的实际修改位置

已在以下两个真实入口修改，并已同步测试：

1. `src/v3.py:44` 增加 `Q3_WORKERS = 4`；`src/v3.py:163` 的 Q3 配置从字面量 `5` 改为引用 `Q3_WORKERS`；`src/v3.py:208` 的 Q3 冻结规格同步为同一值。这里是正式 V3 编排器生成 Q3 命令和 manifest 的权威配置。
2. `tests/test_v3.py` 将 Q3 冻结规格断言更新为 4，并保留“外层串行、内层并行”的契约测试。

`src/Q3` 的搜索算法没有改变候选逻辑、随机种子、评价预算或停止语义；Q3 的并行度只影响 seed 任务的同时执行数量。

## 4. 冻结运行协议

| 项目 | 冻结值 |
|---|---|
| 实例 | `n200` |
| 候选顺序 | `Q3-BIN → Q3-LIN → Q3-CONT-R`，外层串行 |
| 内层候选 | 固定 `Q2-HG`；`adaptive_constraints=on`、`hypergraph_init=on` |
| dead-space 比例 | 区间 `[0, 0.15]`，绝对精度 `0.005` |
| 选择规则 | `decision_rule=robust`，`robust_min_success_rate=0.80` |
| threshold cold seeds | `2201–2220`，每个实际阈值 20 个，不补种子 |
| selected-ratio final seeds | `2301–2320`，独立于 threshold 阶段 |
| 单次预算 | `30000 evaluations / 60 s / 4 restarts` |
| 并行/线程 | Q3 内层 `workers=4`；外层 `processes=1`；每进程 `threads=1` |
| RNG | `random.Random`（CPython MT19937） |
| Python | `D:\miniconda3\envs\causal_paper\python.exe`，CPython 3.10.20 |
| 平台 | Windows 10，12 logical CPUs；MKL/OMP/OpenBLAS 均为 1 |
| 正式输出根 | `outputs/q3/_runtime/v3_n200/` |

三条路线均已通过 dry-run 检查，生成 3 条候选命令，且每条命令显式带有 `--workers 4`。dry-run 不执行求解、不产生正式结果。

## 5. 当前版本、配置和数据指纹

以下值由当前 checkout 的 `src.v3` 和 `outputs/v3_frozen_manifest.json` 实际重算：

| 项目 | SHA-256 或值 |
|---|---|
| Q3 core code hash | `af3206f66f6a554c0861c9e8a75f74660a48ba97a6076fcd58e1dbbbb2597a99` |
| Q3 V3 code manifest hash | `839947e21e0b5cf25465d1d1410b9afc9afdf276c9af64d49f69696d015d75d7` |
| Q3-BIN config hash | `0d76fc973af444d1849e9a3413c75cb51d7a8d9cda91a8582b168cbeb6e47cba` |
| Q3-LIN config hash | `20a8329f4f661c574fc4a4f9c0192fa5ae7a73d969741ca6feb782be34fdca99` |
| Q3-CONT-R config hash | `ae5becde3ed321d8ca6e1f4726934399a8eb33116da5b19de7aca82285455e06` |
| n200 三文件 manifest hash | `475e63eefda4a1592adaddb9596e92595f6ef6d5404ae0fd1e826d367bd056a7` |

n200 原始输入逐文件指纹如下；这些文件保持只读：

| 文件 | bytes | SHA-256 |
|---|---:|---|
| `data/raw/附件/n200.blocks` | 16719 | `bed652bf55c2034b04a1c1bbe97ad617e027c11736bf069727a63baf575720ef` |
| `data/raw/附件/n200.nets` | 38414 | `8867f3f167845d88623a5cadba68f7a19fe343278779538e7804c5ac0c5940a2` |
| `data/raw/附件/n200.pl` | 6512 | `0400507fcb07124e01f6cdb86c5e71cdce1bbbb871030651f5583a2f66ec3589` |

共享 `src/v3.py` 纳入 Q1/Q2/Q3/Q4 的冻结逐文件清单，因此本轮重新生成了完整 `outputs/v3_frozen_manifest.json`；这不是重跑 Q1/Q2，也没有改变它们已经落盘的历史运行结果。各问题当前清单 hash 以该 JSON 为准。

## 6. 验证结果

已实际执行：

```text
D:\miniconda3\envs\causal_paper\python.exe -B -m unittest discover -s tests -p 'test*.py' -q
```

结果：`Ran 87 tests in 30.467s`，`OK`。

同时实际执行：

```text
D:\miniconda3\envs\causal_paper\python.exe -B -m src.v3 dry-run --problem q3
```

结果：3 条计划命令，候选顺序、`workers=4`、cold/final seeds、预算、配置 hash、数据 hash 与冻结清单一致；正式运行根仍为空。测试和 dry-run 只证明入口/契约/冻结边界可用，不构成模型效果证据。

## 7. 正式运行命令和结果门槛

得到下一步明确授权后，唯一正式入口为：

```text
D:\miniconda3\envs\causal_paper\python.exe -B -m src.v3 run --problem q3 --execute
```

完成三条路线后再执行机械汇总：

```text
D:\miniconda3\envs\causal_paper\python.exe -B -m src.v3 summary --problem q3 --input outputs/q3/_runtime/v3_n200 --output outputs/q3/tables/v3_n200_summary.json
```

结果检查必须先看完整注册分母、缺失 seed、`formal_audit_match`、threshold cold 与 final 的分离，再看 `d_best`、`d_robust`、HPWL、IQR/p90 和同 seed 差值。硬门槛为合法率至少 0.90、robust 判定使用预注册的 0.80 成功率；任何 `timeout/no_feasible` 只能作为有限预算观测，不能写成不可行证明或最优性证明。当前没有任何 Q3 数值结论。

## 8. 剩余风险与待确认事项

- `workers=4` 是当前机器和既定 Q2 设置下的授权配置，不是 Q3 的性能优越性结论；若之后需要证明 4 优于 5，应另建同输入、同 seed、同预算的对照实验，不能混入本次正式选型。
- Q3 的阈值实际尝试次数随路线而定，正式总耗时不能从 n100 或 Q2 单次记录直接外推；运行中不得因为某路线暂时领先而改变后续路线的注册配置。
- 正式运行失败或中断时保留已有 marker/失败状态，不自动补种子、不覆盖旧尝试；如需重跑，使用新的 `--attempt` 后缀并重新核对 manifest。
- 正式结果完成后仍需建模负责人和交叉复核人检查；本文件和协议保持 `REVIEWING`，不自动升级到 `VERIFIED` 或 `FINAL`。

