# Q4 V2 论文手交接（VERIFIED）

状态：`VERIFIED`。2026-08-09 人工复核接受 `b1` 横梁厚度 2、exact 声明域和现有证据。本材料可用于 V2 方法与阶段性结果，但不是 `FINAL`，不应直接作为最终论文结论提交。

## 可写入方法章节的内容

本题只含题面四个异形模块 `b1`--`b4`。当前用户确认 `b1` 顶部横梁厚度为 2；采用的局部顶点面积为 `b1=12`、`b2=6`、`b3=2`、`b4=4`，总模块面积 24。模块允许 `0/90/180/270°` 旋转；旋转后以外接框左下角为锚点，整数平移网格步长为 1；边界接触合法，正面积重叠非法。

布局变量是模块整数锚点和离散方向。目标外接框面积为 `A_box=W·H`，空白面积为 `deadspace=A_box−24`，`dead_space_ratio=deadspace/module_area`，相对空白为 `rho=deadspace/A_box`。多边形面积用鞋带公式计算；正式评价器和独立 `audit_layout` 均需验证合法性与指标一致。Q4 无 nets，`HPWL=0` 只是共享 audit schema 的结构性兼容值，不是 Q4 优化指标或实验结论。

精确路线由实际代码生成 `upper_area=36` 下的候选 `(W,H)`，完整搜索整数声明域；SA 使用固定 `domain=9×9`、每个 seed 总评价预算 30000，由 4 次 restart 共享（各 7500），每 seed 60 秒和 `per_restart_linear` 温度计划。SA 从独立行布局开始，不使用精确解初始化。

## 阶段性结果证据

- Exact 原始 JSON：[result.json](../../outputs/q4/_runtime/v2/exact/result.json)；状态 `optimal/complete=true`，`W×H=4×6`，面积 24，deadspace 0，lower/upper=24/24，formal 与 audit 一致。
- 计时修复前文件 `result_pre_clock_fix.json` 仅作 superseded 追溯，不纳入正式汇总；正式 exact 证据仅使用 `result.json`。
- SA 10 seed 明细：[v2_sa_run_details.csv](../../outputs/q4/tables/v2_sa_run_details.csv)；全部 `success`、合法且 audit 匹配。面积 best=24、median=28、Tukey Q1=25、Q3=28、IQR=3；seed1108 独立得到面积24。
- 汇总与路线对比：[v2_sa_summary.csv](../../outputs/q4/tables/v2_sa_summary.csv)、[v2_route_comparison.csv](../../outputs/q4/tables/v2_route_comparison.csv)。
- 代表布局图：[v2_representative_layouts.svg](../../outputs/q4/figures/v2_representative_layouts.svg)（另有 PDF/PNG）。图中 exact 是主证据，SA1108 仅作匹配验证，并明确“不证明最优”。
- 模型细节与来源分层：[v2_model_report.md](../../outputs/q4/reports/v2_model_report.md)；协议：[v2_experiment_protocol.md](../../outputs/q4/reports/v2_experiment_protocol.md)。

Exact 面积 24 等于模块面积下界，因此在本轮相同形状/方向许可下没有更低连续平移面积；该下界推理和声明域边界应随 exact JSON 一起引用。代码、配置、命令和环境追溯字段保存在每个 JSON 及 CSV 中；Q4 定向测试为 19/19，未在此处写全量回归数字。

## 当前不能写入正式结论的内容

- 不能把 SA 的 best 或 seed1108 的面积匹配写成 SA 已证明最优；SA 是随机启发式，固定预算不等于完备搜索。
- 不能删除、排除或重跑任一注册 seed，也不能把 10 个 seed 的统计当作连续域或其他实例规模的结论。
- 不能把本轮 `VERIFIED` 扩大解释为 `FINAL`，不能把材料迁入 `outputs/q4/final/`。
- 不能把本轮结果外推到题面未确认的几何厚度、其他旋转许可、连续参数或 Q1--Q3 模型。

## V3 待办

1. 人工复核已确认几何来源边界、b1 厚度 2、协议和 exact 声明域；后续变化必须退回 `REVIEWING`。
2. 若需要扩展，增加连续域/几何敏感性和预算敏感性实验，并保持整数 exact 与 SA 的同一正式评价/独立 audit 口径。
3. 完成全量回归、论文图文审校和最终结果门槛后，才讨论 `FINAL` 与正式发布目录。
