import anndata as ad
import pandas as pd
import os

STANDARD_DIR = "../../data/standard/human_lung"

os.makedirs(STANDARD_DIR, exist_ok=True)
adata = ad.read_h5ad(f"{STANDARD_DIR}/302C.h5ad")

bulk_df = adata.obs
bulk_df = bulk_df.drop(columns=['ds'])

bulk_df.index.name = None
bulk_df.columns.name = None

bulk_df.to_csv(f"{STANDARD_DIR}/302C_bulk_obs.txt", sep="\t", index=True)

print("✅ 已生成 样本x细胞 格式的矩阵。")