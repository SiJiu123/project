library(MuSiC)
library(Biobase)
library(SingleCellExperiment)

args <- commandArgs(trailingOnly = TRUE)
work_dir <- if (length(args) >= 1) args[[1]] else "../../work/music"
reference_id <- if (length(args) >= 2) args[[2]] else "296C"
bulk_id <- if (length(args) >= 3) args[[3]] else "302C"
cell_types <- if (length(args) >= 4 && nchar(args[[4]]) > 0) strsplit(args[[4]], ",", fixed = TRUE)[[1]] else NULL
sample_column <- if (length(args) >= 5) args[[5]] else "auto"

sc_eset <- readRDS(file.path(work_dir, paste0(reference_id, "_counts.rds")))
bulk_eset <- readRDS(file.path(work_dir, paste0(bulk_id, "_bulk_X.rds")))
if (!("Sample" %in% colnames(colData(sc_eset)))) {
    stop("MuSiC requires a Sample column in prepared SingleCellExperiment. Run prepare with SAMPLE_COLUMN=<column_name>.")
}
result <- music_prop(
    bulk.mtx = bulk_eset,
    sc.sce = sc_eset,
    cluster = "CellType",
    sample = "Sample",
    select.ct = cell_types,
    verbose = FALSE
)
names(result)

MuSiC <- result$Est.prop.weighted

head(MuSiC)

write.csv(MuSiC, file.path(work_dir, paste0(bulk_id, "_music_pred.csv")), row.names = TRUE, quote = FALSE)
