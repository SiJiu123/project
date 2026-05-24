import argparse
import random
from pathlib import Path

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--cells")
    parser.add_argument("--n_samples", type=int, default=32000)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--unknown", nargs="*")
    parser.add_argument("--prefix", default="simulated")
    parser.add_argument("--data-format", default="txt")
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main():
    args = parse_args()
    np.random.seed(args.seed)
    random.seed(args.seed)

    from scaden.simulate import simulation

    simulation(
        simulate_dir=str(Path(args.out)),
        data_dir=str(Path(args.data)),
        sample_size=int(args.cells) if args.cells else 100,
        num_samples=args.n_samples,
        pattern=args.pattern,
        unknown_celltypes=args.unknown if args.unknown else ["unknown"],
        out_prefix=args.prefix,
        fmt=args.data_format,
    )


if __name__ == "__main__":
    main()
