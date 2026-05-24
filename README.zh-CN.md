# 统一去卷积流水线

这个项目提供一个统一入口，用同一套标准数据格式运行和评估多个去卷积模型：

- `scaden`
- `scpdeconv`
- `tape`
- `music`
- `cibersortx`：外部官网运行，本地只负责准备输入和评估结果

## 1. 项目结构

核心文件和目录：

- `config.py`：全局默认配置
- `run_pipeline.py`：统一运行入口
- `pipeline/`：调度器、模型适配器、公共工具
- `data/standard/<DATASET>/`：标准化后的数据目录
- `utils/data_factory.py`：从 train/test h5ad 生成标准输入和 pseudo-bulk
- `work/<DATASET>/`：各模型中间文件
- `results/<DATASET>/`：统一评估输出
- `save_models/<DATASET>/`：模型权重
- `scripts/`：辅助脚本
- `eval_only.py`：旧版独立评估脚本，适合只评估已有预测文件的场景

## 2. 数据入口

当前主流程不负责从原始大 h5ad 中按 donor 划分数据。你需要先在流程外准备好：

```text
data/<DATASET>/<TRAIN_ID>_train.h5ad
data/<DATASET>/<TEST_ID>_test.h5ad
```

也可以直接放在标准目录：

```text
data/standard/<DATASET>/<TRAIN_ID>_train.h5ad
data/standard/<DATASET>/<TEST_ID>_test.h5ad
```

h5ad 要求：

- `.X` 是细胞 x 基因表达矩阵
- `obs_names` 是细胞 ID
- `var_names` 是基因名
- `obs` 中包含细胞类型列
- 细胞类型列默认自动识别 `CellType` 或 `Celltype`
- 如果 train/test 的细胞类型列名不同，分别用 `TRAIN_CELL_TYPE_COLUMN=<列名>` 和 `TEST_CELL_TYPE_COLUMN=<列名>` 指定
- 如果要运行 MuSiC，训练集 h5ad 的 `obs` 还需要包含 sample/donor 分组列；用 `TRAIN_SAMPLE_COLUMN=<列名>` 指定

## 3. 标准化输出

运行 `prepare` 后，会在：

```text
data/standard/<DATASET>/
```

生成：

```text
<TRAIN_ID>_counts.txt
<TRAIN_ID>_celltypes.txt
<TEST_ID>_counts.txt
<TEST_ID>_celltypes.txt
<TEST_ID>_bulk_X.txt
<TEST_ID>_bulk_obs.txt
```

同时会生成 pseudo-bulk 方法变体：

```text
<TEST_ID>_bulk_X.uniform.txt
<TEST_ID>_bulk_obs.uniform.txt
<TEST_ID>_bulk_X.dirichlet.txt
<TEST_ID>_bulk_obs.dirichlet.txt
```

以及 CIBERSORTx 等外部流程会用到的文件：

```text
<TRAIN_ID>_counts_transposed.txt
<TRAIN_ID>_class_labels.txt
```

## 4. 常用参数

这些参数可以在 `config.py` 中修改，也可以在命令行中覆盖：

```text
MODEL=scaden | scpdeconv | tape | music | cibersortx | all
STAGES=prepare,run,eval
DATASET=<数据集名称>
TRAIN_ID=<训练集 ID>
TEST_ID=<测试集 ID>
TRAIN_CELL_TYPE_COLUMN=<训练集 h5ad obs 中的细胞类型列名>
TEST_CELL_TYPE_COLUMN=<测试集 h5ad obs 中的细胞类型列名>
TRAIN_SAMPLE_COLUMN=<训练集 h5ad obs 中的 sample/donor 列名>
TEST_SAMPLE_COLUMN=<测试集 h5ad obs 中的 sample/donor 列名>
CELL_TYPES=auto | <逗号分隔的细胞类型列表>
STANDARD_REBUILD_MODE=always | if_missing | never
```

`MODEL` 也支持逗号分隔多选，例如：
```text
MODEL=scaden,tape,scpdeconv
```

旧参数 `REFERENCE_ID` 和 `BULK_ID` 仍然兼容，但新命令建议使用 `TRAIN_ID` 和 `TEST_ID`。

`CELL_TYPES=auto` 会从测试集或已有 `<TEST_ID>_bulk_obs.txt` 中推断细胞类型顺序。

`TRAIN_SAMPLE_COLUMN` 主要供 MuSiC 使用。MuSiC 至少需要两个 sample/donor 分组；如果训练集只有一个分组，MuSiC 会明确报错，建议跳过 `MODEL=music` 或换成包含多个 donor/sample 的训练集。

建议把每个数据集固定的列名写在 `config.py` 的 `DATASET_CONFIGS` 中。命令行里的 `TRAIN_CELL_TYPE_COLUMN`、`TEST_CELL_TYPE_COLUMN`、`TRAIN_SAMPLE_COLUMN`、`TEST_SAMPLE_COLUMN` 仍然可以作为临时覆盖。

## 5. 新数据集全流程示例

假设你已经准备好：

```text
data/my_dataset/A_train.h5ad
data/my_dataset/B_test.h5ad
```

并且细胞类型列叫 `cell_type`。

先跑标准化，确认数据能接入：

```powershell
& "C:\Users\Lenovo\miniconda3\envs\dzwdecode\python.exe" run_pipeline.py `
  MODEL=scaden `
  STAGES=prepare `
  DATASET=my_dataset `
  TRAIN_ID=A `
  TEST_ID=B `
  CELL_TYPES=auto `
  STANDARD_REBUILD_MODE=if_missing
```

再跑一个本地模型的完整链路：

```powershell
& "C:\Users\Lenovo\miniconda3\envs\dzwdecode\python.exe" run_pipeline.py `
  MODEL=scaden `
  STAGES=prepare,run,eval `
  DATASET=my_dataset `
  TRAIN_ID=A `
  TEST_ID=B `
  CELL_TYPES=auto `
  STANDARD_REBUILD_MODE=if_missing
```

确认单模型跑通后，可以跑全部模型。`MODEL=all` 会包含 CIBERSORTx；如果还没有放入官网预测文件，CIBERSORTx 的 `eval` 会自动跳过。

```powershell
& "C:\Users\Lenovo\miniconda3\envs\dzwdecode\python.exe" run_pipeline.py `
  MODEL=all `
  STAGES=prepare,run,eval `
  DATASET=my_dataset `
  TRAIN_ID=A `
  TEST_ID=B `
  CELL_TYPES=auto `
  STANDARD_REBUILD_MODE=if_missing
```

如果细胞类型列本来就叫 `CellType` 或 `Celltype`，可以写：

```text
TRAIN_CELL_TYPE_COLUMN=cell_type
TEST_CELL_TYPE_COLUMN=CellType
```

## 6. CIBERSORTx 官网流程

CIBERSORTx 模型不在本地运行。项目中对它的处理是：

- `prepare`：生成官网需要的输入文件
- `run`：什么都不做
- `eval`：读取官网跑完后放回本地的预测结果

先准备官网输入：

```powershell
& "C:\Users\Lenovo\miniconda3\envs\dzwdecode\python.exe" run_pipeline.py `
  MODEL=cibersortx `
  STAGES=prepare `
  DATASET=my_dataset `
  TRAIN_ID=A `
  TEST_ID=B `
  CELL_TYPES=auto
```

然后把官网输出整理并放到：

```text
work/my_dataset/cibersortx/predictions_B.csv
```

其中 `B` 是你的 `TEST_ID`。

最后只跑评估：

```powershell
& "C:\Users\Lenovo\miniconda3\envs\dzwdecode\python.exe" run_pipeline.py `
  MODEL=cibersortx `
  STAGES=eval `
  DATASET=my_dataset `
  TRAIN_ID=A `
  TEST_ID=B `
  CELL_TYPES=auto
```

## 7. 评估输出

每个模型会输出：

```text
results/<DATASET>/<model>/predictions_<TEST_ID>.csv
results/<DATASET>/<model>/metrics_summary.csv
results/<DATASET>/<model>/typewise_ccc.csv
results/<DATASET>/<model>/evaluation.json
```

全局输出：

```text
results/<DATASET>/run_report.json
results/<DATASET>/leaderboard.md
results/<DATASET>/typewise_ccc_boxplot.png
results/<DATASET>/typewise_ccc_merged.csv
```

不同数据集会写入不同目录，例如：

```text
results/<DATASET>/<model>/
work/<DATASET>/<model>/
save_models/<DATASET>/
```

## 8. 注意事项

- 上游第三方模型源码目录默认视为只读，不建议直接修改：
  - `models/scaden/scaden-master`
  - `models/tape/tape_main`
  - `models/music/music_master`
  - `models/scp_deconv/scpdeconv_main`
- 新数据集需要先在外部完成 train/test 划分。
- 如果只想评估已有预测文件，可以用 `MODEL=<model> STAGES=eval`。
- `eval_only.py` 是旧版独立评估脚本，当前主流程推荐优先使用 `run_pipeline.py STAGES=eval`。
