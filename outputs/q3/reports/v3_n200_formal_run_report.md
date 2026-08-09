# Q3 V3 n200 正式运行报告

- 阶段：`REVIEWING`
- 更新时间：2026-08-09
- 范围：Q3 V3 `n200`，`Q3-BIN → Q3-LIN → Q3-CONT-R`
- 冻结配置：内层 `Q2-HG`，`workers=4`，`30000 evaluations / 60 s / 4 restarts`
- 正式结果根目录：`outputs/q3/_runtime/v3_n200/`

## 1. 执行状态

三条路线均已生成完整 `result.json`、attempts 表、config snapshot 和实时进度流；每条路线均有一个 `run_complete`，无 `run_error`，无缺失 threshold/final seed。

运行过程中承载正式命令的外层等待达到 4 小时上限，曾在 Q3-CONT-R 的 `d=0.0703125` 第 4 个冷启动处终止。Q3-BIN、Q3-LIN 的完整结果未受影响；随后仅按同一冻结命令重跑未完成的 Q3-CONT-R，未改变 workers、预算、种子、候选顺序或参数。

## 2. 结果汇总

| 路线 | threshold 点数 | threshold cold | warm（不计入 cold） | `d_best` | `d_robust` | final | final 合法/审计率 | final HPWL 中位数 | IQR | P90 | final 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Q3-BIN | 7 | 140 | 0 | 0.075 | 0.075 | 20 | 20/20 = 1.000 | 520098.75 | 5050.875 | 522641.75 | 20 timeout |
| Q3-LIN | 31 | 620 | 0 | 0.075 | 0.075 | 20 | 20/20 = 1.000 | 520098.75 | 5050.875 | 522641.75 | 20 timeout |
| Q3-CONT-R | 7 | 140 | 6 | 0.075 | 0.075 | 20 | 20/20 = 1.000 | 520098.75 | 5050.875 | 522641.75 | 20 timeout |

阈值搜索中，三条路线在 `d < 0.075` 的已测试点均未达到 robust 判定；`d=0.075` 达到 20/20 cold 成功率 1.0。Q3-LIN 的完整 0.005 网格还显示更高比例均为 robust，但最小 robust 比例仍为 0.075。

## 3. 机械决策与解释边界

机械汇总的 `d_robust_priority` 为真，三条路线的 `d_robust`、final 合法/审计率和 final HPWL 中位数完全相同；按注册路线优先级机械排序为 `Q3-BIN`、`Q3-LIN`、`Q3-CONT-R`，因此机械选择为 `Q3-BIN`。这只是并列时的预注册优先级，不构成 Q3-BIN 相对另外两条路线的性能优越性证明。

final 记录全部为 `timeout`，但 20/20 记录均通过合法性和 formal audit；`timeout` 表示达到本轮 60 秒预算，不等于不可行，也不等于最终最优性证明。

## 4. 完整性与审计证据

- Q3-BIN：160 attempts 行 = 7×20 threshold + 20 final。
- Q3-LIN：640 attempts 行 = 31×20 threshold + 20 final。
- Q3-CONT-R：166 attempts 行 = 6 warm + 7×20 cold threshold + 20 final。
- 三条路线的 `result.json` 与 `v3_freeze.json` 的 code/config/data hash 均一致。
- 三条路线均无缺失 seed、无 crash、无实时流错误事件。
- 原始输入 `data/raw/附件/n200.*` 未修改。

正式 `src.v3 summary` 校验器当前把 CONT-R 同一阈值的 warm/cold 同 seed 误判为重复；这是审计键缺少 `mode` 的校验器问题，不是结果重复。`outputs/q3/tables/v3_n200_summary.json` 使用等价的临时审计键（加入 `mode`）生成，并在 `validation_note` 中记录了该事实。该问题应在后续单独修复并补充测试，不能把当前临时汇总视为已完成代码修复。

## 5. 证据文件

- 机器汇总：`outputs/q3/tables/v3_n200_summary.json`
- Q3-BIN：`outputs/q3/_runtime/v3_n200/runtime/n200/v3_n200_q3-bin/result.json`
- Q3-LIN：`outputs/q3/_runtime/v3_n200/runtime/n200/v3_n200_q3-lin/result.json`
- Q3-CONT-R：`outputs/q3/_runtime/v3_n200/runtime/n200/v3_n200_q3-cont-r/result.json`
- 实时查看脚本：`tmp/q3_v3_live_progress/view.ps1`（本地忽略，不纳入阶段提交）

## 6. 未执行与待复核

- 未创建 commit，未 push，未迁入 `outputs/q3/final/`。
- `workers=4` 仍是按 Q2 经验冻结的运行配置；本次没有与 `workers=5` 做同预算对照，不能据此宣称 4 优于 5。
- 本报告和机器汇总均保持 `REVIEWING`，需要建模负责人和复核人确认后，才能决定是否进入 `VERIFIED` 或 `FINAL`。
