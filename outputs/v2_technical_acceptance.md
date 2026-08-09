# Q1–Q4 V2 技术验收结论（VERIFIED）

- 验收日期：2026-08-09
- 初次执行基线：Git HEAD `5b4042aff79ac6e3134998adc93eb679895309c0`
- 本次复核基线：Git HEAD `4ed8e1e8dbef13cdb1ef7f08ba26984179e12ea9`；未重跑 Q2/Q3 n100 或 Q4 正式实验
- 验收性质：Agent 技术审查；2026-08-09 指定人工复核人接受证据边界并批准 Q2/Q3/Q4 V2 为 `VERIFIED`
- 变更边界：未暂存、commit、push、清理无关改动或迁入任何 `outputs/qN/final/`

## 1. 已通过项

### 1.1 冻结边界与原始数据

- Q1/Q2 的参数、既有报告和结果未在本轮修改或重跑；复核开始前工作区干净，本轮只更新本验收记录与协作状态表。Q2 的 70 条 V2 记录统一绑定运行时代码哈希 `5182e532feca7ba4337692b112b06f181d6f79ee85596eacf83c9109b14fb709`。
- 当前 HEAD 的 Q2 manifest 哈希为 `8486b3cd4164489a9bede5e71db248a389ba0f5ef3dc616ed4a75e4fb95aad5a`。漂移来自 Q3 接入 warm start 时对 `src/Q2/common.py` 与 `src/Q2/p1_p2.py` 的扩展：Q2 默认调用仍传入 `initial_state=None`，新增 `best_state` 不进入 Q2 CLI 序列化。64/64 单元测试通过支持“默认路径语义未变”，但这不等于当前 HEAD 已重新取得同哈希 n100 运行证据。
- `data/raw` 基线为 12 个文件、2,418,936 bytes；阶段 0 原始字节 manifest SHA-256 为 `46139100a5104af97cdda3a104540426019b06ec5dbc48b346edb3b87f958bdd`。本轮未覆盖或原地清洗原始数据。
- Q1 V2 的既有状态为 `VERIFIED`；本次人工复核接受 Q2 的 `5182e532…` 历史运行快照边界，并批准 Q2/Q3/Q4 V2 为 `VERIFIED`。所有状态只覆盖各报告声明的 V2 范围。

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

## 2. VERIFIED 证据边界

1. **Q2 的 VERIFIED 绑定历史运行快照。** 人工复核明确接受代码哈希 `5182e532…` 的 50 条主组、20 条压力记录和对应 manifest；该状态不表示当前 HEAD 已取得同哈希 n100 运行证据。
2. **Q3 三候选顶层状态均为 timeout。** 其 final 布局合法且 audit 一致，但 timeout 不能写成最优性证明；低阈值 `no_feasible` 也不能写成数学不可行。
3. **Q3 仅是 n100 开发比较。** 未完成 n200 正式选型、n300 留出或预注册的预算/种子敏感性，不能据当前 HPWL 的细小差异宣布某候选普遍优越。
4. **Q4 几何来源边界已被人工接受。** `b1` 横梁厚度 2 来自用户确认，而不是题面 PDF 的独立文字标注；本次 VERIFIED 绑定该确认，不得外推为题面独立文字证据。
5. **Q4 图为 V2 复核预览。** 已提供可编辑数据和 SVG/PDF/PNG，但完整敏感性分析、最终论文图排版和 V3 不确定性检验尚未执行。

## 3. 后续阶段任务

1. 如要求 Q2 当前 HEAD 同哈希复现，另行退回 `REVIEWING` 并重跑受影响的 n100 组；本次 VERIFIED 不要求该重跑。
2. V3 再单独冻结 n200/n300、敏感性、预算和最终论文图协议；不得从本轮 V2 结果倒推或补写。
3. 任何公式、参数、代码、数据、几何口径、关键数字或结论变化，都必须说明影响范围并将受影响阶段退回 `REVIEWING`。

## 4. 技术结论与人工状态建议

- **人工复核结论：** 2026-08-09，指定人工复核人接受 Q2 历史快照、Q3 n100 开发证据包以及 Q4 几何来源与 exact/SA 证据边界，批准 Q2/Q3/Q4 V2 为 `VERIFIED`。
- **总体判定：** Q1-Q4 V2 均为 `VERIFIED`；该判定不覆盖 V3、Q2/Q3 n200/n300、最终论文结论或 `FINAL`。
