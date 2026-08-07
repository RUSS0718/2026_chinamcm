# 第 0 轮：共享评价器与几何核验报告

- 问题范围：Q1-Q4 共用前置核验
- 当前状态：REVIEWING
- 负责人：蔡乔夕（共享评价器）、钟江铭（独立审计），共同负责解析与数据冻结
- 交叉复核：钟江铭、蔡乔夕
- Agent 技术实现：terra_worker
- Agent 技术验收：main Agent
- 最后更新：2026-08-07

## 已完成内容

- 完成官方 `.nets` 格式解析：每个 `NetDegree` 后直接读取指定数量的引脚，并生成 `net_000001` 等稳定的内部网络编号。
- 解析器记录模块、Terminal、网络和引脚的声明数量与实际数量，同时记录网络度数总和、引脚引用数、缺失引用及数据完整性。
- 审计程序逐一比较 `.blocks` 中声明的 Terminal 名称与 `.pl` 中的 Terminal 名称，防止在数量相同的情况下出现名称错位。
- 主评价器和独立审计均将 0°、90°、180°、270° 旋转后的多边形重新归一到布局左下锚点。
- Q4 的面积与碰撞使用真实正交多边形计算，不使用外接矩形代替。两个评价实现均显式返回长宽比 `aspect_ratio`；`rho` 表示死区比例，`deadspace` 表示死区面积。
- 使用 Python 标准库 `unittest` 编写人工常量测试，覆盖手算 HPWL、Terminal 绝对坐标、旋转后中心引脚、边界接触、正面积重叠、轮廓贴边与越界、死区、L 型四向旋转、凹形嵌套，以及主评价器与独立审计结果一致性。
- 命令行入口生成 `data/processed/round0_audit.json`。原始文件清单覆盖 `data/raw/` 下全部 12 个文件；每个实例均记录 3 个附件文件的相对路径、字节数和 SHA-256。

## 实际命令与结果

```powershell
& 'C:\Users\CQX\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
```

实际结果：运行 6 项测试，全部通过，输出状态为 `OK`。

```powershell
& 'C:\Users\CQX\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m src.round0
```

实际结果：成功生成 `data\processed\round0_audit.json`。

## 三实例审计结果

| 实例 | 模块数 | Terminal 数 | 网络数 | 声明引脚数 | 网络度数总和 | 缺失引用数 |
|---|---:|---:|---:|---:|---:|---:|
| n100 | 100 | 334 | 885 | 1873 | 1873 | 0 |
| n200 | 200 | 564 | 1585 | 3599 | 3599 | 0 |
| n300 | 300 | 569 | 1893 | 4358 | 4358 | 0 |

三个实例的 `.blocks` 与 `.pl` Terminal 名称集合完全一致，即 `terminal_sets_match=true`。main Agent 已独立复算上述数量和文件哈希，并通过第 0 轮技术验收。按照仓库阶段规则，在指定人类复核人确认前，报告状态继续保持 `REVIEWING`。

## 验收结论

- 第 0 轮已证明解析、人工几何样例和共享指标计算在当前测试范围内一致。
- 该结论只适用于数据与评价框架的前置核验，不代表任何优化器已经实现或任何候选模型效果已经得到验证。

## 剩余风险

- 正交多边形评价目前通过人工构造的小样例验证；进入 Q4 V2 后仍需使用题面冻结的真实多边形顶点再次复核。
- 当前没有优化器运行结果、模型比较结果或论文最终数字，不得将本报告作为模型有效性证据。
