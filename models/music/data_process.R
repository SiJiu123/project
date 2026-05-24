library(SingleCellExperiment)

args <- commandArgs(trailingOnly = TRUE)
standard_dir <- if (length(args) >= 1) args[[1]] else "../../data/standard/human_lung"
work_dir <- if (length(args) >= 2) args[[2]] else "../../work/music"
reference_id <- if (length(args) >= 3) args[[3]] else "296C"
bulk_id <- if (length(args) >= 4) args[[4]] else "302C"
if (!dir.exists(work_dir)) {
    dir.create(work_dir, recursive = TRUE)
}

# 1. 读取数据
X <- read.table(file.path(work_dir, paste0(reference_id, "_sc_X.txt")), header = TRUE, sep = "\t", row.names = 1, check.names = FALSE)
meta <- read.table(file.path(work_dir, paste0(reference_id, "_sc_obs.txt")), header = TRUE, sep = "\t", row.names = 1, check.names = FALSE)

X <- t(X)

# 2. 确保对齐 (矩阵的列名 == 元数据的行名)
X <- X[, rownames(meta)]

# 3. 合成为“带注释”的对象
# 这里的 colData 就是所谓的“注释”
sc_sce <- SingleCellExperiment(
    assays = list(counts = as.matrix(X)),
    colData = meta
)

# 4. 保存为 rds 文件，这才是 MuSiC 真正想要的 sc.eset
saveRDS(sc_sce, file.path(work_dir, paste0(reference_id, "_counts.rds")))


bulk_data <- read.table(file.path(standard_dir, paste0(bulk_id, "_bulk_X.txt")), header = TRUE, row.names = 1, sep = "\t", check.names = FALSE)

# 2. 转换为 Matrix 格式（MuSiC 必须要求 Matrix，不能是 Dataframe）
bulk_matrix <- as.matrix(bulk_data)

# 3. 保存为 rds
saveRDS(bulk_matrix, file = file.path(work_dir, paste0(bulk_id, "_bulk_X.rds")))
