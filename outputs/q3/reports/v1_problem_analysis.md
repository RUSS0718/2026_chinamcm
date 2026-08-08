# Q3 V1 问题分析

- 状态：REVIEWING
- 负责人：钟江铭（P1/P2）、蔡乔夕（P0）
- 交叉复核：蔡乔夕
- Agent 技术实现：terra_worker（初始骨架）、Luna xhigh worker（缺陷修补）；Agent 技术验收：main Agent、独立 Luna xhigh reviewer
- 更新：2026-08-08
- 运行结果：未执行正式 V2 死区搜索；仅完成自动化测试和 n100 极低预算软件 smoke。任何“未找到”均不构成不可行证明。

## 目标、输入与输出

题面规定轮廓始终为正方形。对题面死区比例 `d=deadspace/module_area`，边长为 `L(d)=sqrt(A_B*(1+d))`；目标是在存在合法布局的意义下寻找最小 `d`，并在最终确认的轮廓下重新优化 HPWL。共享评价器另记录 `rho=deadspace/area=d/(1+d)`，但不得用 `rho` 替代题面要求报告的 `d`。输入继承 Q2 的模块、网络和 Terminal，另加死区搜索精度与稳健判定口径。输出包括 `d_best`、`d_robust`、每个相邻更小死区的尝试状态、最终轮廓上的 HPWL、布局和完整运行元数据。

## 约束、依赖与最终结果

- 显式：矩形模块不重叠且在候选轮廓内；`area=L(d)^2`，`module_area=A_B`，`deadspace=area-module_area`，题面 `d=deadspace/module_area`，另有 `rho=deadspace/area`。
- 隐式：内层启发式失败只说明该预算/种子下未找到；连续死区搜索需记录精度和判定规则；最终 HPWL 只能在已确认的可行轮廓上比较。
- 依赖 Q2 的数据、Terminal、HPWL、固定轮廓及合法性口径；对 Q2 任何尺寸/引脚变更均需回退复核。
- 最终应报告最小已找到可行值、稳健值、相邻更小值的状态以及最终 HPWL；正式数值仍待 V2 预注册实验。

## 候选比较与选择

| 编号 | 路线与作用 | 优点 | 风险/数据可行性 | 回退条件 |
|---|---|---|---|---|
| Q3-LIN (P0) | 固定步长逐级缩小死区 | 透明、失败位置易审计 | 三实例数据足够；精度与运行次数线性相关 | 始终保留 |
| Q3-BIN (P1) | 二分死区 + 独立多起点内层搜索 | 利用真实可行域的单调扩张减少阈值试验 | 有限预算下“找到解”可能非单调，不能把失败当不可行证明 | P2 过度依赖 warm start 时使用 |
| Q3-CONT-R (P2) | P1 + 连续压缩 warm start + 稳健边界报告 | 可复用相邻可行布局并减少搜索消耗 | warm start 可能造成路径依赖，必须保留冷启动确认 | 将连续压缩仅作辅助初始解，主报告回退 P1 |

## 算法与开关

1. 固定轮廓长宽比、死区单位和容差，定义可行判定为独立评价器合法。
2. P0 逐级搜索；P1 在区间中点用相互独立的多起点内层运行确认或拒绝候选阈值。
3. P2 仅在 `continuous_compression=on` 时从较大死区解连续压缩 warm start；仍保留冷启动确认。
4. 对最终可行轮廓以冻结预算重新优化 HPWL，不能把阈值搜索中的偶然最低 HPWL 当最终值。

## 风险与 V2 证据

2026-08-08 已对照正式题面第 1、3 页确认正方形轮廓公式、Q3 最小死区目标及更新 HPWL 的要求。数学上的“存在合法布局”随 `d` 增加单调，但启发式在有限预算下是否找到布局可能不单调；舍入容差和预算依赖是核心风险。V2 需给出二分终止、`d_best/d_robust` 定义、每阈值种子与预算、冷启动对照、最终轮廓复优化命令和完整尝试表。

## 开发骨架验收记录

2026-08-08 完成以下软件行为验收，状态仍为 `REVIEWING`：

- `Q3-LIN` 使用固定步长递减；`Q3-BIN` 使用 cold-only 二分；`Q3-CONT-R` 使用二分外层，并仅在 `continuous_compression=on` 时增加 warm start。
- warm attempt 只作为辅助初始解；阈值决策、`d_best`、`d_robust`、`found_legal` 和阈值最佳 HPWL 均只使用 cold attempts。
- `crash` 运行保留在明细中，但不计入 cold 合法尝试、成功率或边界判定；crash 的 final attempt 也不得成为最终布局候选。`timeout` 的合法 cold attempt 仍按其实际合法性计入。
- CONT-R 仅在已接受阈值有合法布局时，将该阈值最佳合法 warm/cold 状态传播到下一次更低阈值的额外 warm attempt；后续 cold seeds 始终独立运行，warm 结果不改变边界或最终复优化判定。
- `Q3-CONT-R + continuous_compression=off` 与相同内层配置的 `Q3-BIN` 退化行为一致；不支持 warm state 的 `Q2-SP` 不允许开启连续压缩。
- 最终轮廓使用独立 final seeds 重新优化，最佳合法布局写入 JSON，并记录 `layout_path`、正式评价、独立审计、配置哈希和代码哈希。
- 默认 `run_id` 纳入配置哈希，不同预算、种子、精度或开关不会使用同一默认输出名。

实际验证：

| 命令 | 结果 | 证据边界 |
|---|---|---|
| Python 3.10.20 `-B -m unittest tests.test_q3 -v` | 25 项 Q3 测试，`OK` | 只证明搜索控制流、失败语义、布局落盘、进程并发和可复算接口 |
| Python 3.10.20 `-B -m unittest discover -s tests -v` | 44 项全量测试，`OK` | 未发现 Q1/Q2/共享评价器回归 |
| `python -B -m src.Q3 --help` 与 `python -B src/q3.py --help` | 均返回 0 | 两个入口可调用 |
| `python -B -m src.Q3 --instance n100 --candidate Q3-CONT-R ... --max-evaluations 10` | 本地 `tmp/` smoke 返回 `success`，记录 1 条 warm、2 条 cold 和 1 个最终布局 | 极低预算开发探针，不是 V2 边界、模型效果或正式结果证据 |

旧 n100 数字仅为整合前代码哈希下的历史记录，详见 [`v2_n100_results.md`](v2_n100_results.md)，不得作为当前代码的验收、Q4 输入或最终模型优劣结论。BIN、LIN、CONT-R 的整合后全量重跑待执行；n200 正式选型也尚未执行。
