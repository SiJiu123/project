from pipeline.adapters.cibersortx_adapter import CIBERSORTxAdapter
from pipeline.adapters.demo_deconv_adapter import ProtoDeconvAdapter, SupDeconvAdapter
from pipeline.adapters.music_adapter import MuSiCAdapter
from pipeline.adapters.scaden_adapter import ScadenAdapter
from pipeline.adapters.scpdeconv_adapter import ScpDeconvAdapter
from pipeline.adapters.tape_adapter import TAPEAdapter


REGISTRY = {
    "scaden": ScadenAdapter,
    "scpdeconv": ScpDeconvAdapter,
    "tape": TAPEAdapter,
    "music": MuSiCAdapter,
    "cibersortx": CIBERSORTxAdapter,
    "supdeconv": SupDeconvAdapter,
    "protodeconv": ProtoDeconvAdapter,
}


def normalize_model_name(model_name: str) -> str:
    name = model_name.strip().lower()
    aliases = {
        "scpdeconv": "scpdeconv",
        "scp": "scpdeconv",
        "tape": "tape",
        "music": "music",
        "musicr": "music",
        "scaden": "scaden",
        "cibersortx": "cibersortx",
        "cibersort": "cibersortx",
        "csx": "cibersortx",
        "demo1": "supdeconv",
        "supdeconv": "supdeconv",
        "superviseddeconv": "supdeconv",
        "demo2": "protodeconv",
        "protodeconv": "protodeconv",
        "prototype": "protodeconv",
    }
    return aliases.get(name, name)


def parse_model_names(model_text: str):
    raw_items = [item.strip() for item in str(model_text).split(",") if item.strip()]
    normalized = [normalize_model_name(item) for item in raw_items]
    if "all" in normalized:
        return list(REGISTRY.keys())

    seen = []
    for item in normalized:
        if item not in REGISTRY:
            raise ValueError(f"Unsupported model: {item}")
        if item not in seen:
            seen.append(item)
    return seen
