import os
from pathlib import Path
import sys

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from TAPE import Deconvolution
import pandas as pd

STANDARD_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../../data/standard/human_lung")
WORK_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("../../work/tape")
REFERENCE_ID = sys.argv[3] if len(sys.argv) > 3 else "296C"
BULK_ID = sys.argv[4] if len(sys.argv) > 4 else "302C"
SEED = int(sys.argv[5]) if len(sys.argv) > 5 else 1
WORK_DIR.mkdir(parents=True, exist_ok=True)

# Runtime knobs for low-memory machines.
BATCH_SIZE = int(os.environ.get("TAPE_BATCH_SIZE", "128"))
EPOCHS = int(os.environ.get("TAPE_EPOCHS", "128"))

sc_ref = pd.read_csv(WORK_DIR / f"{REFERENCE_ID}_sc_counts.txt", sep='\t', index_col=0)

bulkdata = pd.read_csv(STANDARD_DIR / f"{BULK_ID}_bulk_X.txt", sep='\t', index_col=0)

bulkdata = bulkdata.T

SignatureMatrix, CellFractionPrediction = \
 _ , pred = Deconvolution(sc_ref, bulkdata, sep='\t', scaler='mms',
                  datatype='counts', genelenfile='tape_main/data/GeneLength.txt',
                  mode='overall', adaptive=True, variance_threshold=0.98,
                  save_model_name='TAPE_human_lung',
                  batch_size=BATCH_SIZE, epochs=EPOCHS, seed=SEED)

pred.to_csv(WORK_DIR / f'{BULK_ID}_pred_fractions.txt', sep='\t', index=True)
