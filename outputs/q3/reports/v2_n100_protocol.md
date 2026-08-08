# Q3 V2 n100 开发实验协议

- 检查点：待重跑协议。当前 `_code_hash=144fa968a824ac6f943c9f547f54506bfe683c4e14befce0780c3cfc917a3b87`，与旧产物的整合前哈希 `bc42b101f2ed299627044a5cd195e25528f3bf56b42bdbdb85318b9e2483fad7` 不一致；旧产物不得用于 Q4 或最终结论。
- 重跑范围：BIN、LIN、CONT-R 均待在整合后代码上按本协议全量重跑；以下参数继续作为下一次运行的冻结协议。
- 状态：REVIEWING
- 冻结日期：2026-08-08
- 实例：`n100`
- 目的：开发阶段比较 Q3 外层死区搜索策略，检查边界记录、稳定性和最终轮廓复优化流程。
- 证据边界：本协议只用于 n100 开发比较，不构成 n200 正式选型、数学不可行证明或最终模型结论。

## 统一口径

- 题面死区比例：`d=deadspace/module_area`。
- 正方形轮廓边长：`L(d)=sqrt(A_B*(1+d))`。
- 搜索区间：`[0.0, 0.15]`。
- 绝对搜索精度：`0.005`。
- cold 成功率门槛：`0.8`，即 10 个预注册种子中至少 8 个找到合法布局。
- 阈值选择：使用 `decision_rule=robust`，最终轮廓取 `d_robust`。
- 内层候选：三个外层候选统一使用 `Q2-HG`，避免同时改变外层策略和内层模型。
- 内层默认开关：`adaptive_constraints=on`、`hypergraph_init=on`。
- 失败语义：`no_feasible` 或 `timeout` 只表示有限预算内未找到，不是不可行证明。

## 候选与开关

| 运行 ID | 外层候选 | 连续压缩 | 定位 |
|---|---|---:|---|
| `v2_n100_q3_bin` | `Q3-BIN` | OFF | P1 二分主干 |
| `v2_n100_q3_cont_r` | `Q3-CONT-R` | ON | P2 二分 + warm start |
| `v2_n100_q3_lin` | `Q3-LIN` | OFF | P0 固定步长基线 |

实际候选顺序为 BIN → LIN → CONT-R；这是用户在 BIN 验收后于 2026-08-08 明确调整的执行顺序。n100 阶段不得根据前一候选结果修改后续候选的区间、精度、种子或预算。

## 种子与预算

- 阈值 cold runs：`1101-1110`。
- 最终轮廓复优化：`1101-1110`，在选定轮廓下重新独立运行，不复用阈值阶段结果。
- 每个 seed 最大评价次数：`30000`。
- 每个 seed 墙钟上限：`60s`。
- 每个 seed 重启数：`4`。
- 三候选保留全部失败运行、warm/cold 模式、评价次数和实际运行时间。
- CONT-R 的 warm attempt 是额外辅助运行，不计入 cold 成功率、`d_best` 或 `d_robust`。

## 环境

- Python：`D:\Anaconda\envs\CA-py310\python.exe`，Python `3.10.20`。旧 n100 记录中的 Codex bundled CPython `3.12.13` 与 BIN 实际运行环境不一致；本次整合后 BIN、LIN、CONT-R 均按此 Python `3.10.20` 协议全量重跑。
- 系统：Windows 11，`AMD64 Family 25 Model 97 Stepping 2`。
- 逻辑处理器：16。
- 执行方式：候选按 BIN → LIN → CONT-R 顺序运行；同一候选最多 5 个 seed 进程并行，候选之间不并行。
- 输入：`data/raw/附件/n100.blocks`、`n100.nets`、`n100.pl`，程序不得修改原始文件。

## 固定命令

公共参数：

```text
--instance n100
--inner-candidate Q2-HG
--lower-ratio 0
--upper-ratio 0.15
--precision 0.005
--robust-min-success-rate 0.8
--decision-rule robust
--seeds 1101-1110
--max-evaluations 30000
--time-limit 60
--restarts 4
--workers 5
--adaptive-constraints on
--hypergraph-init on
--final-seeds 1101-1110
--final-max-evaluations 30000
--final-time-limit 60
--final-restarts 4
--raw data/raw/附件
--runtime-root outputs/q3/_runtime/v2_n100
--table-root outputs/q3/tables
```

候选命令分别增加：

```text
--candidate Q3-BIN --continuous-compression off --run-id v2_n100_q3_bin
--candidate Q3-CONT-R --continuous-compression on --run-id v2_n100_q3_cont_r
--candidate Q3-LIN --continuous-compression off --run-id v2_n100_q3_lin
```

## 验收输出

每个候选必须保存：

- 完整阈值尝试和 final seed 明细；
- `d_best`、`d_robust`、`selected_ratio`；
- 每个阈值的 cold 成功率、warm/cold 模式和状态；
- 最终最佳合法布局、HPWL、共享评价与独立审计一致性；
- 代码哈希、配置哈希、命令和实际运行时间。

三候选完成后再生成统一比较表；运行过程中不得迁入 `outputs/q3/final/`。
