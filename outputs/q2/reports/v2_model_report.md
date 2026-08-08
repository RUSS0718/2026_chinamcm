# Q2 V2：固定轮廓实现与候选入口

- 状态：REVIEWING
- 更新：2026-08-08
- 实现目录：`src/Q2/`
- 公共入口：`python -B -m src.Q2 run`、`python -B -m src.Q2 batch`
- 本阶段只报告 n100 开发粗筛观察，不作 n200 正式选型或最终模型结论，不迁移文件到 `outputs/q2/final/`。

## 已冻结口径

设模块总面积为 `A_B`，题面死区比例固定为 `d=0.15`：

```text
L = sqrt(A_B * (1 + d))
rho = d / (1 + d)
```

轮廓固定为 `(0, 0, L, L)`。模块可以旋转 0/90 度；边界接触合法；正面积重叠不合法。模块引脚取旋转后矩形中心，`.pl` 中的 Terminal 坐标保持绝对坐标并直接计入网络 HPWL：

```text
HPWL = sum_net ((max x_pin - min x_pin) + (max y_pin - min y_pin))
```

搜索内层利用 B*-Tree contour 或 Sequence Pair 解码的无重叠性质快速计算轮廓溢出和 HPWL；每次运行的最终候选仍由共享 `evaluate` 和独立 `audit_layout` 复算。浮点口径不额外放宽，坐标容差记录为 `0.0`。

## 候选实现

| 候选 | 实现 | 开关 |
|---|---|---|
| Q2-SP（P0） | 独立 Sequence Pair + Fast-SA；首个 restart 使用固定轮廓 shelf 初始化再编码为 Sequence Pair | `adaptive_constraints` 默认 OFF |
| Q2-BT（P1） | 复用 Q1 `BTreeState`、contour 解码和旋转/移动/交换邻域；固定轮廓可行性优先 | `adaptive_constraints` 默认 ON |
| Q2-HG（P2） | P1 上增加网络超图连接度的软初始化 | `hypergraph_init` 默认 ON，可显式 OFF 做消融 |

可行性优先规则为：不可行状态之间只比较轮廓溢出；合法状态之间才比较 HPWL；最终选型仍需统一预算、多种子和独立复核。

## 结果记录

单次运行写入 `layout.json` 和 `events.jsonl`，记录：候选、开关、随机种子、代码/配置哈希、轮廓边长、实际布局宽高、边界溢出、合法性、HPWL、首次合法解评价次数/时间、运行时间、评价次数、状态和错误信息。`batch` 另外写入运行明细、汇总和配置快照 CSV/JSON。

## 实际验证

使用工作区绑定 Python 运行：

```text
C:\Users\CQX\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -B -m unittest discover -s tests -v
```

当前结果：14 个测试全部通过，其中包括 Q2 三个候选的固定轮廓、独立审计、Terminal/HPWL 一致性、同 seed 可复现性、P0/P1 固定轮廓初始化，以及 P2 初始化开关 OFF/ON 不破坏 n100 可行性。

P0、P1 和 P2-ON 在 `n100`、`max-evaluations=1` 的回归门槛中均由固定轮廓初始化直接得到合法布局；该事实只证明可行域入口稳定，不构成性能结论。

## n100 开发粗筛

冻结协议如下：

- 实例：`n100`；种子：`2101-2110`；
- 每次最多 `30000` 次评价、`60 s`、`4` 次重启；
- 优化器代码哈希：`fac6f6f1cd9dc87cfcf4b3a2aa7efd2f72b589c68f28562029218338dd395f4e`；
- 输入完整性与哈希沿用 `data/processed/round0_audit.json`；
- P0/P1 以及 P2-OFF/P2-ON 分别以成对并行进程运行。并行会影响墙钟吞吐，因此运行时间和 P0/P1 有效评价次数只能作为开发参考；P2 OFF/ON 均完成 30000 次评价，配对 HPWL 可直接比较。

| 配置 | 合法/总数 | success/timeout/no_feasible/crash | 最好 HPWL | 中位 HPWL | 中位首次合法评价 | 中位评价数 | 中位运行时间/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0：Q2-SP | 10/10 | 0/10/0/0 | 296924.5 | 297261.0 | 1 | 19193 | 60.0012 |
| P1：Q2-BT | 10/10 | 7/3/0/0 | 256205.5 | 263293.5 | 1 | 30000 | 49.3426 |
| P2-OFF：Q2-HG，初始化关闭 | 10/10 | 10/0/0/0 | 256205.5 | 263293.5 | 1 | 30000 | 53.2089 |
| P2-ON：Q2-HG，初始化开启 | 10/10 | 10/0/0/0 | 241764.5 | 248082.75 | 1 | 30000 | 50.1392 |

开发观察：

- P1 相对 P0 在 10/10 个配对种子上 HPWL 更低；`P1-P0` 差值中位数为 `-33967.5`，配对相对差值中位数为 `-11.4268%`。
- P2-ON 相对 P2-OFF 在 10/10 个配对种子上 HPWL 更低，且合法率未下降；`ON-OFF` 差值中位数为 `-15541.25`，配对相对差值中位数为 `-6.0178%`。
- 以上只支持“P1、P2 可进入 n200 正式协议”的开发决策；不证明总体优越性，也不替代 n200 选型和 n300 留出验证。

可复现汇总入口：

```text
python -B -m src.Q2.summarize --p0 outputs/q2/tables/v2_n100_p0_current_run_details.csv --p1 outputs/q2/tables/v2_n100_p1_current_run_details.csv --p2-off outputs/q2/tables/v2_n100_p2_off_current_run_details.csv --p2-on outputs/q2/tables/v2_n100_p2_on_current_run_details.csv --output-root outputs/q2/tables --run-id v2_n100_current
```

核心输出：

- `outputs/q2/tables/v2_n100_current_run_details.csv`：40 条完整运行记录；
- `outputs/q2/tables/v2_n100_current_summary.csv`：四配置汇总；
- `outputs/q2/tables/v2_n100_current_paired_differences.csv`：P1-P0 与 P2-ON-P2-OFF 配对差值；
- `outputs/q2/tables/v2_n100_current_comparison_snapshot.json`：输入表、代码哈希、预算和种子快照。

## 开发故障与修复记录

- 初版 P1 使用随机 complete B*-Tree，四重启分段后每个 restart 只有约 7500 次评价，seed 2101 在 30000 次总预算下未找到合法解；历史失败记录保留在本地带 `smoke` 的开发批次中，不纳入本阶段提交范围。
- 修复为共享合法 shelf 几何、分别编码为 Sequence Pair 与 B*-Tree 后，P0/P1 的首次合法评价均稳定为 1。
- 初版 P2-ON 直接用超图顺序替换 complete tree 标签，seed 2101 出现 `no_feasible`；随后限制为合法 shelf 同一行内的超图软排序，保持行内模块集合、旋转和总宽不变。修复后才重新运行当前代码哈希下的全部 P0/P1/P2 批次。

## 未完成与风险

- n100 已完成开发粗筛，但尚未执行 n200 正式选型和 n300 留出验证，因此不能写成最终模型性能结论。
- P0 十次均触发 60 秒上限，且有效评价次数低于 P1；n200 协议需要明确以墙钟时间还是评价次数作为主预算，并避免并行资源竞争污染时间比较。
- Q2-HG 目前只有软初始化，未实现高风险的局部精确修复；这是有意保留的范围边界。
- 阶段状态仍为 `REVIEWING`，需要交叉复核人确认参数、运行预算和正式结果表后才能进入 `VERIFIED`。
