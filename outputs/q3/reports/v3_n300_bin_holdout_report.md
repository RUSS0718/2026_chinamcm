# Q3-BIN V3 n300 快速固定预算留出验证报告

- 问题：`Q3`
- 状态：`REVIEWING`
- 主责建模师：钟江铭
- 复核人：蔡乔夕（待人工复核）
- 更新时间：2026-08-09
- 执行完整性：完整
- attempt：`q3bin_n300_20260809T231631`
- 证据根目录：`E:/2026_chinamcm/outputs/q3/_runtime/v3_n300_bin_holdout/q3bin_n300_20260809T231631`

## 1. 直接结论与解释边界

`d_best=0.05625`，`d_robust=0.05625`。final 合法且审计一致率 30/30 = 1.000，formal audit 一致率 30/30 = 1.000。
final HPWL：median=786498.75，IQR=2776.875，P90=787724.35。
本轮未运行 Q3-LIN 或 Q3-CONT-R，不能形成完整 n300 三路线比较，也不能据此证明 Q3-BIN 优于 LIN/CONT-R。
`timeout` 表示达到 60 秒固定预算，不表示失败、收敛或最优；较小死区未找到只能写成本预算内未找到，不能写成数学不可行。

## 2. 冻结配置与运行规模

- route：`Q3-BIN`；inner：`Q2-HG`；ratio：`0–0.15`；precision：`0.005`；decision：`robust`；minimum success：`0.80`
- adaptive constraints：`on`；hypergraph init：`on`；continuous compression：`off`
- `30000 evaluations / 60 s / 4 restarts`；workers/processes：`4/4`；threads/process：`1`
- threshold cold seeds：`3301–3330`；independent final seeds：`3401–3430`
- 实际 attempts：`240` / 最大 `240`；运行时间：`3935.198 s`（`65.59 min`）

## 3. Threshold 点

| d | cold seeds | 合法且审计一致 | missing | robust | 状态 |
|---:|---|---:|---:|:---:|---|
| 0 | 3301–3330 | 0/30 | 0 | 否 | timeout=0, no_feasible=30, crash=0, success=0 |
| 0.0375 | 3301–3330 | 0/30 | 0 | 否 | timeout=0, no_feasible=30, crash=0, success=0 |
| 0.046875 | 3301–3330 | 0/30 | 0 | 否 | timeout=0, no_feasible=30, crash=0, success=0 |
| 0.0515625 | 3301–3330 | 0/30 | 0 | 否 | timeout=0, no_feasible=30, crash=0, success=0 |
| 0.05625 | 3301–3330 | 30/30 | 0 | 是 | timeout=30, no_feasible=0, crash=0, success=0 |
| 0.075 | 3301–3330 | 30/30 | 0 | 是 | timeout=30, no_feasible=0, crash=0, success=0 |
| 0.15 | 3301–3330 | 30/30 | 0 | 是 | timeout=30, no_feasible=0, crash=0, success=0 |

相邻更小已测试点：
- `d=0.0515625`：合法且审计一致 0/30，missing=0，timeout=0, no_feasible=30, crash=0, success=0。仅表示固定预算搜索状态。

### 3.1 每个 threshold 的 cold seed 记录

| d | seed | status | legal | audit match | HPWL | runtime_s | evaluations |
|---:|---:|---|:---:|:---:|---:|---:|---:|
| 0 | 3301 | no_feasible | False | True | 947013 | 60.0081085002 | 5180 |
| 0 | 3302 | no_feasible | False | True | 945821 | 60.0104165999 | 5079 |
| 0 | 3303 | no_feasible | False | True | 967327 | 60.013694 | 4920 |
| 0 | 3304 | no_feasible | False | True | 976481.5 | 60.0071090001 | 5142 |
| 0 | 3305 | no_feasible | False | True | 955335 | 60.0123456002 | 5203 |
| 0 | 3306 | no_feasible | False | True | 947166.5 | 60.0150774 | 4990 |
| 0 | 3307 | no_feasible | False | True | 947807.5 | 60.0068822 | 4927 |
| 0 | 3308 | no_feasible | False | True | 959447 | 60.0036624002 | 5058 |
| 0 | 3309 | no_feasible | False | True | 928663.5 | 60.0090437999 | 4889 |
| 0 | 3310 | no_feasible | False | True | 966715.5 | 60.0023127999 | 4940 |
| 0 | 3311 | no_feasible | False | True | 951779 | 60.016047 | 5090 |
| 0 | 3312 | no_feasible | False | True | 931724.5 | 60.0143835 | 5085 |
| 0 | 3313 | no_feasible | False | True | 941733.5 | 60.0130918 | 4798 |
| 0 | 3314 | no_feasible | False | True | 985398 | 60.0087637999 | 5032 |
| 0 | 3315 | no_feasible | False | True | 902750.5 | 60.0059632 | 4872 |
| 0 | 3316 | no_feasible | False | True | 957934.5 | 60.0005918001 | 4878 |
| 0 | 3317 | no_feasible | False | True | 954937 | 60.0065452 | 4876 |
| 0 | 3318 | no_feasible | False | True | 944198.5 | 60.0073674 | 4991 |
| 0 | 3319 | no_feasible | False | True | 937699.5 | 60.0067639002 | 4842 |
| 0 | 3320 | no_feasible | False | True | 971499.5 | 60.0086113 | 4794 |
| 0 | 3321 | no_feasible | False | True | 959969.5 | 60.0025327001 | 4878 |
| 0 | 3322 | no_feasible | False | True | 939695 | 60.0083363 | 4829 |
| 0 | 3323 | no_feasible | False | True | 980415 | 60.0007684 | 4833 |
| 0 | 3324 | no_feasible | False | True | 946639.5 | 60.0063718001 | 5012 |
| 0 | 3325 | no_feasible | False | True | 978472.5 | 60.0081143 | 4764 |
| 0 | 3326 | no_feasible | False | True | 948155.5 | 60.0146812999 | 4903 |
| 0 | 3327 | no_feasible | False | True | 944270.5 | 60.0008819001 | 4787 |
| 0 | 3328 | no_feasible | False | True | 929744 | 60.0106465002 | 4863 |
| 0 | 3329 | no_feasible | False | True | 929007 | 60.0033070999 | 6161 |
| 0 | 3330 | no_feasible | False | True | 892621 | 60.0047034 | 6117 |
| 0.0375 | 3301 | no_feasible | False | True | 928544.5 | 60.0091263999 | 5017 |
| 0.0375 | 3302 | no_feasible | False | True | 944032 | 60.0102243 | 4919 |
| 0.0375 | 3303 | no_feasible | False | True | 932720 | 60.0030058001 | 4852 |
| 0.0375 | 3304 | no_feasible | False | True | 960351.5 | 60.0109123001 | 4961 |
| 0.0375 | 3305 | no_feasible | False | True | 918839.5 | 60.0024766 | 5048 |
| 0.0375 | 3306 | no_feasible | False | True | 990521.5 | 60.0036378 | 4825 |
| 0.0375 | 3307 | no_feasible | False | True | 930971.5 | 60.0056171 | 4744 |
| 0.0375 | 3308 | no_feasible | False | True | 927870 | 60.007768 | 4978 |
| 0.0375 | 3309 | no_feasible | False | True | 944503.5 | 60.0102488 | 4796 |
| 0.0375 | 3310 | no_feasible | False | True | 957135 | 60.0053615 | 4706 |
| 0.0375 | 3311 | no_feasible | False | True | 923112.5 | 60.0070644999 | 4956 |
| 0.0375 | 3312 | no_feasible | False | True | 943927 | 60.0132348998 | 4906 |
| 0.0375 | 3313 | no_feasible | False | True | 974172 | 60.0030962001 | 4571 |
| 0.0375 | 3314 | no_feasible | False | True | 955064.5 | 60.0049769001 | 4739 |
| 0.0375 | 3315 | no_feasible | False | True | 934603.5 | 60.0077835999 | 4616 |
| 0.0375 | 3316 | no_feasible | False | True | 937931 | 60.0039434 | 4606 |
| 0.0375 | 3317 | no_feasible | False | True | 921531.5 | 60.0113458 | 4621 |
| 0.0375 | 3318 | no_feasible | False | True | 948846.5 | 60.0018014999 | 4732 |
| 0.0375 | 3319 | no_feasible | False | True | 924662.5 | 60.0029809 | 4486 |
| 0.0375 | 3320 | no_feasible | False | True | 954702 | 60.0021316998 | 4565 |
| 0.0375 | 3321 | no_feasible | False | True | 954401.5 | 60.0159194001 | 4771 |
| 0.0375 | 3322 | no_feasible | False | True | 942439 | 60.0042771001 | 4766 |
| 0.0375 | 3323 | no_feasible | False | True | 931202 | 60.0057949 | 4707 |
| 0.0375 | 3324 | no_feasible | False | True | 922263.5 | 60.0093306 | 4868 |
| 0.0375 | 3325 | no_feasible | False | True | 982933 | 60.0065315 | 4689 |
| 0.0375 | 3326 | no_feasible | False | True | 929864 | 60.003396 | 4815 |
| 0.0375 | 3327 | no_feasible | False | True | 930631 | 60.0047752999 | 4794 |
| 0.0375 | 3328 | no_feasible | False | True | 951537.5 | 60.0031623 | 4795 |
| 0.0375 | 3329 | no_feasible | False | True | 930206.5 | 60.0150800999 | 6049 |
| 0.0375 | 3330 | no_feasible | False | True | 958609 | 60.0013532001 | 5913 |
| 0.046875 | 3301 | no_feasible | False | True | 942848.5 | 60.0085032999 | 4961 |
| 0.046875 | 3302 | no_feasible | False | True | 976178.5 | 60.0003832001 | 4920 |
| 0.046875 | 3303 | no_feasible | False | True | 991510 | 60.0088857999 | 4781 |
| 0.046875 | 3304 | no_feasible | False | True | 949333.5 | 60.0039180999 | 5004 |
| 0.046875 | 3305 | no_feasible | False | True | 956021.5 | 60.0097806 | 5148 |
| 0.046875 | 3306 | no_feasible | False | True | 941796.5 | 60.0064923998 | 4934 |
| 0.046875 | 3307 | no_feasible | False | True | 943804.5 | 60.0121293999 | 4805 |
| 0.046875 | 3308 | no_feasible | False | True | 950349 | 60.0067024999 | 5013 |
| 0.046875 | 3309 | no_feasible | False | True | 970147.5 | 60.0012075 | 4873 |
| 0.046875 | 3310 | no_feasible | False | True | 950919 | 60.0150005999 | 4863 |
| 0.046875 | 3311 | no_feasible | False | True | 972825.5 | 60.0064012001 | 5025 |
| 0.046875 | 3312 | no_feasible | False | True | 926950 | 60.0154010998 | 5028 |
| 0.046875 | 3313 | no_feasible | False | True | 987239 | 60.0087114 | 4893 |
| 0.046875 | 3314 | no_feasible | False | True | 948771.5 | 60.0065015 | 5084 |
| 0.046875 | 3315 | no_feasible | False | True | 904553.5 | 60.0060175001 | 4973 |
| 0.046875 | 3316 | no_feasible | False | True | 950293.5 | 60.0038928001 | 4925 |
| 0.046875 | 3317 | no_feasible | False | True | 949518.5 | 60.0013728002 | 4876 |
| 0.046875 | 3318 | no_feasible | False | True | 933666 | 60.0001433 | 4989 |
| 0.046875 | 3319 | no_feasible | False | True | 934395.5 | 60.0087825002 | 4833 |
| 0.046875 | 3320 | no_feasible | False | True | 943721.5 | 60.0106968 | 4767 |
| 0.046875 | 3321 | no_feasible | False | True | 940590.5 | 60.0072785001 | 4679 |
| 0.046875 | 3322 | no_feasible | False | True | 938796.5 | 60.0050699001 | 4568 |
| 0.046875 | 3323 | no_feasible | False | True | 1007707 | 60.0063509 | 4530 |
| 0.046875 | 3324 | no_feasible | False | True | 957059 | 60.0049182998 | 4657 |
| 0.046875 | 3325 | no_feasible | False | True | 959899 | 60.0021722 | 4820 |
| 0.046875 | 3326 | no_feasible | False | True | 949292.5 | 60.0099866001 | 4901 |
| 0.046875 | 3327 | no_feasible | False | True | 938386 | 60.0241026001 | 4891 |
| 0.046875 | 3328 | no_feasible | False | True | 930499 | 60.0034282999 | 4861 |
| 0.046875 | 3329 | no_feasible | False | True | 912037 | 60.0092118999 | 6060 |
| 0.046875 | 3330 | no_feasible | False | True | 950490.5 | 60.0061971 | 5886 |
| 0.0515625 | 3301 | no_feasible | False | True | 925102.5 | 60.0097356001 | 5038 |
| 0.0515625 | 3302 | no_feasible | False | True | 954970 | 60.0010300002 | 5024 |
| 0.0515625 | 3303 | no_feasible | False | True | 995131.5 | 60.0061945999 | 4848 |
| 0.0515625 | 3304 | no_feasible | False | True | 949010.5 | 60.0080014998 | 5094 |
| 0.0515625 | 3305 | no_feasible | False | True | 918134.5 | 60.0008620999 | 5029 |
| 0.0515625 | 3306 | no_feasible | False | True | 940299 | 60.0080439001 | 4860 |
| 0.0515625 | 3307 | no_feasible | False | True | 971228 | 60.007063 | 4831 |
| 0.0515625 | 3308 | no_feasible | False | True | 930280.5 | 60.0006388002 | 5024 |
| 0.0515625 | 3309 | no_feasible | False | True | 960206 | 60.0066333001 | 4864 |
| 0.0515625 | 3310 | no_feasible | False | True | 943121 | 60.0086635 | 4761 |
| 0.0515625 | 3311 | no_feasible | False | True | 944499.5 | 60.0029915001 | 4934 |
| 0.0515625 | 3312 | no_feasible | False | True | 909078.5 | 60.0078743999 | 4980 |
| 0.0515625 | 3313 | no_feasible | False | True | 937920 | 60.0100461999 | 4953 |
| 0.0515625 | 3314 | no_feasible | False | True | 956367.5 | 60.0057172999 | 5096 |
| 0.0515625 | 3315 | no_feasible | False | True | 936220 | 60.0028902001 | 5050 |
| 0.0515625 | 3316 | no_feasible | False | True | 974621 | 60.0011513999 | 4970 |
| 0.0515625 | 3317 | no_feasible | False | True | 930873.5 | 60.0049514002 | 4985 |
| 0.0515625 | 3318 | no_feasible | False | True | 926249 | 60.0156355998 | 5072 |
| 0.0515625 | 3319 | no_feasible | False | True | 937259.5 | 60.0009991 | 4914 |
| 0.0515625 | 3320 | no_feasible | False | True | 940780.5 | 60.0017665001 | 4850 |
| 0.0515625 | 3321 | no_feasible | False | True | 972984.5 | 60.0016920001 | 4930 |
| 0.0515625 | 3322 | no_feasible | False | True | 945562.5 | 60.0045749999 | 4837 |
| 0.0515625 | 3323 | no_feasible | False | True | 962562.5 | 60.009108 | 4855 |
| 0.0515625 | 3324 | no_feasible | False | True | 936813.5 | 60.0064516 | 4952 |
| 0.0515625 | 3325 | no_feasible | False | True | 907614.5 | 60.0058964 | 4822 |
| 0.0515625 | 3326 | no_feasible | False | True | 937497 | 60.0139174 | 4936 |
| 0.0515625 | 3327 | no_feasible | False | True | 929731.5 | 60.0108038001 | 4835 |
| 0.0515625 | 3328 | no_feasible | False | True | 924174 | 60.0079760002 | 4933 |
| 0.0515625 | 3329 | no_feasible | False | True | 935290 | 60.0080976 | 6074 |
| 0.0515625 | 3330 | no_feasible | False | True | 921052.5 | 60.0076601 | 5969 |
| 0.05625 | 3301 | timeout | True | True | 786991 | 60.0087841998 | 5086 |
| 0.05625 | 3302 | timeout | True | True | 784216.5 | 60.0113323 | 5063 |
| 0.05625 | 3303 | timeout | True | True | 788398 | 60.0071836 | 5058 |
| 0.05625 | 3304 | timeout | True | True | 786495.5 | 60.0046171001 | 5144 |
| 0.05625 | 3305 | timeout | True | True | 785886 | 60.0075327002 | 5006 |
| 0.05625 | 3306 | timeout | True | True | 783440.5 | 60.0078299001 | 5082 |
| 0.05625 | 3307 | timeout | True | True | 785477.5 | 60.0115365 | 5135 |
| 0.05625 | 3308 | timeout | True | True | 784481.5 | 60.0030682001 | 5045 |
| 0.05625 | 3309 | timeout | True | True | 788756.5 | 60.0136051001 | 5103 |
| 0.05625 | 3310 | timeout | True | True | 786918 | 60.0160979 | 5047 |
| 0.05625 | 3311 | timeout | True | True | 785577.5 | 60.0150382 | 5001 |
| 0.05625 | 3312 | timeout | True | True | 781476 | 60.0038569001 | 5086 |
| 0.05625 | 3313 | timeout | True | True | 786078.5 | 60.0047746999 | 5118 |
| 0.05625 | 3314 | timeout | True | True | 785678.5 | 60.0045630999 | 5164 |
| 0.05625 | 3315 | timeout | True | True | 786445.5 | 60.0052464001 | 5121 |
| 0.05625 | 3316 | timeout | True | True | 787444.5 | 60.0035148 | 5076 |
| 0.05625 | 3317 | timeout | True | True | 784827 | 60.0121591999 | 5155 |
| 0.05625 | 3318 | timeout | True | True | 787298.5 | 60.0008777999 | 5050 |
| 0.05625 | 3319 | timeout | True | True | 785253 | 60.0095447002 | 5166 |
| 0.05625 | 3320 | timeout | True | True | 786683.5 | 60.0009421001 | 5014 |
| 0.05625 | 3321 | timeout | True | True | 787567.5 | 60.0101081 | 5012 |
| 0.05625 | 3322 | timeout | True | True | 787246 | 60.0025723001 | 5059 |
| 0.05625 | 3323 | timeout | True | True | 784312.5 | 60.0087047999 | 5212 |
| 0.05625 | 3324 | timeout | True | True | 786173.5 | 60.0078932999 | 5036 |
| 0.05625 | 3325 | timeout | True | True | 783267.5 | 60.0065899 | 5030 |
| 0.05625 | 3326 | timeout | True | True | 782915 | 60.0040382999 | 5219 |
| 0.05625 | 3327 | timeout | True | True | 787697 | 60.0076788 | 5086 |
| 0.05625 | 3328 | timeout | True | True | 785742.5 | 60.0090988001 | 5011 |
| 0.05625 | 3329 | timeout | True | True | 785362 | 60.0066264998 | 6265 |
| 0.05625 | 3330 | timeout | True | True | 785711 | 60.0037964 | 6179 |
| 0.075 | 3301 | timeout | True | True | 785655 | 60.0025728 | 5076 |
| 0.075 | 3302 | timeout | True | True | 782215.5 | 60.0095901999 | 5047 |
| 0.075 | 3303 | timeout | True | True | 784950 | 60.0094651 | 5188 |
| 0.075 | 3304 | timeout | True | True | 784771.5 | 60.003944 | 5161 |
| 0.075 | 3305 | timeout | True | True | 784000.5 | 60.0024667999 | 5085 |
| 0.075 | 3306 | timeout | True | True | 783666.5 | 60.0018860002 | 5085 |
| 0.075 | 3307 | timeout | True | True | 784045 | 60.002318 | 5083 |
| 0.075 | 3308 | timeout | True | True | 785486.5 | 60.0057873002 | 5152 |
| 0.075 | 3309 | timeout | True | True | 784575 | 60.0111246 | 5171 |
| 0.075 | 3310 | timeout | True | True | 785690 | 60.0063255001 | 4971 |
| 0.075 | 3311 | timeout | True | True | 783822.5 | 60.0002811002 | 4991 |
| 0.075 | 3312 | timeout | True | True | 783660.5 | 60.0085259001 | 5095 |
| 0.075 | 3313 | timeout | True | True | 783230.5 | 60.0085511 | 5103 |
| 0.075 | 3314 | timeout | True | True | 783518.5 | 60.0089377998 | 5070 |
| 0.075 | 3315 | timeout | True | True | 786412 | 60.0071539001 | 5076 |
| 0.075 | 3316 | timeout | True | True | 784827 | 60.0041115 | 5082 |
| 0.075 | 3317 | timeout | True | True | 783209 | 60.0058939001 | 5087 |
| 0.075 | 3318 | timeout | True | True | 784226 | 60.0067894 | 5023 |
| 0.075 | 3319 | timeout | True | True | 783280 | 60.0081718999 | 5098 |
| 0.075 | 3320 | timeout | True | True | 784665 | 60.0131371999 | 5033 |
| 0.075 | 3321 | timeout | True | True | 784640 | 60.0020345999 | 5024 |
| 0.075 | 3322 | timeout | True | True | 786629 | 60.0137305998 | 5018 |
| 0.075 | 3323 | timeout | True | True | 782386 | 60.0044932 | 5133 |
| 0.075 | 3324 | timeout | True | True | 784589 | 60.0150500999 | 5030 |
| 0.075 | 3325 | timeout | True | True | 784177.5 | 60.0064107 | 5009 |
| 0.075 | 3326 | timeout | True | True | 779685.5 | 60.0078830998 | 5077 |
| 0.075 | 3327 | timeout | True | True | 782922.5 | 60.0083448999 | 5032 |
| 0.075 | 3328 | timeout | True | True | 784022.5 | 60.0074225999 | 5029 |
| 0.075 | 3329 | timeout | True | True | 782954 | 60.0018237 | 6458 |
| 0.075 | 3330 | timeout | True | True | 784172 | 60.0033628 | 6368 |
| 0.15 | 3301 | timeout | True | True | 788477 | 60.0078781 | 5222 |
| 0.15 | 3302 | timeout | True | True | 784428.5 | 60.0105722002 | 5164 |
| 0.15 | 3303 | timeout | True | True | 788051.5 | 60.003552 | 5294 |
| 0.15 | 3304 | timeout | True | True | 789177.5 | 60.0074199 | 5193 |
| 0.15 | 3305 | timeout | True | True | 788297 | 60.0071981 | 5227 |
| 0.15 | 3306 | timeout | True | True | 784995.5 | 60.0045554 | 5221 |
| 0.15 | 3307 | timeout | True | True | 784612.5 | 60.0115002 | 5159 |
| 0.15 | 3308 | timeout | True | True | 789330 | 60.0112647999 | 5238 |
| 0.15 | 3309 | timeout | True | True | 790550.5 | 60.0029644 | 5077 |
| 0.15 | 3310 | timeout | True | True | 788217 | 60.0072261002 | 5070 |
| 0.15 | 3311 | timeout | True | True | 787599 | 60.0043707001 | 5094 |
| 0.15 | 3312 | timeout | True | True | 783570.5 | 60.0086888999 | 5079 |
| 0.15 | 3313 | timeout | True | True | 786030 | 60.0098152999 | 5145 |
| 0.15 | 3314 | timeout | True | True | 787670.5 | 60.0028857 | 5143 |
| 0.15 | 3315 | timeout | True | True | 790644 | 60.0106651001 | 5069 |
| 0.15 | 3316 | timeout | True | True | 785772.5 | 60.0004398001 | 5132 |
| 0.15 | 3317 | timeout | True | True | 788772 | 60.0155094999 | 5064 |
| 0.15 | 3318 | timeout | True | True | 789325 | 60.0038129999 | 5104 |
| 0.15 | 3319 | timeout | True | True | 787575 | 60.0102363999 | 5082 |
| 0.15 | 3320 | timeout | True | True | 789461.5 | 60.0050716 | 5128 |
| 0.15 | 3321 | timeout | True | True | 789497 | 60.0029245 | 5063 |
| 0.15 | 3322 | timeout | True | True | 788518.5 | 60.0144247001 | 5069 |
| 0.15 | 3323 | timeout | True | True | 785949 | 60.0069081001 | 5149 |
| 0.15 | 3324 | timeout | True | True | 780377 | 60.0053892999 | 5118 |
| 0.15 | 3325 | timeout | True | True | 783608.5 | 60.0092010999 | 5130 |
| 0.15 | 3326 | timeout | True | True | 782376 | 60.0071254 | 5102 |
| 0.15 | 3327 | timeout | True | True | 786936.5 | 60.0011412001 | 5105 |
| 0.15 | 3328 | timeout | True | True | 785710.5 | 60.0065889999 | 5139 |
| 0.15 | 3329 | timeout | True | True | 785659 | 60.0010966999 | 6335 |
| 0.15 | 3330 | timeout | True | True | 776247 | 60.0058509 | 6377 |

## 4. Independent final seeds

状态：timeout=30, no_feasible=0, crash=0, success=0；missing=0。

| seed | status | legal | audit match | HPWL | runtime_s | evaluations |
|---:|---|:---:|:---:|---:|---:|---:|
| 3401 | timeout | True | True | 785879.5 | 60.0102282001 | 5344 |
| 3402 | timeout | True | True | 786170 | 60.0074469 | 5116 |
| 3403 | timeout | True | True | 787002.5 | 60.0081753 | 5201 |
| 3404 | timeout | True | True | 782554.5 | 60.0082310999 | 5268 |
| 3405 | timeout | True | True | 787592 | 60.0051159002 | 5191 |
| 3406 | timeout | True | True | 789172.5 | 60.0097675 | 5098 |
| 3407 | timeout | True | True | 785276.5 | 60.0128931 | 5313 |
| 3408 | timeout | True | True | 789362.5 | 60.0143329999 | 5228 |
| 3409 | timeout | True | True | 782907.5 | 60.0057331 | 5191 |
| 3410 | timeout | True | True | 786780 | 60.0056292 | 5223 |
| 3411 | timeout | True | True | 784351.5 | 60.0032949999 | 5091 |
| 3412 | timeout | True | True | 787324 | 60.00651 | 5186 |
| 3413 | timeout | True | True | 786947.5 | 60.0094629999 | 5102 |
| 3414 | timeout | True | True | 787966 | 60.0073649001 | 5202 |
| 3415 | timeout | True | True | 786820.5 | 60.0085189999 | 5209 |
| 3416 | timeout | True | True | 785715.5 | 60.0154412 | 5198 |
| 3417 | timeout | True | True | 783846 | 60.0113124 | 5233 |
| 3418 | timeout | True | True | 787697.5 | 60.0129384 | 5064 |
| 3419 | timeout | True | True | 786421 | 60.0133011001 | 5071 |
| 3420 | timeout | True | True | 786576.5 | 60.0041041998 | 5131 |
| 3421 | timeout | True | True | 782149 | 60.0046051999 | 5250 |
| 3422 | timeout | True | True | 787159.5 | 60.0001111 | 5168 |
| 3423 | timeout | True | True | 787456.5 | 60.0060701999 | 5273 |
| 3424 | timeout | True | True | 782587 | 60.0095422 | 5167 |
| 3425 | timeout | True | True | 783189.5 | 60.0086817001 | 5215 |
| 3426 | timeout | True | True | 787371.5 | 60.0028277 | 5191 |
| 3427 | timeout | True | True | 786412 | 60.0024857998 | 5178 |
| 3428 | timeout | True | True | 785581 | 60.0014859 | 5135 |
| 3429 | timeout | True | True | 787498.5 | 60.0079321999 | 6199 |
| 3430 | timeout | True | True | 781072 | 60.0098705001 | 6345 |

## 5. 与 n200 Q3-BIN 的规模稳定性对照

| 实例 | threshold 点数 | d_best | d_robust | final 合法率 | HPWL median | IQR | P90 |
|---|---:|---:|---:|---:|---:|---:|---:|
| n200 | 7 | 0.075 | 0.075 | 1 | 520098.75 | 5050.875 | 522641.75 |
| n300 | 7 | 0.05625 | 0.05625 | 1 | 786498.75 | 2776.875 | 787724.35 |

该对照只检查冻结 Q3-BIN 从 n200 到 n300 的固定预算规模稳定性；HPWL 绝对量级不用于跨实例优劣排序。

## 6. 完整性与哈希

- threshold：210/210；missing=0；timeout=90, no_feasible=120, crash=0, success=0
- final：30/30；missing=0；timeout=30, no_feasible=0, crash=0, success=0
- code hash：`1a0f8d6a28a0b4ab5529836ad3a6c1bb7e97fc2908e9c57f5118954c393bf3e2`
- config hash：`e03febf1bd99c941ef565a29ca8a3c04ebb51b71152e14c520f0c70c5ec224bc`
- aggregate data hash：`d7ad31e667df750871ff48b49954f63ac10381a333b010a703350543e285d180`

| 原始文件 | bytes | raw SHA-256 | normalized SHA-256 |
|---|---:|---|---|
| `data/raw/附件/n300.blocks` | 21289 | `edfd2f9d93e1f30933d78282f28ef5a4d3aee6c1a024657e66dff115506d89c4` | `88ca80814070d9578c7ccd31182ff31ab026a1a1ea9da5fd0e0342d26327bc82` |
| `data/raw/附件/n300.nets` | 46787 | `6895cff224d81bef4325f72944ac5e7f498ef0fa31c050a5f90633f6b456c85f` | `39d9cc7b7d347dd0ecefb8d17e0adfbcbf2af1c071079fbf64caec34bcc0d94c` |
| `data/raw/附件/n300.pl` | 6609 | `03352d2a43dd3546116317a8194eae29557a4f3d00875d3a5738c4b77fa484e1` | `7b095ff15624666c3fdf95c71fda72e45ffff70acdf27d10302830ba3031f035` |

实际命令：

```text
D:\miniconda3\envs\causal_paper\python.exe -B -m src.Q3 --instance n300 --candidate Q3-BIN --inner-candidate Q2-HG --lower-ratio 0 --upper-ratio 0.15 --precision 0.005 --robust-min-success-rate 0.8 --decision-rule robust --seeds 3301-3330 --max-evaluations 30000 --time-limit 60.0 --restarts 4 --workers 4 --adaptive-constraints on --hypergraph-init on --continuous-compression off --final-seeds 3401-3430 --final-max-evaluations 30000 --final-time-limit 60.0 --final-restarts 4 --stop-submissions-after 6000.0 --hard-stop-after 6260.0 --raw data/raw/附件 --runtime-root E:\2026_chinamcm\outputs\q3\_runtime\v3_n300_bin_holdout\q3bin_n300_20260809T231631\runtime --table-root E:\2026_chinamcm\outputs\q3\_runtime\v3_n300_bin_holdout\q3bin_n300_20260809T231631\tables --run-id v3_n300_q3-bin
```

## 7. 未执行与待复核

- 未运行 Q3-LIN、Q3-CONT-R，未调参、加预算、补 seed 或挑选结果。
- 未修改 `data/raw/`，未覆盖 n200/既有 attempt，未迁入 `outputs/q3/final/`。
- 未创建 commit，未 push。状态保持 `REVIEWING`，等待人工复核。
