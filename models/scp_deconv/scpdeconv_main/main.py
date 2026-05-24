import os
import sys
# sys.path.append('/apdcephfs/private_gelseywang/scDeconvolution/scpDeconv')
# os.chdir('/apdcephfs/private_gelseywang/scDeconvolution/Script/git/scpDeconv')
import argparse
import options
from model.refer_mixup import *
from model.AEimpute_model import *
from model.DANN_model import *
from model.utils import *

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", type=str, default='murine_cellline', help='The name of benchmarking datasets')
parser.add_argument("--data_dir", type=str, default=None, help='Override input data directory')
parser.add_argument("--result_dir", type=str, default=None, help='Override output directory')
parser.add_argument("--reference_id", type=str, default="296C", help='Reference/train dataset id')
parser.add_argument("--bulk_id", type=str, default="302C", help='Target/test dataset id')
parser.add_argument("--cell_type_column", type=str, default="CellType", help='Cell type column in h5ad obs')
parser.add_argument("--cell_types", type=str, default="", help='Comma-separated cell types')
parser.add_argument("--target_type", type=str, default="", help='Target mode: simulated or real')
parser.add_argument("--target_dataset_name", type=str, default="", help='Override target dataset filename or path')
parser.add_argument("--target_metadata_name", type=str, default="", help='Optional target metadata filename for csv input')
args = parser.parse_args()

def main():
    dataset = args.dataset
    ### Start Running scpDeconv ###
    print("------Start Running scpDeconv------")
    opt = options.get_option_list(
        dataset=dataset,
        data_dir=args.data_dir,
        result_dir=args.result_dir,
        reference_id=args.reference_id,
        bulk_id=args.bulk_id,
        cell_type_column=args.cell_type_column,
        cell_types=[x for x in args.cell_types.split(",") if x],
        target_type=args.target_type if args.target_type else None,
        target_dataset_name=args.target_dataset_name if args.target_dataset_name else None,
        target_metadata_name=args.target_metadata_name if args.target_metadata_name else None,
    )
    os.makedirs(opt['SaveResultsDir'], exist_ok=True)

    ### Run Stage 1 ###
    print("------Start Running Stage 1 : Mixup reference------")
    model_mx = ReferMixup(opt)
    source_data, target_data = model_mx.mixup()
    print("The dim of source data is :")
    print(source_data.shape)
    print("The dim of target data is :")
    print(target_data.shape)
    print("Stage 1 : Mixup finished!")

    ### Run Stage 2 ###
    print("------Start Running Stage 2 : Training AEimpute model------")
    model_im = AEimpute(opt)
    source_recon_data = model_im.train(source_data, target_data)
    print("Stage 2 : AEimpute model training finished!")

    ### Run Stage 3 ###
    print("------Start Running Stage 3 : Training DANN model------")
    model_da = DANN(opt)
    model_da.train(source_recon_data, target_data) 
    print("Stage 3 : DANN model training finished!")

    ### Run Stage 4 ###
    print("------Start Running Stage 4 : Inference for target data------")
    if opt['target_type'] in ("simulated", "external_simulated"):
        final_preds_target, ground_truth_target = model_da.prediction()
        SavePredPlot(opt['SaveResultsDir'], final_preds_target, ground_truth_target)
        final_preds_target.to_csv(os.path.join(opt['SaveResultsDir'], "target_predicted_fractions.csv"))
        ground_truth_target.to_csv(os.path.join(opt['SaveResultsDir'], "target_gt_fractions.csv")) #改

    elif opt['target_type'] == "real":
        final_preds_target, _ = model_da.prediction()
        final_preds_target.to_csv(os.path.join(opt['SaveResultsDir'], "target_predicted_fractions.csv"))
    print("Stage 4 : Inference for target data finished!")

if __name__ == "__main__":
    main()
