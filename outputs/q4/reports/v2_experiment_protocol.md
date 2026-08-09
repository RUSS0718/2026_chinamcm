# Q4 V2 正式实验协议（VERIFIED）

## 1. 状态、范围与解锁条件

- 阶段状态：`VERIFIED`。2026-08-09 人工复核接受几何来源、exact 声明域和运行证据边界；本协议不是 `FINAL`，发生影响性变更时退回 `REVIEWING`。
- 本协议针对题面给出的四个异形模块 `b1`、`b2`、`b3`、`b4`；本协议绝不将该问题称作 `n100`，也不把四模块实验扩展为其他规模实例。
- 本文件只登记实验定义、命令和证据字段；当前不包含运行结果。所有实验输出必须写入 `outputs/q4/_runtime/v2/`，不得写入 `outputs/q4/final/`。
- SA 正式批次须在精确路线结果由主 Agent 验收后另行解锁；在此之前不得运行 seeds 1101--1110 正式批次。

## 2. 已冻结的几何与问题定义

用户已确认 `b1` 顶部横梁厚度为 2。各模块以自身旋转归一后的外接框左下角为锚点，局部顶点按同一方向、无重复终点记录如下：

| 模块 | 局部顶点（整数坐标） | 面积 |
|---|---|---:|
| `b1` | `[(1,0),(3,0),(3,2),(4,2),(4,4),(0,4),(0,2),(1,2)]` | 12 |
| `b2` | `[(0,0),(2,0),(2,2),(1,2),(1,4),(0,4)]` | 6 |
| `b3` | `[(0,0),(2,0),(2,1),(0,1)]` | 2 |
| `b4` | `[(0,0),(1,0),(1,4),(0,4)]` | 4 |

模块面积总和为 `12+6+2+4=24`。允许旋转角为 `0°/90°/180°/270°`；每次旋转后重新平移，使局部外接框的 `min-x=min-y=0`。平移变量限定为步长为 1 的整数平移网格。

布局语义是模块锚点加旋转后的局部顶点。模块边界接触（包括边接触和点接触）合法；任意两个模块正面积重叠非法。评价器必须同时检查外接框、面积、deadspace 和合法性；正式结果还必须调用独立 `src/_internal/audit.py` 的 `audit_layout`，并记录 `formal_audit_match`。

指标口径固定为 `dead_space_ratio=deadspace/module_area`，`rho=deadspace/A_box`，其中 `A_box=W*H`。Q4 不定义 nets，`HPWL=0` 仅是共享 audit schema 的结构性兼容字段，不是 Q4 优化指标或实验结论。

## 3. 精确路线（integer-grid exact）

### 3.1 注册配置

- `upper_area=36`；`time_limit=300` 秒。
- `grid_step=1`，旋转集合为 `[0, 90, 180, 270]`，搜索域为整数平移网格。
- 候选容器 `(W,H)` 不在协议中手写；由 `src.Q4.search._container_sizes(instance, upper_area)` 根据实际模块外接框和 `upper_area` 生成。输出必须记录实际 `width_range`、`height_range`、`containers_total` 与 `containers_checked`。
- 固定真实入口（不得改写为其他脚本）：

```powershell
D:\Anaconda\envs\CA-py310\python.exe -B -m src.Q4 exact --upper-area 36 --time-limit 300 --output outputs/q4/_runtime/v2/exact/result.json
```

### 3.2 状态与界语义

- `status=optimal` 且 `complete=true`：候选容器按实际代码域完整排除/验证，并找到当前域最小面积布局；仅此组合可称为“整数声明域最优”。
- `status=timeout` 或 `complete=false`：只报告当前 incumbent（若存在）、已排除范围和界；不得称最优。无 incumbent 时 `upper_bound` 必须为 `None`，不得用注册的 `upper_area` 冒充可行上界。
- `lower_bound` 表示模块面积下界或已完整排除容器后的下一个未排除面积，具体以结果字段和 `containers_checked` 为准；`upper_bound` 仅在存在已验证合法 incumbent 时表示其面积。
- `status=no_feasible` 且 `complete=true`：声明代码域已穷尽但没有可行布局；不得伪造 `upper_bound`。
- 若完整精确结果的面积为 24，则模块面积下界证明了连续平移域的全局最优（整数解同时达到不可低于的面积下界）。若面积大于 24，结论只限于本协议的整数声明域，不得扩展为连续域全局最优。

## 4. SA 路线（同一问题定义）

SA 只有在第 3 节精确结果经主 Agent 验收后解锁。预注册且顺序运行的种子为：`1101, 1102, 1103, 1104, 1105, 1106, 1107, 1108, 1109, 1110`。

- `max_evaluations=30000`、`time_limit=60` 秒、`restarts=4`、`domain=(9,9)`。
- 温度计划为 `per_restart_linear`；每个 restart 独立重置进度并按确定性预算分配。
- 初始布局为独立合法行布局；不得使用精确解或精确解的变体初始化 SA。
- 邻域仅在同一整数平移网格中随机改变模块平移和旋转；每个候选必须经正式评价器判定合法；每个种子的最终保存布局再由独立 audit 复核。
- 单种子命令模板（`SEED` 替换为预注册种子）及输出路径：

```powershell
D:\Anaconda\envs\CA-py310\python.exe -B -m src.Q4 sa --seed SEED --max-evaluations 30000 --time-limit 60 --restarts 4 --domain-width 9 --domain-height 9 --output outputs/q4/_runtime/v2/sa/seed_SEED.json
```

每个种子无论 `success`、`timeout`、`no_feasible` 或 crash，都必须保留可追溯 JSON（crash 另保存标准错误和退出码），不得静默丢弃失败批次。

## 5. 结果证据与汇总

每个 exact/SA JSON 至少记录：`status`、`complete`（如适用）、`layout`、完整 `formal` 指标、完整 `audit` 指标、`formal_audit_match`、`runtime`、`evaluations`/`placements_tested`（如适用）、界字段、声明域、实际 `config` 及 `config_hash`、代码逐文件 manifest 与聚合 `code_hash`、实际 `command` 和环境（含 cwd、Python、CPU count）。

SA 汇总表必须记录：合法率、best area、median area、IQR、runtime、evaluations，以及相对精确 incumbent/声明域结果的 `gap`。汇总不得把 timeout、crash 或 no-feasible 当作成功样本，也不得用缺失结果补齐统计量。

本协议及其运行输出不会自行迁入 `outputs/q4/final/`，也不会自行将阶段提升为 `FINAL`；当前 `VERIFIED` 来自 2026-08-09 的人工复核批准。
