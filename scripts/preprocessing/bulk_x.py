import anndata as ad
import pandas as pd
import os

STANDARD_DIR = "../../data/standard/human_lung"

os.makedirs(STANDARD_DIR, exist_ok=True)
adata = ad.read_h5ad(f"{STANDARD_DIR}/302C.h5ad")

bulk_df = pd.DataFrame(
    adata.X.toarray() if hasattr(adata.X, 'toarray') else adata.X,
    index=adata.obs_names,
    columns=adata.var_names
).T
bulk_df.index.name = None
bulk_df.columns.name = None
# 2. 导出为制表符分隔的 txt 文件
# index=True 会保留左侧的基因名（gene0, gene1...）
bulk_df.to_csv(f"{STANDARD_DIR}/302C_bulk_X.txt", sep="\t", index=True)

print("✅ 已生成 基因x样本 格式的矩阵。")