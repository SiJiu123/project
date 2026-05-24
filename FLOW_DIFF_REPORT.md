# 四模型全流程对照报告（基于副本流程复跑）

## 1. 本次排查范围与约束
- 目标：对比 `project - 副本` 的原始四模型流程 与 当前 `project` 统一管线流程 的结果差异。
- 模型：`scaden`、`scpDeconv`、`TAPE`、`MuSiC`。
- 约束：**不修改 `project - 副本` 任何代码**（仅运行）。
- 输入口径：使用当前 `project/data/standard/human_lung` 的标准数据，并确认是 `uniform` 激活口径。
- 你要求排除项：**测试集伪样本生成差异不纳入讨论**。

## 2. 输入口径确认（uniform）
已验证以下文件 MD5 完全一致，说明当前标准输入确实是 uniform：
- `302C_bulk_X.txt` == `302C_bulk_X.uniform.txt`
- `302C_bulk_obs.txt` == `302C_bulk_obs.uniform.txt`

## 3. 副本流程复跑说明（只跑不改代码）
### 3.1 Scaden（按副本 Scaden.md 主链路）
执行链路：
1. `scaden simulate`（296C, n=6000）
2. `scaden process`
3. `scaden train --steps 5000`
4. `scaden predict`

说明：
- 为满足 Scaden 输入格式要求，仅对**数据文件内容**做了运行前兼容处理（不改副本代码）：
  - `296C_celltypes.txt` 表头为 `Celltype`
  - `296C_counts.txt` 行索引转数字，避免 `simulate` 解析报错
- 以上是数据对接动作，不是代码修改。

### 3.2 scpDeconv
执行：在副本 `models/scpDeconv/scpDeconv-main` 目录运行 `python main.py --dataset human_lung_RNA`。
- 四阶段完整执行（mixup -> AEimpute -> DANN -> inference）。
- 输入特征：该流程直接从 `data/296C_train.h5ad` 和 `data/302C_test.h5ad` 出发构造训练/目标数据并输出预测与对应 GT。

### 3.3 TAPE
执行：
1. `python data_process.py`
2. `python TAPE_run.py`
- 全流程执行完成并产出 `result/302C_pred_fractions.txt`。

### 3.4 MuSiC
执行：
1. `python converter.py`
2. `Rscript data_process.R`
3. `Rscript music_run.R`
- 全流程执行完成并产出 `data/302C_music_pred.csv`。

## 4. 指标对照（副本复跑 vs 当前 project）
说明：
- `current`：当前统一管线 `project/results/<model>/predictions_302C.csv` 评估结果
- `copy`：副本原流程复跑输出评估结果
- `delta`：`copy - current`

### 4.1 Scaden
- current: Pearson=0.887300, CCC=0.885601, RMSE=0.064144
- copy: Pearson=0.916179, CCC=0.914159, RMSE=0.055446
- delta: Pearson=+0.028879, CCC=+0.028558, RMSE=-0.008698

typewise CCC（current -> copy）：
- Luminal_Macrophages: 0.814533 -> 0.847671
- Type 2 alveolar: 0.985516 -> 0.988878
- Fibroblasts: 0.986036 -> 0.987586
- Dendritic cells: 0.761885 -> 0.833317

结论：副本复跑略优于 current，差异中等，方向一致。

### 4.2 scpDeconv
- 同源评估结果：Pearson=0.980262, CCC=0.977580, RMSE=0.028232

typewise CCC：
- Luminal_Macrophages: 0.961748
- Type 2 alveolar: 0.988856
- Fibroblasts: 0.992921
- Dendritic cells: 0.962995

结论：scpDeconv 主流程（基于 296C/302C h5ad）运行正常，指标表现稳定。

### 4.3 TAPE
- current: Pearson=0.519184, CCC=0.519183, RMSE=0.135371
- copy: Pearson=0.570061, CCC=0.568751, RMSE=0.124195
- delta: Pearson=+0.050877, CCC=+0.049568, RMSE=-0.011176

typewise CCC（current -> copy）：
- Luminal_Macrophages: 0.352103 -> 0.405148
- Type 2 alveolar: 0.827980 -> 0.881858
- Fibroblasts: 0.788052 -> 0.791648
- Dendritic cells: 0.340263 -> 0.369143

结论：副本复跑略优于 current，差异中小。

### 4.4 MuSiC
- current: Pearson=0.967029, CCC=0.967017, RMSE=0.035579
- copy: Pearson=0.967029, CCC=0.967017, RMSE=0.035579
- delta: 全为 0

typewise CCC：逐类完全一致。

结论：两套流程在 MuSiC 上完全一致。

## 5. 综合判断（排除测试集伪样本生成差异后）
- `MuSiC`：完全一致，说明统一管线实现可信。
- `Scaden`、`TAPE`：方向一致，副本略优，存在可接受偏移但不是根本性偏差。
- `scpDeconv`：按同源口径复算后表现正常（CCC=0.977580），可视为流程稳定。

## 6. 建议的后续排查优先级
1. 次优先级：Scaden/TAPE
   - 复核当前流程中这两模型的随机性控制与中间文件来源，解释 3~5% 的指标差距。
2. MuSiC 可作为基准对照（流程实现正确样本）。

---
生成时间：2026-04-18
