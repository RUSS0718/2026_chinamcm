# Q1–Q4 V2 技术验收结论（REVIEWING）

- 验收日期：2026-08-09
- 执行基线：Git HEAD `5b4042aff79ac6e3134998adc93eb679895309c0`
- 验收性质：Agent 技术审查，不代替人工复核人标记 `VERIFIED` 或 `FINAL`
- 变更边界：未暂存、commit、push、清理无关改动或迁入任何 `outputs/qN/final/`

## 1. 已通过项

### 1.1 冻结边界与原始数据

- Q1/Q2 的代码、参数、既有报告和结果未在本轮修改或重跑；当前 `git diff` 在 `src/Q1`、`src/Q2`、`outputs/q1`、`outputs/q2` 和 `data/raw` 下为空。
- `data/raw` 基线为 12 个文件、2,418,936 bytes；阶段 0 原始字节 manifest SHA-256 为 `46139100a5104af97cdda3a104540426019b06ec5dbc48b346edb3b87f958bdd`。本轮未覆盖或原地清洗原始数据。
- Q1 V2 的既有状态为 `VERIFIED`，但范围只覆盖报告声明的 n100 开发证据；Q2 V2 仍为 `REVIEWING`。因此“冻结”不等于把 Q2 提升为已通过人工复核。

### 1.2 Q4 V2

- 几何口径已冻结：`b1` 横梁厚度 2；四模块面积分别为 12、6、2、4，总面积 24；旋转为 `0/90/180/270`，旋转后以外接框左下角归一；边界接触合法、正面积重叠非法。
- 精确路线在声明的整数平移域返回 `optimal/complete=true`，上下界均为 24，布局外接框为 `4×6`，deadspace 为 0，正式评价与独立 audit 一致。因为该布局达到模块面积和下界 24，在相同冻结几何和旋转许可下，连续平移也不可能得到更低面积。
- SA 使用预注册 seeds `1101–1110`，每 seed 总评价预算 30000、4 restarts、60 s；10/10 合法且 audit 一致。面积 best/median/Tukey IQR 为 `24/28/3`，其中 seed 1108 达到 24，但 SA 结果未被写成最优性证明。
- exact 与 SA 分路线验收；Q4 未称为 n100 测试。表格、原始 JSON、代表布局顶点、SVG/PDF/PNG 预览、模型报告和 `paper/q4/v2_handoff.md` 均可追溯。

### 1.3 Q3 V2 n100

- 三候选按 `Q3-BIN → Q3-LIN → Q3-CONT-R` 顺序，在统一 `_code_hash=a3971eefa77bc2cdaecd9fa0f59e85fc37668df57d6587d2217ec3f416ae8215` 下运行。首次 BIN 的旧 hash 运行因命令/环境追溯修复被完整保留为 superseded 证据，未纳入正式汇总。
- BIN：7 个阈值、70 cold、10 独立 final，共 80 条；`d_best=d_robust=selected_ratio=0.065625`。
- LIN：19 个阈值、190 cold、10 独立 final，共 200 条；`d_best=d_robust=selected_ratio=0.065`。
- CONT-R：7 个阈值、70 cold、6 个额外 warm、10 独立 final，共 86 条；`d_best=d_robust=selected_ratio=0.065625`。6 个 warm 未计入 cold 成功率或阈值边界。
- 正式三候选合计 366 条记录，全部 `formal_audit_match=true`，无 crash 或非空 error；所有 timeout/no_feasible 状态均保留。每个阈值确有 10 个 cold seeds，final 也确有重新运行的 10 个独立 seeds，不能概括为“1101–1110 总共只跑 10 次”。
- final 合法率均为 10/10。BIN、LIN、CONT-R 的 final HPWL best/median/Tukey IQR 分别为 `248215.5/258206.5/11615.0`、`248106.5/258206.5/12244.0`、`248106.5/258206.5/12244.0`。这些是固定 n100 开发证据，不构成跨规模优越性结论。
- 实际绝对命令、Python/平台/cwd/CPU、总墙钟、config hash、完整阈值/final 明细、最终布局模块表、统一比较表、模型报告和 `paper/q3/v2_handoff.md` 已形成闭环。

### 1.4 横向一致性与验证

- Q2–Q4 明确使用 `dead_space_ratio=deadspace/module_area`；辅助量 `rho=deadspace/area`。Q3 的正方形轮廓使用 `L(d)=sqrt(A_B(1+d))`。Q4 的 HPWL=0 只作为无 nets 时的共享 audit schema 兼容字段，不作为优化指标或结果结论。
- Q1–Q4 均以正式评价器和独立 audit 复核关键布局；旋转后锚点、边界接触、正面积重叠、面积与 HPWL 口径在各自适用范围内有明确说明。n100 坐标单位与 Q4 的 grid units 未混写。
- 主方案与对照关系成立：Q1/Q2 保留各自基线；Q3 有 BIN、LIN、CONT-R；Q4 有精确路线与 SA 路线。
- `D:\Anaconda\envs\CA-py310\python.exe -B -m unittest discover -s tests -p 'test*.py' -v` 实际通过 64/64。Q3 五张统一表重复生成后 SHA-256 不变；Q4 汇总脚本复建统计不变。测试仅作为代码证据，未被写成模型效果证明。

## 2. 未通过项与证据边界

1. **Q2 尚未完成人工复核。** 其 V2 报告仍为 `REVIEWING`，所以不能声称 Q1–Q4 全部已 VERIFIED。
2. **Q3 三候选顶层状态均为 timeout。** 其 final 布局合法且 audit 一致，但 timeout 不能写成最优性证明；低阈值 `no_feasible` 也不能写成数学不可行。
3. **Q3 仅是 n100 开发比较。** 未完成 n200 正式选型、n300 留出或预注册的预算/种子敏感性，不能据当前 HPWL 的细小差异宣布某候选普遍优越。
4. **Q4 几何仍需人工确认来源。** `b1` 横梁厚度 2 来自本轮用户确认，而不是题面 PDF 的独立文字标注；人工复核人应将该确认与题图一起核对。
5. **Q4 图为 V2 复核预览。** 已提供可编辑数据和 SVG/PDF/PNG，但完整敏感性分析、最终论文图排版和 V3 不确定性检验尚未执行。

## 3. 需要补做的最小任务

1. 人工复核 Q2 V2 既有材料，决定是否维持 `REVIEWING` 或提升阶段；Agent 不代替该决定。
2. 人工复核 Q3 的 30 个 final seed、三份最终 layout、366 条状态记录及首次 BIN superseded 链；若只验收 n100 V2 开发证据，无需重跑。
3. 人工复核 Q4 的题图几何、`b1` 厚度 2、exact 声明域和 4×6 零空白布局；若口径确认，无需重跑。
4. V3 再单独冻结 n200/n300、敏感性、预算和最终论文图协议；不得从本轮 V2 结果倒推或补写。

## 4. 技术结论与人工状态建议

- **论文方法章节水准：** Q3、Q4 已达到高水准的方法章节交接要求，公式、参数、入口、命令、环境、原始状态、汇总表和局限能够独立追溯。Q1 的既有 V2 仅在其声明范围内成立；Q2 因人工复核未完成，尚不能作为全链路已通过项。
- **建议人工复核：** 建议人工复核人将 Q3 的“n100 V2 开发证据包”和 Q4 V2 提交为 `VERIFIED` 候选；是否实际标记由复核人决定。Q2 不建议仅凭本轮冻结动作改变状态。
- **总体判定：** 本轮 Q3/Q4 技术验收通过，Q1/Q2 冻结边界通过；但 Q1–Q4 整体不能标记为全部 `VERIFIED` 或 `FINAL`。
