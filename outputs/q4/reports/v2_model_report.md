# Q4 V2 模型与运行证据（REVIEWING）

状态：`REVIEWING`。本文是可复查的 V2 技术材料，不是人工 `VERIFIED` 或 `FINAL`，也不是论文最终结论。实验定义见[正式协议](v2_experiment_protocol.md)；原始 JSON、表格、图和生成脚本均保留在仓库中。

## 1. 范围与结论边界

本轮只处理题面四个异形模块 `b1`--`b4`，不称为 `n100`。精确路线在协议声明的整数平移网格上返回 `status=optimal, complete=true`，布局外接框为 `W=4,H=6`，面积 24，deadspace 0；正式评价器与独立 audit 一致。SA 10 个预注册种子均完成，seed 1108 得到面积 24，但 SA 结果仅是独立匹配验证，不构成最优性证明。

## 2. 几何来源分层

1. **用户确认（当前冻结事实）**：`b1` 顶部横梁厚度为 2；本轮采用的完整局部顶点及面积为：

   | 模块 | 局部顶点 | 面积 |
   |---|---|---:|
   | `b1` | `[(1,0),(3,0),(3,2),(4,2),(4,4),(0,4),(0,2),(1,2)]` | 12 |
   | `b2` | `[(0,0),(2,0),(2,2),(1,2),(1,4),(0,4)]` | 6 |
   | `b3` | `[(0,0),(2,0),(2,1),(0,1)]` | 2 |
   | `b4` | `[(0,0),(1,0),(1,4),(0,4)]` | 4 |

   总模块面积为 `24`。
2. **题面直接证据**：题面图给出四模块及其外接尺寸/相对形状；原图对 `b1` 局部横梁厚度没有独立的文字标注。此前仅凭题图不能把竖向总高度 4 推成横梁厚度；本轮的厚度 2 来自上述用户确认。
3. **仓库共享约定**：[V2 协议](v2_experiment_protocol.md)冻结旋转 `0/90/180/270`、旋转后外接框左下角锚点、整数步长 1、接触合法和正面积重叠非法。
4. **实现与输出**：`src/Q4/geometry.py`、`src/Q4/model.py` 负责几何/正式评价，`src/_internal/audit.py` 负责独立复核；运行 JSON 的 `code_manifest`/`code_hash` 是当次实现证据。绘图顶点 CSV 仅用于代表布局展示，并保留原始锚点及外接框归一偏移。

## 3. 变量、公式与约束

对模块 `i`，布局变量为整数锚点 `(x_i,y_i)` 与方向 `r_i∈{0,90,180,270}`。旋转后多边形平移到局部外接框 `min-x=min-y=0`，平移网格步长为 1。边界接触（点或边）合法；任意两个模块的正面积交集必须为 0；容器搜索时所有模块必须落入候选 `(W,H)`。

对局部顶点按鞋带公式计算面积：

\[
A_i=\frac12\left|\sum_k(x_k y_{k+1}-x_{k+1}y_k)\right|,\quad \sum_iA_i=24.
\]

布局外接框宽高为 `W,H`，评价面积、空白面积和比例为：

\[
A_{box}=W H,\qquad deadspace=A_{box}-24,\qquad \rho=deadspace/A_{box}.
\]

同时记录 `dead_space_ratio=deadspace/module_area`。Q4 不定义 nets；JSON/audit 中的 `HPWL=0` 只是共享 audit schema 的结构性兼容值，不是 Q4 优化指标，也不构成实验结论。

正式评价器用正交多边形扫描线/Fraction 交面积判定正面积重叠；精确搜索另用单位网格 cell 占用，并对每个模块每个方向校验 `len(cells)==polygon_area`。每个最终布局均记录 `formal_audit_match`。

## 4. 算法与声明域

### 4.1 精确路线

真实入口为：

```powershell
D:\Anaconda\envs\CA-py310\python.exe -B -m src.Q4 exact --upper-area 36 --time-limit 300 --output outputs/q4/_runtime/v2/exact/result.json
```

代码由实际 `_container_sizes(instance, upper_area)` 生成候选容器，共 14 个，声明域宽高范围均为 `[4,9]`，本次在首个容器完成验证（`containers_checked=1`），测试 741 个候选放置。只有 `complete=true` 且 `status=optimal` 才能称为整数声明域最优。本次结果的 `lower_bound=upper_bound=24`，并且独立 audit 合法且一致。

模块面积和给出任何连续平移布局的下界 `A_box≥24`。本次完整精确结果达到 24，因此在同一形状/方向许可下，连续平移也没有更低面积；这只依赖面积下界与本次达到下界的证据，不把面积大于 24 的整数结果外推为连续全局最优。

### 4.2 SA 路线

协议固定 `seed=1101..1110`、`max_evaluations=30000`、`time_limit=60s`、`restarts=4`、`domain=9×9`、`per_restart_linear`。每个 restart 从独立合法行布局开始，不使用精确结果初始化；邻域随机改变整数平移/方向，正式评价器判定候选合法，最终保存布局由独立 audit 复核。运行命令和每 seed 输出路径见[协议](v2_experiment_protocol.md)及[运行明细表](../tables/v2_sa_run_details.csv)。

## 5. 运行结果

### 5.1 Exact

原始证据：[exact/result.json](../_runtime/v2/exact/result.json)；表格：[v2_exact_result.csv](../tables/v2_exact_result.csv)。

| status | complete | area | W×H | deadspace | lower/upper | legal | audit match | runtime(s) | placements |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| optimal | true | 24 | 4×6 | 0 | 24/24 | true | true | 0.0060143 | 741 |

代表布局锚点为 `b1=(0,2,r0)`、`b2=(0,0,r0)`、`b3=(2,0,r90)`、`b4=(3,0,r0)`。

### 5.2 SA（全 10 个 seed，不排除）

运行明细：[v2_sa_run_details.csv](../tables/v2_sa_run_details.csv)。每个 seed 均为 `success`、`legal=true`、`formal_audit_match=true`、`evaluations=30000`，面积依次为：

| seed | area | W×H | deadspace | gap=(area−24)/24 | runtime(s) |
|---:|---:|---:|---:|---:|---:|
| 1101 | 28 | 7×4 | 4 | 0.1666667 | 20.2278460 |
| 1102 | 25 | 5×5 | 1 | 0.0416667 | 20.5204269 |
| 1103 | 28 | 4×7 | 4 | 0.1666667 | 20.2930709 |
| 1104 | 28 | 7×4 | 4 | 0.1666667 | 20.4809050 |
| 1105 | 25 | 5×5 | 1 | 0.0416667 | 20.4998117 |
| 1106 | 28 | 7×4 | 4 | 0.1666667 | 20.3460531 |
| 1107 | 28 | 4×7 | 4 | 0.1666667 | 20.4050908 |
| 1108 | 24 | 6×4 | 0 | 0 | 20.4969194 |
| 1109 | 25 | 5×5 | 1 | 0.0416667 | 20.3088204 |
| 1110 | 28 | 7×4 | 4 | 0.1666667 | 20.5922901 |

统计表：[v2_sa_summary.csv](../tables/v2_sa_summary.csv)。10 个 seed 全部纳入；Tukey 四分位数采用排序后上下半样本中位数：best area 24、median 28、Q1 25、Q3 28、IQR 3；best gap 0、median gap 0.1666667、gap IQR 0.125；runtime median 20.4429979s、IQR 0.1909913s；legal rate 和 audit-match rate 均为 1.0。

## 6. 追溯、环境与测试证据

- Exact 与 10 个 SA JSON 的 `code_hash` 全部一致：`5f9b461b33e142f399a717c9fab309c0667da57a09af8d86efec389274550b02`；SA 每 seed 的 `config_hash` 保留在运行明细表，exact `config_hash` 为 `ca80f5194d869afed11bf35b4457d347690c684f336ae009ee258190d2661dea`。
- 运行环境字段来自 JSON：Windows 10 build `10.0.26200`，Python `3.10.20`，CPU count `16`；复现绘图依赖固定为 `matplotlib==3.10.9`（见仓库 `requirements.txt`）。每行保留实际 `command`、`layout_path`、`code_hash`、`config_hash`、`error` 和（若存在）`exit_code` 字段。
- `outputs/q4/_runtime/v2/exact/result_pre_clock_fix.json` 是计时修复前的 superseded 追溯副本，不纳入正式汇总；正式 exact 证据仅使用 `result.json`。
- 路线比较：[v2_route_comparison.csv](../tables/v2_route_comparison.csv)；代表布局顶点：[v2_representative_layout_vertices.csv](../tables/v2_representative_layout_vertices.csv)；图：[v2_representative_layouts.svg](../figures/v2_representative_layouts.svg)、[PDF](../figures/v2_representative_layouts.pdf)、[PNG](../figures/v2_representative_layouts.png)。
- Q4 定向测试命令 `D:\Anaconda\envs\CA-py310\python.exe -B -m unittest tests.test_q4 -v`：19/19 OK。这里仅记录 Q4 定向代码证据，不写全量回归最终数字。
- 失败清单为空：10 个 SA JSON 均存在且为 success；无 timeout、crash、no_feasible。此结论来自构建脚本的 fail-closed 校验，不是对未生成文件的推断。

## 7. 局限与 V3 待办

本轮 exact 证明的是声明的整数平移网格、四方向、实际候选容器域；连续域结论仅因面积 24 下界被达到而成立，不能推广为其他几何或其他旋转许可。SA 是固定预算的随机启发式，不提供最优性证明，seed 1108 的面积匹配不能替代 exact。当前没有敏感性分析、跨参数预算分析、连续域搜索或正式论文级不确定性分析；V3 需先由人工复核冻结几何/协议，再决定是否开展这些扩展。

阶段仍为 `REVIEWING`，本报告不标记 `VERIFIED`/`FINAL`，也不迁入 `outputs/q4/final/`。
