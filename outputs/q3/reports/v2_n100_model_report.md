# Q3 V2 n100 模型报告（VERIFIED）

本文件已于 2026-08-09 通过人工复核，阶段为 `VERIFIED`，但不是 `FINAL`。统计只来自三次整合后正式运行的 `result.json`/`layout.json`；首次 BIN 运行因命令与环境追溯修复已标记为 `superseded due to command/environment trace fix`，归档在 `outputs/q3/_runtime/v2_n100/n100/v2_n100_q3_bin_pre_trace_fix`，不进入本汇总。

## 1. 口径、符号与模型

实例为题面 n100，模块面积记为 `A_B`，布局包围盒为正方形边长 `L`。死区与题面比率为

```text
deadspace = area - module_area
d = dead_space_ratio = deadspace / module_area
L(d) = sqrt(A_B * (1 + d))
rho = deadspace / area = d / (1 + d)
```

网络半周长为 `HPWL = (max x - min x) + (max y - min y)`，总 HPWL 为所有网络之和。正面积重叠非法，边界接触合法；`no_feasible` 仅表示给定有限预算没有找到合法布局，不是数学不可行证明。Q3 实际使用 `Q2-HG` 作为内层候选。

外层候选差异为：`Q3-BIN` 对死区区间作二分，`Q3-LIN` 以 `0.005` 固定步长扫描，`Q3-CONT-R` 作二分并把 warm 状态作为额外记录。每个阈值的 cold 统计只含预注册 seeds `1101--1110`；warm 不计入 cold 成功率、`d_best` 或 `d_robust`。选定阈值后另行运行 10 个 `final_cold`，不复用阈值阶段结果。

## 2. 冻结参数、入口与环境

三候选均使用 `lower_ratio=0`、`upper_ratio=0.15`、`precision=0.005`、`robust_min_success_rate=0.8`、`decision_rule=robust`、`max_evaluations=30000`、`time_limit=60`、`restarts=4`、`workers=5`，final 使用同样的 10 seeds、30000 次评价、60 s、4 restarts。实际入口是 `python -B -m src.Q3`。

实际运行命令均以以下绝对解释器开头，并保存在逐候选比较表的 `command` 字段：

```text
D:\Anaconda\envs\CA-py310\python.exe -B -m src.Q3
```

环境字段来自结果文件：Python `3.10.20`、平台 `Windows-10-10.0.26200-SP0`、工作目录为仓库根目录、`cpu_count=16`。三候选共享 `_code_hash=a3971eefa77bc2cdaecd9fa0f59e85fc37668df57d6587d2217ec3f416ae8215`；候选配置哈希分别为：BIN `ebd9648137db72f8db15cb6923d784118878de4e12618d2b52d0381158ebbca6`、LIN `6d43b5af6cd886a44776f53e8cb57a547f4c1d49d07985a39cb47672563483b1`、CONT-R `1888f1899323904cc73aa4ff9833e78c17b354c4b234e6588590bd2fb6dfb131`。

## 3. 可追溯结果

完整阈值记录见 [`v2_n100_threshold_summary.csv`](../tables/v2_n100_threshold_summary.csv)，final seed 明细见 [`v2_n100_final_seed_details.csv`](../tables/v2_n100_final_seed_details.csv)，候选比较见 [`v2_n100_candidate_comparison.csv`](../tables/v2_n100_candidate_comparison.csv)，失败/非成功状态见 [`v2_n100_failure_summary.csv`](../tables/v2_n100_failure_summary.csv)，最终布局模块见 [`v2_n100_final_layout_modules.csv`](../tables/v2_n100_final_layout_modules.csv)。

| candidate | 阈值数 | cold / warm / final | `d_best` = `d_robust` | final 合法率 | final HPWL best / median / Tukey IQR | 顶层状态 | 墙钟秒 |
|---|---:|---:|---:|---:|---:|---|---:|
| Q3-BIN | 7 | 70 / 0 / 10 | 0.065625 | 10/10 | 248215.5 / 258206.5 / 11615.0 | timeout | 963.5561 |
| Q3-LIN | 19 | 190 / 0 / 10 | 0.065 | 10/10 | 248106.5 / 258206.5 / 12244.0 | timeout | 2409.2094 |
| Q3-CONT-R | 7 | 70 / 6 / 10 | 0.065625 | 10/10 | 248106.5 / 258206.5 / 12244.0 | timeout | 1323.9317 |

每个候选的 final 合法率分母固定为 10；上述 HPWL 统计只对合法 final 记录计算。本报告采用 Tukey 上下半样本中位数（n=10 时下五个与上五个）定义 Q1/Q3/IQR。所有阈值/final 记录的 `formal_audit_match` 均为 true，且每个 layout 文件的 formal/audit 指标字典相等。

阈值层面，BIN 记录 7 个阈值（3 个 cold 全合法、4 个 `no_feasible`）；LIN 记录 19 个阈值（18 个 cold 全合法、最低 `0.06` 为 `no_feasible`）；CONT-R 记录 7 个阈值，warm 额外 6 条且未改变 cold 统计。非成功状态完整保留：BIN 共 40 条 cold `no_feasible`、30 条阈值 `timeout`、10 条 final `timeout`；LIN 共 10 条 `no_feasible`、180 条阈值 `timeout`、10 条 final `timeout`；CONT-R cold 共 40 条 `no_feasible`、30 条阈值 `timeout`，warm 为 4 条 `no_feasible` 与 2 条 `timeout`，final 为 10 条 `timeout`。三候选均无非空 `error` 字段。

## 4. 复核边界与局限

- `timeout` 表示达到墙钟/预算边界时仍保留当前结果；不等于最优性证明。
- `no_feasible` 仅是有限预算内未找到布局，不得写成连续或整数域不可行证明。
- 结果是 n100、固定机器/参数/10 seeds 的阶段性开发证据；不能外推到 n200、n300、其他预算或题面外设定。
- 代码测试验证入口、正式评价器和独立审计字段一致性，但测试不是模型效果证据。
- 本轮不生成 V3 敏感性结论，也未将任何材料迁入 `outputs/q3/final/`。

## 5. 人工复核结论与下一步

2026-08-09，指定人工复核人接受 30 个 final seed、三份 layout、366 条正式记录、协议参数、命令/环境/hash 与表格聚合，批准本阶段为 `VERIFIED`。该状态只覆盖 n100 V2 开发证据；timeout、no_feasible、跨规模外推和 V3 局限仍然有效，本文件不是论文定稿。
