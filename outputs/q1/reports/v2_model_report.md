# Q1 V2 数据处理与模型报告

- 状态：VERIFIED
- 问题：Q1
- 负责人：钟江铭（P1/P2）
- 交叉复核：蔡乔夕
- 更新：2026-08-08
- 范围：包含既有 P1/P2 n100 开发记录，以及 Q1-G、Q1-SP、Q1-BT、Q1-BT-D 的独立 n100 批次；不包含 n200 正式选型、n300 留出，P2 消融留待 V3。

## 1. 数据处理与口径

Q1 只读取 `data/raw/附件/*.blocks`。本阶段不使用 `.nets` 或 `.pl`，不修改原始附件。解析要求声明块数与有效块数一致、模块名唯一、每个模块为四点正矩形、宽高为正；不满足的记录进入排除原因，不静默删除。

```text
{
  "source_of_truth": "data/raw/附件/*.blocks",
  "q1_uses_only_blocks": true,
  "instances": [
    {
      "instance": "n100",
      "source": "data/raw/附件/n100.blocks",
      "sha256_lf_normalized": "c66f917c48f3c7ee9624bec8e0dc053eb349d10121d3278d25b09b67a2e94e2b",
      "declared_blocks": 100,
      "parsed_blocks": 100,
      "declared_terminals": 334,
      "processed_rows": 100,
      "excluded_rows": 0,
      "exclusion_reasons": [],
      "positive_dimensions": true,
      "four_vertex_rectangles": true,
      "unique_names": true,
      "total_module_area": 179501,
      "min_width": 16,
      "max_width": 67,
      "min_height": 16,
      "max_height": 67
    },
    {
      "instance": "n200",
      "source": "data/raw/附件/n200.blocks",
      "sha256_lf_normalized": "bed652bf55c2034b04a1c1bbe97ad617e027c11736bf069727a63baf575720ef",
      "declared_blocks": 200,
      "parsed_blocks": 200,
      "declared_terminals": 564,
      "processed_rows": 200,
      "excluded_rows": 0,
      "exclusion_reasons": [],
      "positive_dimensions": true,
      "four_vertex_rectangles": true,
      "unique_names": true,
      "total_module_area": 175696,
      "min_width": 12,
      "max_width": 48,
      "min_height": 12,
      "max_height": 48
    },
    {
      "instance": "n300",
      "source": "data/raw/附件/n300.blocks",
      "sha256_lf_normalized": "88ca80814070d9578c7ccd31182ff31ab026a1a1ea9da5fd0e0342d26327bc82",
      "declared_blocks": 300,
      "parsed_blocks": 300,
      "declared_terminals": 569,
      "processed_rows": 300,
      "excluded_rows": 0,
      "exclusion_reasons": [],
      "positive_dimensions": true,
      "four_vertex_rectangles": true,
      "unique_names": true,
      "total_module_area": 273170,
      "min_width": 12,
      "max_width": 48,
      "min_height": 12,
      "max_height": 48
    }
  ]
}
```

## 2. 模型定义

节点变量为 B*-Tree 的根、左右子节点关系、模块标签和旋转变量 `r_i∈{0,90}`。左子节点放在父模块右侧，右子节点与父模块同横坐标；模块纵坐标由 contour 在其横向区间的最大高度确定。该解码结构保证候选布局不发生正面积重叠，最终仍由共享评价器和独立审计复核。

对布局包围盒 `W,H`，主目标为 `min (W·H)`；面积相同才最小化 `max(W,H)/min(W,H)`。内部 Fast-SA 劣解接受概率为 `min(1, exp(-Δ/T))`，初温由平均上坡代价和初始接受概率 `0.9` 标定，采用论文中的 `c=100,k=7` 三阶段温度更新。

P1 使用旋转、节点移动和节点交换。当前 P2 入口在 P1 上同时开启定向扰动，以及布局与整体 90° 对称状态去重；各组件的消融实验移交 V3。搜索指标始终采用精确字典序；相对 0.5% 只作为跨种子工程非劣比较假设。

## 3. 入口、参数与环境

P0/P1 批量入口：`python -B -m src.Q1 batch --instance n100 --candidates Q1-G,Q1-SP,Q1-BT --seeds 1101-1110 --max-evaluations 100000 --time-limit 60 --restarts 4 --raw data/raw/附件 --runtime-root outputs/q1/_runtime/v2_n100_p0_p1 --table-root outputs/q1/tables --run-id v2_n100_p0_p1`

P2 批量入口：`python -B -m src.Q1 batch --instance n100 --candidates Q1-BT-D --seeds 1101-1110 --max-evaluations 100000 --time-limit 60 --restarts 4 --raw data/raw/附件 --runtime-root outputs/q1/_runtime/v2_n100_p2 --table-root outputs/q1/tables --run-id v2_n100_p2`

P0/P1 批次代码哈希：`05aeb28bf29253376439b2a4c2cf07db2b92297d941f64e205109a8fa3d287e3`；重命名后的 P2 批次代码哈希：`49b949a32a9adf778a19163f3fe3fcc9d2c0d7376e769124d52df820c53a3558`。

```json
{
  "environment": {
    "python": "3.10.20 | packaged by Anaconda, Inc. | (main, Mar 11 2026, 17:42:35) [MSC v.1942 64 bit (AMD64)]",
    "implementation": "CPython",
    "platform": "Windows-10-10.0.26200-SP0",
    "logical_cpu_count": 16,
    "rng": "random.Random (CPython seeded Mersenne Twister)"
  },
  "assumptions": {
    "batch_scope": "Q1-G/Q1-SP/Q1-BT and Q1-BT-D are stored in separate reproducibility batches; P2 ablations are deferred to V3",
    "area_noninferiority_relative_tolerance": 0.005,
    "n100_seeds": [
      1101,
      1102,
      1103,
      1104,
      1105,
      1106,
      1107,
      1108,
      1109,
      1110
    ],
    "max_evaluations_per_run": 100000,
    "time_limit_seconds_per_run": 60.0,
    "restarts_per_run": 4
  }
}
```

## 4. n100 阶段运行结果

以下结果仅是固定预算下的开发粗筛，不是最终模型有效性或优于 P0 的结论。P2 两个单组件消融行来自既有开发记录，本轮只复现两个组件同时开启的 Q1-BT-D；消融的正式重跑和分析移交 V3。失败运行保留在完整明细中。

| 配置 | 合法/总数 | success | timeout | no_feasible | crash | 最好面积 | 中位面积 | 中位长宽比 | 中位评价次数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P1 | 10/10 | 0 | 10 | 0 | 0 | 190557.0 | 194764.5 | 2.996078431372549 | 87245.5 |
| P2-directed-only | 10/10 | 0 | 10 | 0 | 0 | 371910.0 | 444369.0 | 4.428062875635691 | 83214.5 |
| P2-dedup-only | 10/10 | 0 | 10 | 0 | 0 | 189329.0 | 196536.5 | 2.831349002451664 | 84747.5 |
| P2（本轮 Q1-BT-D） | 10/10 | 0 | 10 | 0 | 0 | 362894.0 | 448560.5 | 4.428062875635691 | 67170.0 |

独立 P0/P1 复现批次结果如下。Q1-G 是确定性基线，十个种子产生相同结果，不能视为十个独立随机样本。

| 配置 | 合法/总数 | success | timeout | no_feasible | crash | 最好面积 | 中位面积 | 中位评价次数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Q1-G | 10/10 | 10 | 0 | 0 | 0 | 279189.0 | 279189.0 | 1.0 |
| Q1-SP | 10/10 | 0 | 10 | 0 | 0 | 203840.0 | 206895.0 | 24873.0 |
| Q1-BT | 10/10 | 0 | 10 | 0 | 0 | 191394.0 | 195955.5 | 73858.0 |

面积持平容差和主模型选型仍需 n200 正式协议；独立 P0/P1 批次的 30 条记录均保留在新明细表中，但其 n100 结果仍不构成主模型选择或 P1/P2 相对基线优越性的结论，也不代替两人共同冻结 C3。

## 5. 证据文件

- `data/processed/q1_v2_input_audit.json`：Q1 输入审计与哈希。
- `outputs/q1/tables/v2_n100_run_details.csv`：全部配置和种子的运行明细。
- `outputs/q1/tables/v2_n100_ablation_summary.csv`：配置汇总。
- `outputs/q1/tables/v2_n100_paired_differences.csv`：相同种子的配对差值。
- `outputs/q1/tables/v2_n100_representative_layouts.csv`：各配置代表性完整布局。
- `outputs/q1/tables/v2_n100_p0_p1_run_details.csv`：Q1-G、Q1-SP、Q1-BT 共 30 条独立运行明细。
- `outputs/q1/tables/v2_n100_p0_p1_summary.csv`：上述批次的候选汇总。
- `outputs/q1/tables/v2_n100_p0_p1_config_snapshot.json`：入口、代码哈希、参数、种子与环境。
- `outputs/q1/tables/v2_n100_p0_p1_representative_layouts.csv`：每个候选的代表布局坐标。
- `outputs/q1/tables/v2_n100_p2_run_details.csv`：Q1-BT-D 的 10 条独立运行明细。
- `outputs/q1/tables/v2_n100_p2_summary.csv`：Q1-BT-D 批次汇总。
- `outputs/q1/tables/v2_n100_p2_config_snapshot.json`：P2 入口、代码哈希、参数、种子与环境。
- `outputs/q1/tables/v2_n100_p2_representative_layouts.csv`：P2 最佳运行的完整布局坐标。
- `outputs/q1/_runtime/`：逐次布局和日志；不进入最终结果目录。

## 6. 未解决事项

1. n200 前仍需由两人共同冻结候选、预算、机器线程、RNG 和非劣判定。
2. P2 消融及 n100 正式比较移交 V3；任何论文确定数字须等待 V3 的正式比较和独立复核。
