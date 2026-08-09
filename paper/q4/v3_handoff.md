# Q4 V3 论文交接（VERIFIED）

## 可用证据

Q4 V3 是独立的整数声明域扩展，不属于 `n200` 选型。正式运行注册 726 个 slot：G-/G0/G+ × 9x9/12x12 的 6 个 exact，以及相同几何×域下 3 个评价次数（10000、30000、60000）×2 个时间上限（60、120 秒）×20 个 cold seeds（2201--2220）的 720 个 SA。外层 workers=8，每 run 单进程单线程，OMP/MKL/OPENBLAS 均为 1。

运行根为 `outputs/q4/_runtime/v3_integer_domain`，注册/发现 726/726，状态为 exact `optimal=6`、SA `success=600`、`timeout=120`，无 `no_feasible` 或 crash；formal 与声明域审计均为 726/726。逐单元 CSV 为 `outputs/q4/tables/v3_integer_domain_summary.csv`，中文摘要为 `outputs/q4/tables/v3_integer_domain_summary_cn.json`。

Exact 紧包围盒目标面积：G- 在两个声明域均为 24，G0 在两个声明域均为 24，G+ 在两个声明域均为 28。SA 每个预算单元合法率均为 1.0；面积中位数、IQR、P90、最大值和同格 exact incumbent gap 请直接引用 CSV，不从图像或单次 best 推断。

## 哈希与复现

不可变执行快照为 `outputs/q4/tables/v3_integer_domain_execution_manifest.json`：execution code `51df5eac273ea439410170bda7198b38ed3c360bad647679442303aea02f7db3`，execution runner `8a156193b83a7d13fa40d0b708809626162dd9ce0ba39a42c6572ffae7a9c8d8`，config `6153919d92e2740f8e07ffd59c13a958680dc0f32d0fc3995195d5b1db034ed4`，data `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`。正式命令是 `D:\Anaconda\envs\CA-py310\python.exe -B -m src.v3 run --problem q4 --execute`，base commit 为 `ad1495f8f08ec863850d4291484e355bbd403a13`。

正式运行后修复了汇总 CLI 的 join 缺口：marker 不含 `config_id` 时，汇总仅在完整 sidecar/marker 验真通过后从注册 plan fingerprint 注入。生成本汇总的分析 runner 为 `17965f265464e1acd72667e2edd0e4d4c44c7c7b51e4ad5f295cc1aeb257e277`；合并 Q2 后当前分析 runner 为 `cdba59be5cbf10dabceb37eb98f4dc686ed5f2362b2c906e96f2eed6bea901d2`。两者都不追溯修改执行快照或 runtime marker。

## 论文口径与限制

- `formal/audit` 是紧包围盒目标指标；`domain_formal/domain_audit/domain_audit_match` 是声明 9x9 或 12x12 域内证据。报告面积应使用 objective `formal.area`，不能把域面积 81/144 当作结果面积。
- `upper_area=36` 只支持声明整数域内的完整搜索范围；不支持连续域全局最优或全域不可行表述。
- SA 的 timeout 必须保留并纳入分母；incumbent gap 只相对同几何同声明域 exact 参考。SA best、median 或 gap=0 均不等价于全局最优。
- Q4 无 nets，HPWL=0 仅为共享 schema 字段，不作优化效果结论。

2026-08-09，人工复核人（用户）接受声明整数域、完整 exact 界、SA 预算敏感性和 timeout 保留边界，批准本交接为 `VERIFIED`，但不是 `FINAL`。不得生成 `final/`、连续域结论或把 SA 命中 exact 写成最优性证明。

论文图：[`v3_route_layouts.png`](../../outputs/q4/figures/v3_route_layouts.png)与[`v3_exact_sa_consistency.png`](../../outputs/q4/figures/v3_exact_sa_consistency.png)。
