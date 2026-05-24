# 这里导出的counts第一列是barcode
import anndata as ad
import pandas as pd
import os

STANDARD_DIR = "../../data/standard/human_lung"

# 1. 创建目录
os.makedirs(STANDARD_DIR, exist_ok=True)

# 2. 读取数据
adata_train = ad.read_h5ad(f"{STANDARD_DIR}/296C_train.h5ad")

# 确保是原始计数
if adata_train.raw is not None:
    adata_train = adata_train.raw.to_adata()

# 3. 导出 counts (保持：细胞在行，基因在列)
counts = pd.DataFrame(
    adata_train.X.toarray() if hasattr(adata_train.X, 'toarray') else adata_train.X,
    index=adata_train.obs_names,
    columns=adata_train.var_names
)

counts.to_csv(f"{STANDARD_DIR}/296C_counts.txt", sep="\t", index=True, index_label='')

# 4. 导出 celltypes (不含表头和索引)
# 这里的逻辑没问题，保持原样
adata_train.obs['CellType'].to_csv(f"{STANDARD_DIR}/296C_celltypes.txt", sep="\t", index=False)

print("✅ 296C 训练参考集导出完成。")



adata_test = ad.read_h5ad(f"{STANDARD_DIR}/302C_test.h5ad")

# 确保是原始计数
if adata_test.raw is not None:
    adata_test = adata_test.raw.to_adata()

# 3. 导出 counts (保持：细胞在行，基因在列)
counts = pd.DataFrame(
    adata_test.X.toarray() if hasattr(adata_test.X, 'toarray') else adata_test.X,
    index=adata_test.obs_names,
    columns=adata_test.var_names
)

counts.to_csv(f"{STANDARD_DIR}/302C_counts.txt", sep="\t", index=True, index_label='')

# 4. 导出 celltypes (不含表头和索引)
# 这里的逻辑没问题，保持原样
adata_test.obs['CellType'].to_csv(f"{STANDARD_DIR}/302C_celltypes.txt", sep="\t", index=False)

print("✅ 302C 训练参考集导出完成。")




# import pandas as pd

# # 读取文件，指定分隔符为制表符
# df = pd.read_csv(f"{STANDARD_DIR}/296C_counts.txt", sep="\t")

# # 重命名列名
# df.columns = ['Celltype' if x == 'CellType' else x for x in df.columns]

# # 保存回去，不保存索引
# df.to_csv(f"{STANDARD_DIR}/296C_counts.txt", sep="\t", index=False)
# print("修改完成！")


# # 读取文件，指定分隔符为制表符
# df = pd.read_csv(f"{STANDARD_DIR}/296C_celltypes.txt", sep="\t")

# # 重命名列名
# df.columns = ['Celltype']

# # 保存回去，不保存索引
# df.to_csv(f"{STANDARD_DIR}/296C_celltypes.txt", sep="\t", index=False)
# print("修改完成！")


# # 读取文件，指定分隔符为制表符
# df = pd.read_csv(f"{STANDARD_DIR}/302C_counts.txt", sep="\t")

# # 重命名列名
# df.columns = ['Celltype' if x == 'CellType' else x for x in df.columns]

# # 保存回去，不保存索引
# df.to_csv(f"{STANDARD_DIR}/302C_counts.txt", sep="\t", index=False)
# print("修改完成！")


# # 读取文件，指定分隔符为制表符
# df = pd.read_csv(f"{STANDARD_DIR}/302C_celltypes.txt", sep="\t")

# # 重命名列名
# df.columns = ['Celltype']

# # 保存回去，不保存索引
# df.to_csv(f"{STANDARD_DIR}/302C_celltypes.txt", sep="\t", index=False)
# print("修改完成！")

