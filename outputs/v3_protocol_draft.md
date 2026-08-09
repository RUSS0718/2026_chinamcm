# Q1--Q4 V3 协议与证据盘点（REVIEWING，协议已确认；实现变更待复核）

- **更新时间**：2026-08-09
- **阶段**：`REVIEWING`。2026-08-09 已人工确认完整 V3 协议并选择 Q2B；随后为同轨迹 checkpoint 与 Q3-LIN 全网格修订实现，形成 Q2B′/Q3 新 hash，须重新人工复核。本文仍不是 `VERIFIED`、`FINAL`，不替代主代理验收，也不授权当前启动正式 n200/n300 或 Q4 扩展运行。
- **范围**：Q1--Q3 的 `n200` 正式选型与消融预注册；Q4 的几何/预算扩展协议。`n300` 仅作为后续留出规模，不在本文运行。
- **本轮明确不做**：不改 `data/raw/`、不启动任何 `n200/n300` 正式运行、不迁入 `outputs/qN/final/`、不暂存/提交/push；仅新增 V3 编排/冻结检查模块与小夹具测试。

## 1. 只读盘点：当前代码、入口和证据

### 1.1 工作区与入口

写作前 `git status --short --branch` 为 `V2go...origin/V2go` 且工作区干净；当前仅新增本文、V3 编排、冻结清单与测试文件，未覆盖其他改动。当前 Git HEAD 为完整 commit `beaf1663463a7f3c1bb3bd7de6c2dacea96e53a7`（`q2-q4(v2): 记录人工复核通过并更新为VERIFIED`）。当前真实入口和兼容入口如下：

| 问题 | 当前真实入口 | 关键实现/配置事实 | V2 证据位置 |
|---|---|---|---|
| Q1 | `python -B -m src.Q1 batch`（单次为 `run`） | 候选 `Q1-G/Q1-SP/Q1-BT/Q1-BT-D`；面积为主目标、长宽比为次目标；`random.Random`，每次 4 restart；CLI 默认 `100000` 次评价、`60 s` | `src/Q1/__main__.py`；`outputs/q1/reports/v2_model_report.md`；`outputs/q1/tables/v2_n100_*` |
| Q2 | `python -B -m src.Q2 run|batch`；汇总 `python -B -m src.Q2.summarize` | `Q2-SP` 为 P0/classic-SA，`Q2-BT` 为 P1，`Q2-HG` 为 P2；固定轮廓 `d=0.15`，评价指标 HPWL；默认 `shelf` 初始化、4 restart | `src/Q2/__main__.py`、`src/Q2/common.py`；`outputs/q2/reports/v2_model_report.md`；`paper/q2/v2_handoff.md` |
| Q3 | `python -B -m src.Q3`（`src/q3.py` 为兼容包装） | 外层 `BIN/LIN/CONT-R`，内层固定候选由配置指定；阈值 cold 与选中轮廓 final 分开记录；`CONT-R` warm 仅为额外诊断 | `src/Q3/__main__.py`、`src/Q3/search.py`；`outputs/q3/reports/v2_n100_protocol.md`；`paper/q3/v2_handoff.md` |
| Q4 | `python -B -m src.Q4 exact|sa` | 四个异形模块；exact 是整数平移声明域，SA 是同一几何上的随机启发式；无 nets，`HPWL=0` 仅为共享审计 schema 字段 | `src/Q4/__main__.py`、`src/Q4/model.py`、`src/Q4/sa.py`；`outputs/q4/reports/v2_experiment_protocol.md`；`paper/q4/v2_handoff.md` |

当前 `data/raw/附件/` 包含 `n100/n200/n300` 的 `.blocks/.nets/.pl`；原始输入按 AGENTS.md 只读。`outputs/qN/_runtime/` 保存运行时 JSON/日志，`outputs/qN/tables/` 保存明细与汇总，`paper/qN/` 保存交接口径。

### 1.2 当前测试与 V2 证据边界

- 实际执行（只读验证，使用临时目录的测试夹具）：
  `D:\Anaconda\envs\CA-py310\python.exe -B -m unittest discover -s tests -p 'test*.py' -q` → **75/75，OK，20.973 s**（含 V3 冻结/执行/汇总夹具测试）。
- 该测试结论只证明代码契约、入口和小夹具可运行，不是模型效果、n200 选型或论文结论。
- Q1 V2 是 n100 开发批次；P2 消融的正式重跑留待 V3。Q2 V2 是 `n100` 的 50 条主组加 20 条随机初始化压力组；Q3 V2 是 `n100` 三路线比较；Q4 V2 是四模块 exact/SA，不是 n100。
- `outputs/v2_technical_acceptance.md` 与各 handoff 明确规定：V2 的 `VERIFIED` 不覆盖 V3、`n200/n300`、最终模型或 `FINAL`；`timeout`/`no_feasible` 不能改写为最优性/不可行证明；P0 不能改写为 ground truth。

### 1.3 版本、代码哈希和数据哈希

哈希均为程序按 LF 规范字节重算的结果；配置哈希按各 dataclass 的 `as_dict()` JSON（排序键）计算。下表是**已确认的预注册值**，代码/config/data 发生变化时必须整表更新并退回 `REVIEWING`。

| 组件 | 当前代码哈希 | V3 草案配置哈希/数据哈希 | 具体指向 |
|---|---|---|---|
| Q1 | `3191e8fa3cfd8aaa7948395b9026ff11bb50871a09425b05f1d85c6a8a6a5aaa` | Q1-G `4c11f9694e3449c03d25bc33769f3520608fc5ac417967aadb773404a6aa4412`；Q1-SP `23759db27eb4b66fada058141c85ff43d1d2f5334ec9f1437658df4f05602c9b`；Q1-BT `21710a897788c7b5b1cb80917bb03da9d86b258a6531c066e2462c93a28c7dab`；Q1-BT-D `7eadc36f5e9f024a1f3829860b7a5ed0926bff8720189300ffaea4b152e95570`；n200.blocks `bed652bf55c2034b04a1c1bbe97ad617e027c11736bf069727a63baf575720ef` | `src/Q1/__main__.py` 的 `_code_hash()` 覆盖 Q1 与 `_internal` 依赖；n200 输入为 `data/raw/附件/n200.blocks` |
| Q2 | `bd3ed1f896b81fa3317c2e7f5eaf9d6051976483693f75288b6b3636d1dd004b` | P0 `b4e9c046a28d9fa5da81c71344c61710653c902f72dda0acf23a769324dcee06`；P1 `62c4fc0857968603f5af8a4add05d7825ccbb79cfdfbde340b920a03183d787c`；P2 `53cc3b06b1f09685c2b904c24fe7e462cb8e2ab5f94334409e1229dad3f0fb17`；n200 三文件 manifest `475e63eefda4a1592adaddb9596e92595f6ef6d5404ae0fd1e826d367bd056a7` | 当前 `src/v3.py` 冻结清单含 Q2 与被调用 Q1/内部文件；`data/raw/附件/n200.{blocks,nets,pl}` |
| Q3 | `112df427de656e032b691fa1cc55cd14225ced5832e2c32b5fab0ec43f5779ba` | BIN `d199c899ccd7e0b32551015e1021c53be677c9a11ab13e22435017b1f7bb75ea`；LIN `0873b30da1bab74d09d0f63a8c4a64ab4535df540237cb0ad8728119247c0cce`；CONT-R `77b287aa2415021bd1c49881aa318cd0c8508da7c2755d64da51616815cf0864`；n200 三文件 manifest `475e63eefda4a1592adaddb9596e92595f6ef6d5404ae0fd1e826d367bd056a7` | 当前 `src/v3.py` 冻结清单含 Q3、Q2、Q1/内部被调用文件；配置含 cold `2201--2220` 与 final `2301--2320` |
| Q4 | `ebd6e86d9da5e1aa373ebb25cfbcf2a079863f2c450268174c30e9f5d9f38043` | 整数声明域扩展 config manifest `1ca180449987b53740782fb797d7046a3fad2c6b724e6078413917bc932594e4`；无外部数据文件；连续域仍明确为 false | `python -B -m src.v3 q4-check` 输出及 `outputs/v3_frozen_manifest.json` |

哈希后的完整逐文件清单不在本文重复；Q2 历史清单可直接查阅 `outputs/q2/tables/v2_n100_repaired_fix2_*_config_snapshot.json`，当前 Q2 清单由 `src/Q2/__main__.py::_code_manifest()` 生成。正式运行前必须把完整 `code_files`、`data_files`、配置 JSON、命令和环境写入每一条 snapshot，不能只记录短 hash。

当前 V3 不可变逐文件 manifest 聚合 hash 为：Q1 `512ff5b4274d2c276f2b091aff836fd7328406d6932b256fb9a8f1cedb587177`、Q2 `b9cdfe59217a68b4a921f734a86ad24327fb474c4f920c0235d811dc149596f8`、Q3 `be08db60b3ae6eb4cfff9f584c7338fdecf7aa4cdac156d253905d83b26ae772`；完整内容见 `outputs/v3_frozen_manifest.json`。runner `src/v3.py` 逐文件 SHA-256 为 `bb31f9740b1c3a6de710d5ef130eb3bd829ec33d594259298b5dbac066fb881a`。

## 2. 历史 Q2 code_hash `5182e532feca7ba4337692b112b06f181d6f79ee85596eacf83c9109b14fb709` 与当前 Git HEAD `beaf166` 下 Q2 code_hash `8486b3cd4164489a9bede5e71db248a389ba0f5ef3dc616ed4a75e4fb95aad5a`（V3 B′ 新 hash `bd3ed1f896b81fa3317c2e7f5eaf9d6051976483693f75288b6b3636d1dd004b` 待复核）

### 2.1 历史快照的具体指向

`5182e532feca7ba4337692b112b06f181d6f79ee85596eacf83c9109b14fb709` 不是 Git commit 名，而是 Q2 V2 fix2 运行时 manifest 的聚合 SHA-256。其完整指向是：

- Q2 `__init__.py/__main__.py/common.py/p0.py/p1_p2.py/summarize.py`；Q1 `p0.py/p1_p2.py`；共享 `parser.py/evaluator.py/audit.py/geometry.py`，共 12 个相对路径文件；逐文件 bytes/SHA-256 记录在各 `v2_n100_repaired_fix2_*_config_snapshot.json`。
- n100 三输入的 LF 规范 SHA-256：`n100.blocks=c66f917c48f3c7ee9624bec8e0dc053eb349d10121d3278d25b09b67a2e94e2b`、`n100.nets=cd86e1b49547f9c76144aa2acef6d643c8fd9222c3a4b8c91a40bb6f7ca42193`、`n100.pl=cb8b03aff82241643ca899aa9759d8aa42bcf085ead64d5011f52c83f836355f`；聚合 `data_hash=6be0918f672ac3bbdf8300aaeddedf4f348a2b1a1ea74f5975cc084ba0b2ec13`。
- 固定命令语义：`Q2-SP` P0 为 `classic`，P1 为 `Q2-BT`/adaptive on，P2 为 `Q2-HG`/adaptive on + hypergraph on；`seeds=1101--1110`，`max_evaluations=30000`，`time_limit=180`，`restarts=4`，`shelf` 初始化，单进程单线程顺序执行；`random.Random (MT19937)`。
- 70 条运行（5 主组 + 2 压力组）均保留明细、布局和事件日志；主组/压力组的入口与输出路径见 `outputs/q2/reports/v2_model_report.md` 第 6 节。

因此，`5182e532feca7ba4337692b112b06f181d6f79ee85596eacf83c9109b14fb709` 的**历史结果可按原始快照证据复核**；它不是“当前 checkout 的代码哈希”，也不是可直接由当前 HEAD 重现的承诺。

### 2.2 Q2 V3 版本决策表（人工选择后才解锁）

| 选项 | 版本身份 | 当前证据与可运行性 | 可用于 V3 运行？ |
|---|---|---|---|
| A | 历史运行快照：Q2 聚合 `code_hash=5182e532feca7ba4337692b112b06f181d6f79ee85596eacf83c9109b14fb709`；不是 Git HEAD commit | 当前仓库保存逐文件 manifest、命令、n100 输出和日志，但没有与该 manifest 一一对应的源码归档/可检出的 Git commit；因此只能复核历史产物，不能声称从当前 checkout 可重跑 | **否**，除非人工先提供并核验完整源码快照、依赖环境和来源 hash |
| B（推荐） | 当前 Git HEAD commit `beaf1663463a7f3c1bb3bd7de6c2dacea96e53a7`（`q2-q4(v2): 记录人工复核通过并更新为VERIFIED`）；其当时 Q2 聚合 `code_hash=8486b3cd4164489a9bede5e71db248a389ba0f5ef3dc616ed4a75e4fb95aad5a` | 当前源码、入口和测试均在 checkout；原 B 可按当时 CLI 运行，但 V3 checkpoint 修订后已形成 B′ 新 hash，不能把历史 5182 结果改标为当前结果 | **原 B 已确认；B′ 必须重新人工确认并通过主代理冻结验收** |

**2026-08-09 人工确认记录**：完整 Q1--Q4 V3 协议已确认，`q2_v3_baseline=B`；采用当前 Git HEAD commit `beaf1663463a7f3c1bb3bd7de6c2dacea96e53a7` 下的 Q2 `code_hash=8486b3cd4164489a9bede5e71db248a389ba0f5ef3dc616ed4a75e4fb95aad5a`。随后加入同一 trajectory 的 25/50/75/100% checkpoint，形成 Q2B′ `code_hash=bd3ed1f896b81fa3317c2e7f5eaf9d6051976483693f75288b6b3636d1dd004b`；该实现变更不由原 B 确认自动覆盖，须人工重新确认后才可运行。确认只解除版本选择歧义，不把本文标为 `VERIFIED/FINAL`；正式 n200 运行仍须通过主代理冻结验收，n300 不得调参或选型。所有新 Q2 结果必须绑定复核后的 B′ code hash，不得沿用历史 5182 快照标签。

### 2.3 当前 HEAD 的具体差异与复现限制

当前 `src/Q2/__main__.py::_code_hash()` 实测为 V3B′ `bd3ed1f896b81fa3317c2e7f5eaf9d6051976483693f75288b6b3636d1dd004b`；n200 三文件 data manifest 为 `475e63eefda4a1592adaddb9596e92595f6ef6d5404ae0fd1e826d367bd056a7`，历史 n100 snapshot 的 `6be0918f672ac3bbdf8300aaeddedf4f348a2b1a1ea74f5975cc084ba0b2ec13` 仅用于历史证据。与 `5182e532feca7ba4337692b112b06f181d6f79ee85596eacf83c9109b14fb709` 不一致的文件仍包括 `src/Q2/common.py` 和 `src/Q2/p1_p2.py`，并新增同轨迹 checkpoint 字段；Q2 CLI 现已序列化 `checkpoint_evaluations` 与 `checkpoint_best_hpwl`。当前测试覆盖默认路径、checkpoint 位置/单调 best-so-far、marker 验真和接口契约，但**没有 n100 或 n200 正式运行证据**。

可复现性结论应分层写：

1. 由历史 snapshot、命令、输入和逐文件 manifest，`5182e532feca7ba4337692b112b06f181d6f79ee85596eacf83c9109b14fb709` 绑定的 n100 结果是可追溯的历史证据。
2. 由未修改的当前 Git HEAD 直接重跑将生成 `8486b3cd4164489a9bede5e71db248a389ba0f5ef3dc616ed4a75e4fb95aad5a`；当前 V3 checkout 已生成 B′ `bd3ed1f896b81fa3317c2e7f5eaf9d6051976483693f75288b6b3636d1dd004b`，二者均不能将产物冒充 `5182e532feca7ba4337692b112b06f181d6f79ee85596eacf83c9109b14fb709` 结果。
3. 当前 n100 结果不能外推为 n200/n300 选型：实例规模、模块/网络/terminal 数据、搜索状态空间、运行时间和随机误差均改变；即使接口测试全绿，也不替代同窗 n200 运行。
4. 因此 V3 必须在运行前绑定**当前实际代码 hash + n200 数据 manifest + 每候选 config hash**；禁止只写短前缀或沿用历史 hash 作为新证据。

## 3. Q1--Q3 V3 n200 正式选型协议（协议已确认；Q2B′/Q3实现待复核，REVIEWING）

### 3.1 共同冻结、随机性和停止条件

1. **范围与候选先注册**：只运行本文表格列出的候选；候选顺序、参数、种子、预算、机器和输出根目录在第一条正式运行前写入 manifest。运行中不得根据前一候选结果改变后续配置。
2. **输入**：只读 `data/raw/附件/n200.blocks`、`n200.nets`、`n200.pl`（Q1 只读 `.blocks`）；运行前记录文件 bytes、LF-normalized SHA-256、解析行列数与排除数，原始文件不得覆盖。
3. **建议机器/线程**：Windows 主机、`D:\Anaconda\envs\CA-py310\python.exe`、CPython 3.10.20、16 logical CPUs；Q1/Q2 `processes=1, threads=1`、候选顺序执行；Q3 `workers=5`（最多 5 个独立进程，单进程不启用额外 BLAS/OpenMP 线程），候选顺序执行。若机器或 Python 改变而代码/config/data 字节未变，代码、配置和数据 hash 不变，只刷新环境字段及包含环境的运行 manifest hash；若实现依赖环境（例如浮点库、并行顺序或求解器）导致代码路径/结果语义改变，必须另建版本并重新核验。
4. **RNG**：`random.Random`（CPython MT19937）；阈值 cold 种子固定为 `2201--2220`。Q1/Q2 每候选恰好 20 个 seed；Q3 每个阈值恰好 20 个 cold seed。Q3 选中轮廓的 final 运行建议使用独立注册集 `2301--2320`，不得复用阈值阶段布局/状态；若人工决定仍使用 `2201--2220` 标签，也必须以全新 final 调用、全新输出路径登记，不能把旧 threshold 记录改标为 final。
5. **单次停止**：达到 `max_evaluations`、达到墙钟上限、或发生未捕获异常时停止并保留 `success/timeout/no_feasible/crash`；不能因中位数暂时领先而提前停止，不能删除失败记录。`timeout`/`no_feasible` 是有限预算观测，不是最优或数学不可行证明。
6. **合法与审计**：`legal_rate = (# legal 且 formal_audit_match 的注册 runs) / (# 注册 runs)`；分母包含 timeout/no_feasible/crash。每条 run 必须保存 formal/audit 指标、布局、状态、实际 evaluations/runtime、命令、环境、code/config/data hash。`formal_audit_match=false` 的记录不能进入“成功合法”分子。

建议的共同判定门槛（**已人工确认；尚无正式运行结果**）：

- 主要候选必须 `legal_rate >= 0.90`（20 次中至少 18 次）且无静默缺失；若所有候选均达不到，则报告“无候选通过门槛”，不降低门槛。
- 非劣 margin 对低优指标统一预注册为 `1%`（候选中位数不超过对照中位数的 `1.01` 倍）；同 seed 配对差值同时报告中位数、IQR 和胜出次数。若 margin、合法率或审计门槛冲突，优先合法率/审计，再谈目标值。
- 所有“优于”只在同一输入、同一代码 hash、同一预算、同一 seed 集、同一机器窗口内比较；跨 V2/n100、跨 hash 或跨机器只做背景，不做选型证据。

### 3.2 Q1：面积/长宽比/合法率/稳定性与 P2 消融

**注册候选（每个 20 seed）**：

| 配置 | 真实候选 | `directed_moves` | `state_dedup` | 角色 |
|---|---|---:|---:|---|
| Q1-G | `Q1-G` | off | off | 几何确定性基线 |
| Q1-SP | `Q1-SP` | off | off | Sequence Pair 候选 |
| Q1-BT | `Q1-BT` | off | off | B*-Tree P1 |
| Q1-BT-D | `Q1-BT-D` | on | on | P2 完整方案 |

预算固定为每 run `100000 evaluations / 180 s / 4 restarts`；Q1 的 code hash 和四个 config hash 见第 1.3 节。P2 消融另行注册同一 Q1-BT-D 预算/seed：`directed-only=(on,off)`、`dedup-only=(off,on)`、`both=(on,on)`；P1 `Q1-BT=(off,off)` 为共同对照。消融不是新的“候选优越”样本，必须在同一 seed 逐对比较。

每个配置须输出：`area=W*H`、`aspect_ratio=max(W,H)/min(W,H)`、`deadspace`、`legal`、formal/audit、evaluations、runtime、restarts、proposal/accepted/duplicate_rejections。汇总表至少有 median、IQR、p90、best/worst、legal rate、audit-match rate、首次合法评价数和同 seed 差值。

**建议选型规则（已确认；尚无正式运行结果）**：

1. 先过合法率/审计门槛；再以 median area 最小为主排序，median aspect ratio 最小为次排序。
2. 候选相对 Q1-G 或当前共同对照的 area median 不超过 `+1%` 时视为面积非劣；`p90 area` 和 area IQR 只能作为稳定性证据，不能用 best 单次结果取代。
3. P2 的“消融支持”机械定义为：相对 Q1-BT，`legal_rate_P2 >= legal_rate_P1 - 0.05`、`median_area_P2 <= 1.01 * median_area_P1`，并且至少满足 `IQR_area_P2 <= 0.95 * IQR_area_P1` 或 `p90_area_P2 <= 0.99 * p90_area_P1`。若任一条件不满足，只报告配对差值，不用 P2 取代 P1；不再使用“有预注册改善”等未定义判词。
4. `Q1-G` 可能跨 seed 完全相同，它是确定性基线，不得把 20 条记录当 20 个独立随机样本；稳定性须同时标注这一事实。

### 3.3 Q2：P0 vs P1/P2、HPWL 与同预算效率

**注册候选（每个 20 seed）**：

| 配置 | 候选与开关 | 角色 |
|---|---|---|
| P0 | `Q2-SP`, `classic`, adaptive off, hypergraph off, `shelf` | 独立参考基线，不是 ground truth |
| P1 | `Q2-BT`, `fast`, adaptive on, hypergraph off, `shelf` | P1 |
| P2 | `Q2-HG`, `fast`, adaptive on, hypergraph on, `shelf` | P2 |

预算固定为每 run `30000 evaluations / 180 s / 4 restarts`，单进程单线程顺序；`d=0.15`、`L=sqrt(A_B(1+d))`、旋转 `0/90`、边界接触合法。随机初始化压力组不进入正式选型，若保留必须另标诊断并不能替代 shelf 主组。

每条 run 除最终 HPWL/合法率外，必须保存：`first_feasible_evaluation/time`、每 restart 初始 HPWL/合法性、最佳初始 HPWL、`improvement_from_initial`、evaluations、runtime、formal/audit。对每个 seed 在固定预算的 25/50/75/100% 检查点记录 solver incumbent best-so-far HPWL，形成同预算效率曲线；校准阶段的评价只估计温度、不产生可接受状态，因而不更新 incumbent；不得用不同预算的终点数字比较。

**建议选型规则（已确认；尚无正式运行结果）**：

1. 先要求 legal rate ≥ 0.90、所有合法 run 审计一致；P0 仅作可信独立参考。
2. 以 median HPWL 为主目标，IQR/p90 与 seed 配对差值为稳健性；候选相对 P0 的 median HPWL 不超过 `+1%` 为 HPWL 非劣。
3. P2 相对 P1 的“同预算支持”机械定义为：`legal_rate_P2 >= legal_rate_P1 - 0.05`、`median_HPWL_P2 <= 1.01 * median_HPWL_P1`，并且满足以下任一条：`median_HPWL_P2 <= 0.99 * median_HPWL_P1`；或 `median_first_feasible_evaluation_P2 <= median_first_feasible_evaluation_P1`；或四个固定预算检查点（25/50/75/100%）中至少三个满足 `median_best_so_far_HPWL_P2 <= 0.99 * median_best_so_far_HPWL_P1`。否则只报告效率/HPWL差值，保留 P1 作为较简单的非劣方案。
4. 不得以一次 best HPWL、P0 名称或 `n100` 结果宣称全局最优/跨规模优越。

### 3.4 Q3：BIN/LIN/CONT-R 的 20 cold + 20 final

三路线均固定内层 `Q2-HG`、`adaptive_constraints=on`、`hypergraph_init=on`、区间 `[0,0.15]`、绝对精度 `0.005`、`decision_rule=robust`、`robust_min_success_rate=0.80`；阈值阶段每个实际尝试的阈值必须运行 20 个 cold seeds `2201--2220`。每个 seed `30000 evaluations / 60 s / 4 restarts`；`workers=5` 只改变并发执行，不改变 seed 或预算。

| 路线 | `continuous_compression` | 阈值停止语义 | 额外运行 |
|---|---:|---|---|
| BIN | off | 二分至 bracket 宽度 ≤ `0.005`；记录 `d_best`、`d_robust` | 选中 `d_robust` 后 20 个独立 final seeds `2301--2320` |
| LIN | off | 固定 `0.005` 网格按注册顺序扫描；不得因暂时领先提前截断 | 同上 |
| CONT-R | on | 与 BIN 相同阈值边界；warm 仅作额外记录 | 每个 warm attempt 不计入 cold 成功率、`d_best`、`d_robust`；同上 final |

阈值 `cold_success_rate = cold legal runs / 20`；`d_robust` 为满足 ≥0.80 的最小注册阈值，`d_best` 为有至少一条 cold 合法布局的最小阈值；若没有阈值达到门槛，报告未选中，不把 `no_feasible` 写成不可行。选中轮廓后必须重新调用 final，不能将阈值阶段同 seed 的布局复制进 final。

**建议选型规则（已确认；尚无正式运行结果）**：

1. 先比较 `d_robust`（越小越好），再比较 final 20 seeds 的 legal rate、median HPWL、IQR/p90；`d_best` 只作边界观测。
2. 若两路线 `d_robust` 相差不超过一个精度格（`0.005`），则先要求 final median HPWL 非劣（不超过对方 `1.01` 倍）且 final legal rate 差不低于 `-0.05`；再按 `(median_HPWL, IQR_HPWL, route_rank)` 字典序决胜，其中预注册 `route_rank(BIN)=0`、`route_rank(LIN)=1`、`route_rank(CONT-R)=2`。因此没有“明确差异”这一自由裁量；并列时按固定 route_rank，所有原始差值仍进入报告。
3. `CONT-R` warm 结果不得进入 cold 样本、不得单独构成稳健性证据；所有 timeout/no_feasible 保留在 failure summary。
4. Q3 顶层 `status=timeout` 仍可有合法 final 布局，但不能称最优；只有明确声明的完整搜索/数学下界才可使用“最优”措辞。

### 3.5 统一结果表与论文交接

每问至少交接以下文件（路径可在人工确认后调整，但字段不可删）：

- `outputs/qN/tables/v3_n200_<candidate>_run_details.csv`：逐 run 全字段；
- `outputs/qN/tables/v3_n200_<candidate>_summary.csv`：合法率、目标中位/IQR/p90、状态计数、预算与环境；
- `outputs/qN/tables/v3_n200_manifest.json`：候选顺序、代码逐文件 manifest、数据逐文件 manifest、config JSON/hash、命令、RNG、机器/线程、停止语义；
- `outputs/qN/tables/v3_n200_pairwise.csv`：同 seed 配对差值、非劣判定、胜出次数和 margin；
- `paper/qN/v3_handoff.md`：只把通过人工复核的数字写成方法/阶段结论，明确 `DRAFT/REVIEWING` 待确认项。

每个关键数字必须可沿 `summary → run_details → layout/result JSON → command/code/data hash` 回溯；运行结束后先由建模负责人和交叉复核人检查，再考虑阶段状态变化。本文不替人工复核人标记 `VERIFIED/FINAL`。

### 3.6 V3 编排与 dry-run 实现边界

新增 `src/v3.py` 负责从当前 checkout 生成完整 hash/config/seed manifest、在子进程启动前执行候选/预算/线程/RNG/停止条件/输出根目录/Q2B′ 的 fail-closed 检查，并把 `src/v3.py` 与被调用核心逐文件 bytes/SHA 写入不可变 `outputs/v3_frozen_manifest.json`。现有 marker 必须含完整字段、sidecar fingerprint 与合法 JSON；Q1/Q2 marker 还必须含 data_hash，Q3 同时验 result、attempts、final seed 集合和 tables marker。`python -B -m src.v3 dry-run --problem q2` 只打印 60 条计划；正式入口 `python -B -m src.v3 run --problem q2 --execute` 仍需人工显式授权，失败重试必须传新的 `--attempt` 后缀，且本轮不执行。

Q1/Q2 汇总支持注册集合分母（缺失 seed 计数）、合法率、审计率、状态计数、面积/长宽比或 HPWL 的 median/IQR/p90 及同 seed 差值；Q2 输出 25/50/75/100% 同一 trajectory checkpoint 并明确 `checkpoint_status`。Q3 汇总将 threshold cold、CONT-R warm 和 final cold 分母严格分开，按阈值报告 cold 缺失、`d_best`/`d_robust`、final 20 seed 的合法率/HPWL/IQR/p90 与阶段失败计数。摘要 CLI 读取运行产物并以 `write_once` 写入隔离表，不把 warm/final 混入 cold。

Q4 由 `python -B -m src.v3 q4-check` 提供真实独立 checklist：冻结整数声明域 `G-/G0/G+`、domain `9x9/12x12`、exact/SA 预算矩阵，写入完整 code/config hash 与环境；continuous domain 明确为 false，且 checklist 拒绝任何 n200/n300 选型标签。几何或域定义变更时必须重新生成并人工确认，当前正式 Q4 运行仍阻塞。

## 4. Q4 V3 扩展协议（不是 n200 选型）

### 4.1 目标与冻结基线

Q4 V3 只回答“几何声明、搜索预算和域边界改变时，四模块结果是否敏感”，不引入 `n200`、不比较 Q1--Q3 候选，也不把 SA best 写成最优。基线沿用人工确认的 `b1` 横梁厚度 2、模块面积 `12/6/2/4`、旋转 `0/90/180/270`、整数平移步长 1、边界接触合法、正面积重叠非法；基线 exact/SA 证据仅作 V2 对照。

若要执行几何变体，必须先由人工确认变体是否仍代表题意，并为每个变体重新生成 geometry/model/code hash；不得直接把变体结果并入基线表。建议几何敏感性注册：

- `G0`：确认基线 `b1 beam thickness=2`；
- `G-`：厚度 1（仅在顶点闭合、模块面积和题意均复核后允许）；
- `G+`：厚度 3（同上）；
- 可选 `Grot`：固定基线几何但只允许题面确认的旋转子集，作为声明域敏感性，不得与几何变化混在一组。

Q4 当前已由 `q4_extension_checklist()` 生成整数声明域的完整 64-hex `code_hash=ebd6e86d9da5e1aa373ebb25cfbcf2a079863f2c450268174c30e9f5d9f38043`、聚合 `config_hash=1ca180449987b53740782fb797d7046a3fad2c6b724e6078413917bc932594e4`，并写入 `outputs/v3_frozen_manifest.json`；该清单仅可进入人工复核，continuous domain 保持 false，未授权前仍阻塞正式运行。

### 4.2 搜索/预算敏感性

- Exact：对每个已确认几何变体，在整数平移声明域运行 `upper_area=36`、`grid_step=1`、`time_limit=300 s`；保存 `width_range/height_range/containers_total/containers_checked`、`status`、`complete`、上下界和 exact/audit 一致性。若要测试连续平移，必须新增独立连续域实现并另给 code hash；当前整数 exact 不能自动证明连续域结论。只有达到模块面积下界且证明路径覆盖连续域时，才可写连续域下界结论。
- SA：固定同一几何/域/初始行布局，预注册预算矩阵 `max_evaluations ∈ {10000,30000,60000}`，`time_limit ∈ {60,120}` 只在人工确认资源足够时采用；每个单元使用独立 seeds `2201--2220`、4 restarts，记录合法率、best/median/IQR/p90 area、evaluations、runtime、相对 exact incumbent 的 gap。预算敏感性是观测曲线，不是证明。
- 对 `domain=(9,9)` 与扩大域（例如 `domain=(12,12)`）可做独立域敏感性，但每个域必须单列配置/hash，不能将不同域结果合并为一个 SA 分布。

### 4.3 论文图与交接

在通过人工复核后，论文图建议至少包括：

1. 几何变体 G-/G0/G+ 的可编辑布局图（SVG/PDF + PNG 预览），并在图注写明顶点、面积、旋转和声明域；
2. SA budget--area 曲线（median 与 IQR/p90，横轴 evaluations，标注 exact incumbent）；
3. 几何/域敏感性的 area gap 或合法率热图；
4. exact 与 SA 的代表布局对照图，明确 SA 不是最优证明。

图形数据必须来自 `outputs/q4/tables/v3_*`，绘图脚本/中间 QA 保留在本地复现包；使用 `nature-figure` 规范导出和视觉检查。当前本文不生成图、不修改 `outputs/q4/figures/`。

### 4.4 局限与禁止表述

- `b1` 厚度 2 的来源是用户确认，不等同题面 PDF 独立文字证据；变体结论只能在声明边界内解释。
- 整数声明域 exact 不是连续域 exact；除非面积下界与连续域证明同时成立，不得写“连续全局最优”。
- SA 固定预算、有限 seeds 只支持分布/预算敏感性；best seed、median 或 `gap=0` 不能证明全局最优。
- Q4 没有 nets，`HPWL=0` 不是优化效果；几何扩展不应迁移成 Q1--Q3 的 HPWL 结论。
- Q4 V3 结果不称 `n200` 选型，不与 Q1--Q3 的 n200 候选排名合并，不进入 `outputs/q4/final/` 直至人工复核和论文最终门槛完成。

## 5. 人工确认清单与解锁条件

在任何 n200 正式运行或 Q4 扩展前，人工复核人需逐项确认并记录日期/签名：

1. Q1/Q2/Q3 候选是否按本文冻结，P2 消融是否全量执行；
2. `max_evaluations`、wall-clock、restart、workers、Python/机器线程是否接受；
3. cold `2201--2220` 与 final `2301--2320` 是否接受，是否需要保持同一 seed 标签但独立调用；
4. legal rate ≥0.90、Q3 cold robust ≥0.80、area/HPWL 非劣 margin 1%、稳定性/效率 tie-break 是否接受；
5. Q4 `G-/G0/G+`、9x9/12x12、exact/SA 预算矩阵及论文图需求是否明确授权；连续域当前不在声明范围；
6. 变更后是否重新生成完整 manifest/config snapshot，并将本文状态保持为 `REVIEWING` 直到复核完成。

本轮解锁前还需确认：Q1 core code hash `3191e8fa3cfd8aaa7948395b9026ff11bb50871a09425b05f1d85c6a8a6a5aaa` 因正式 marker 增加 `data_hash` 字段而变化；Q2/Q3/Q4 core code hash 与 V3 runner overall manifest hash 分别见第 1.3 节和 `outputs/v3_frozen_manifest.json`，所有 hash 必须按 core/overall 两层逐字核对。当前正式 n200 尚未运行，等待人工重新确认 Q1、Q2 B′、Q3、Q4 及 runner 后方可解锁。

**解锁规则**：完整协议和原 Q2B 已确认，但 Q2B′ checkpoint 实现与 Q3-LIN 全网格实现需要重新人工确认；在主代理验收冻结清单、输出隔离和运行证据前，本文保持 `REVIEWING`，只可做 dry-run、非正式小夹具和协议修订。不得以 V2 n100 结果、测试或历史 `5182e532feca7ba4337692b112b06f181d6f79ee85596eacf83c9109b14fb709` 快照替代 n200 正式证据；n300 仍不可调参/选型。
