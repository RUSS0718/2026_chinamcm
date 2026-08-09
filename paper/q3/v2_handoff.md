# Q3 V2 n100 论文手交接（VERIFIED）

本 handoff 已于 2026-08-09 通过人工复核，状态为 `VERIFIED`，可用于 V2 方法章节和 n100 阶段性结果；它不是 `FINAL`，也不授权迁入 `outputs/q3/final/`。

## 可写入方法章节的骨架

1. **问题与符号**：以 `module_area` 为模块面积和，`deadspace=area-module_area`，题面比率 `d=deadspace/module_area`，正方形轮廓 `L(d)=sqrt(A_B(1+d))`；HPWL 为网络包围盒半周长总和。
2. **约束**：正面积重叠禁止、边界接触允许；布局结果必须同时通过正式评价器与独立 audit。
3. **候选路线**：BIN 为外层二分，LIN 为 0.005 步长线性扫描，CONT-R 为二分加 warm 状态。三者内层均为 Q2-HG；warm 只作额外诊断记录，不进入 cold 成功率、`d_best` 或 `d_robust`。
4. **预算**：每个阈值 10 个 cold seeds `1101--1110`，30,000 evaluations、60 s、4 restarts、5 workers；选定阈值后另跑 10 个独立 `final_cold`，不能把“阈值 10 次 + final 10 次”写成总共 10 次。

## 阶段性结果证据（可复查，不是正式结论）

- 完整阈值、final、候选比较、失败状态和最终模块坐标分别见 [`v2_n100_threshold_summary.csv`](../../outputs/q3/tables/v2_n100_threshold_summary.csv)、[`v2_n100_final_seed_details.csv`](../../outputs/q3/tables/v2_n100_final_seed_details.csv)、[`v2_n100_candidate_comparison.csv`](../../outputs/q3/tables/v2_n100_candidate_comparison.csv)、[`v2_n100_failure_summary.csv`](../../outputs/q3/tables/v2_n100_failure_summary.csv)、[`v2_n100_final_layout_modules.csv`](../../outputs/q3/tables/v2_n100_final_layout_modules.csv)。
- BIN：7 阈值、70 cold、0 warm、10 final，`d_best=d_robust=0.065625`，顶层 `timeout`，final 合法率 10/10，HPWL best/median/IQR = 248215.5/258206.5/11615.0。
- LIN：19 阈值、190 cold、0 warm、10 final，`d_best=d_robust=0.065`，顶层 `timeout`，final 合法率 10/10，HPWL best/median/IQR = 248106.5/258206.5/12244.0。
- CONT-R：7 阈值、70 cold、6 warm、10 final，`d_best=d_robust=0.065625`，顶层 `timeout`，final 合法率 10/10；6 条 warm 未计入 cold 指标，HPWL best/median/IQR = 248106.5/258206.5/12244.0。
- 三候选所有记录 `formal_audit_match=true`，layout formal/audit 相等；所有非成功状态保留，`no_feasible` 不是数学不可行证明。

## 复现与追溯

真实入口为 `D:\Anaconda\envs\CA-py310\python.exe -B -m src.Q3`，完整实际命令在候选比较表 `command` 字段；环境为 Python 3.10.20、Windows-10-10.0.26200-SP0、仓库根目录、16 CPUs。统一代码哈希为 `a3971eefa77bc2cdaecd9fa0f59e85fc37668df57d6587d2217ec3f416ae8215`；每候选 config hash 和 runtime_seconds 见比较表。首次 BIN 产物旧 hash `144fa968a824ac6f943c9f547f54506bfe683c4e14befce0780c3cfc917a3b87` 已因命令/环境追溯修复标记为 `superseded due to command/environment trace fix`，只保留在 `outputs/q3/_runtime/v2_n100/n100/v2_n100_q3_bin_pre_trace_fix`，不纳入本 handoff。

## 不能写入正式结论的内容

- 不能把任何 `timeout` 结果写成最优、全局最优或连续域最优。
- 不能把 `no_feasible` 写成不可行证明。
- 不能把 warm 记录当作 cold 成功率或阈值稳健性样本。
- 不能外推到其他规模、预算、机器、种子或未经确认的模型设定。

## V3 待办与状态

V3 可考虑预注册的预算/种子敏感性、候选差异的同窗比较和更完整的误差/不确定性报告，但需先冻结方案并重新运行，不能从本轮结果倒推。当前 V2 n100 阶段状态为 `VERIFIED`；任何影响现有关键数字的变化必须退回 `REVIEWING`。
