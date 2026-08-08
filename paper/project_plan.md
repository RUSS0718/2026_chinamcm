# V1 项目技术计划

- 状态：REVIEWING；项目成员：钟江铭、蔡乔夕；Agent 技术实现：terra_worker；Agent 技术验收：main Agent；更新：2026-08-08。
- 已确认：第 0 轮记录三实例解析计数和共享几何/指标测试；尚未运行任一优化候选。
- 本次未执行：不修改 `data/raw/`、优化器、正式结果表或 Git commit/push。

## 依赖与组件

`data/raw -> 解析冻结/第0轮评价 -> Q1(矩形 packing) -> Q2(正方形固定轮廓+HPWL) -> Q3(死区阈值+最终 HPWL)`。Q4 复用 Q1 的搜索框架，但必须以第 0 轮真实正交多边形几何替换矩形碰撞/面积口径，并由 ENUM/CP 独立核验。共享组件是解析器、正式评价器、独立审计、统一结果格式和 B*-Tree/contour（Q1-Q3）；Q1/Q2 的 P0 家族使用 Sequence Pair，Q4 专属真实正交多边形与 ENUM/CP。后问改变数据、参数、公式或关键数字时，受影响前问退回 REVIEWING 并重跑。

## 接口与数据权威

唯一原始事实为 `data/raw/`；首个解析器须经另一人独立审计后冻结。`.blocks/.nets/.pl` 的审计哈希以 LF 规范字节计算，并通过 `.gitattributes` 禁止后续 Git 换行转换；程序不得覆盖或原地清洗原始附件。统一输入为 `instance, problem, candidate, config, seed, budget`，统一输出为模块坐标/方向、`status,runtime,evaluations,layout_path,log_path`。正式指标只能由共享评价器重算，独立审计脚本抽查；Terminal 是 `.pl` 绝对坐标，不是 HardBlock 轮廓约束。

## 指标口径

令布局包围盒或固定轮廓边长为 `W,H`，则 `area=W*H`，`module_area` 为模块真实多边形面积之和，`deadspace=area-module_area`，`aspect_ratio=max(W,H)/min(W,H)`。题面参数 `dead_space_ratio=deadspace/module_area`；内部同时记录 `rho=deadspace/area=dead_space_ratio/(1+dead_space_ratio)`，但 Q2/Q3 的轮廓公式和报告均使用题面的 `dead_space_ratio`。一个网络的 `HPWL=(max x-min x)+(max y-min y)`，总 HPWL 为所有网络之和，模块引脚为中心且 Terminal 使用其绝对坐标。正面积相交非法，边界接触合法。Q4 的模块面积与碰撞均基于真实正交多边形。

## 候选、预注册与失败语义

P0 是独立基线，P1 是稳健主干，P2 是可逐一关闭的创新组件：`directed_moves,state_dedup,hypergraph_init,adaptive_constraints,continuous_compression`。Q1 的 P0 家族冻结为 `Q1-G`（确定性 shelf/bottom-left 下界基准）和 `Q1-SP`（Sequence Pair + 经典 SA 独立随机基线），两者均保留，不再二选一。n100 用种子 1101-1110 开发，n200 用 2201-2220 冻结选型/消融，n300 用 3301-3330 仅留出；记录等墙钟和等评价次数预算，正式运行还须冻结机器、线程、软件与 RNG。状态只能为 `success,no_feasible,timeout,crash`，失败运行保留。Q3 的数学可行域随死区增加单调扩张，但有限预算启发式“找到解”的事件不保证单调；未找到不是不可行证明。Q4 精确路线未 `optimal` 只能报告当前最好可行布局或上界，不能写最优。

## V1 至 V3 验收

V1：各报告说明目标、接口、候选、开关与回退。进入某问 n100 开发前，须完成第 0 轮、该问 V1 和该问专属几何/数据口径复核；参数、重启次数、墙钟/评价次数预算、机器、线程和 RNG 在 n100 开发结束、n200 正式比较前冻结。Q4 的 `b1` 完整顶点只阻塞 Q4 V2，不阻塞 Q1 n100 开发。V3：完整明细/汇总表、独立审计、匹配的比较或敏感性检验，以及论文数字追溯。每问选型至少保留 P0；P2 仅在稳定收益且不降低合法率时采用，否则回退 P1。

## 本阶段验证记录

主 Agent 使用 bundled Python 实际执行 `validate.py paper/diagrams/v1_technical_route.drawio --score`，结果为 `0 error(s), 0 warning(s)`。随后使用 `D:\Program Files\draw.io\draw.io.exe` 31.1.8 导出预览 PNG，完成两轮视觉检查并修正 `第0轮 -> Q4` 的误导性路由；正式导出 `v1_technical_route.drawio.png`（嵌入 XML）和 `v1_technical_route.svg`，最终 PNG 已完成像素检查，无标签裁切、节点重叠或错误连线。2026-08-08 又实际执行 6 项第 0 轮基础测试和审计入口，纠正 `area/module_area` 语义，确认 Q1/Q3 题面口径，并复现三实例规范哈希与解析计数。同日完成 Q3 开发骨架修补；当前 25 项 Q3 专项测试和 44 项全量测试均输出 `OK`，真实入口可调用。Q3 代码/测试已验收，但整合后 BIN、LIN、CONT-R 的 n100 结果待全量重跑，状态为 `REVIEWING`；旧 n100 结果不构成 Q4 输入、n200 正式选型或最终结论。

## 协作确认与资料边界

- 已确认唯一总集成人为蔡乔夕，负责跨问题口径、目录、依赖和最终运行顺序一致性；不改变各题既定负责人。
- Q4 图 3 中 `b1` 竖向总尺寸冻结为 4，与 `b2`、`b4` 的总高度一致；V2 仍需将完整局部顶点写入代码/公式并复核，不凭总高度推定未明确的局部厚度或顶点。
- 选型背景参考本地题面 `data/raw/B题 VLSI布图规划设计.pdf` 与 B*-Tree/Fast-SA 原论文；论文中的历史实验数字不作为本项目候选优劣证据。
