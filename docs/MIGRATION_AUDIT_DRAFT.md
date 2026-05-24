# Linux Migration Audit Draft

## Goal
Migrate current human_lung workflow from Windows development to legacy Linux production servers without code changes in this phase.

## 1. Conda Environment Migration Design

### 1.1 Environment split
Use isolated envs instead of one monolithic env:
- orchestrator env: run_pipeline, metrics, plotting
- scaden env
- scpDeconv env
- tape env
- music env (R + Bioc stack)

### 1.2 GLIBC/CUDA compatibility strategy
- Build/lock envs on a machine with same or older OS/glibc than production.
- Use strict channel priority and fixed channels.
- Pin key ABI-sensitive dependencies: python, pytorch/tensorflow, cudatoolkit, r-base.
- Prefer explicit lock files (`conda list --explicit`) for production recreation.
- Keep online solve only for development; use explicit files for production/offline.

### 1.3 File artifacts
- Human-readable: `deploy/envs/*.environment.yml`
- Production lock: `deploy/locks/*.explicit.txt`

### 1.4 Automation script draft
- `deploy/setup_server_env.sh`
- Supports:
  - online creation from yml
  - offline creation from explicit lock files
  - Miniconda bootstrap
  - preflight checks (kernel/glibc/nvidia)

## 2. Env Variable & Config Decoupling Design

### 2.1 .env template
Created: `.env.example` with
- DATA_PATH/WORK_DIR/RESULTS_DIR/MODELS_DIR
- env names
- rebuild policy and pseudobulk policy
- conda executable hooks (`CONDA_EXE`/`CONDA_SH`/`CONDA_BAT`)

### 2.2 config.py adaptation plan (proposal)
Current high-risk coupling:
- Windows fixed conda path in `config.py` (`CONDA_BAT = C:\\...\\conda.bat`)

Proposed behavior:
- detect platform via `platform.system()`
- resolve paths from env vars first, fallback to defaults
- use `os.pathsep` for PATH separators
- on Linux prefer `conda run` or sourced `conda.sh`
- keep backward compatibility for Windows developers

## 3. Cross-platform Cleanup Plan

### 3.1 Hardcoded/Windows-coupled findings
- Windows conda path in `config.py`
- README uses Windows PowerShell executable forms (`& "C:\\...\\python.exe" ...`)
- one absolute Windows data path in `data/human_lung/split_h5ad_by_donor.py`

### 3.2 Path refactor scope (pathlib-first)
Priority A (our code):
- `pipeline/*`, `scripts/*`, wrappers under `models/*` maintained by this repo

Priority B (third-party vendored source):
- keep minimal patching only when required for server runtime

### 3.3 Shell portability
- Replace PowerShell-centric examples with dual examples:
  - Bash: `python run_pipeline.py MODEL=... STAGES=...`
  - PowerShell: keep existing for Windows users
- Add Linux launcher draft later (`deploy/run_pipeline.sh`)

## 4. Server-side Audit Checklist (collect before implementation)

### 4.1 OS and libc
```bash
cat /etc/os-release
uname -a
ldd --version
strings /lib64/libstdc++.so.6 | grep GLIBCXX | tail
```

### 4.2 GPU/CUDA
```bash
nvidia-smi
nvcc --version
cat /proc/driver/nvidia/version
```

### 4.3 Python/Conda/R
```bash
which python && python -V
which conda && conda -V
conda info
conda config --show channels
R --version
```

### 4.4 Build tools
```bash
gcc --version
g++ --version
make --version
cmake --version
```

### 4.5 Resource/network/permission
```bash
df -h
df -i
```
And report:
- outbound access to `repo.anaconda.com` and `conda-forge`
- sudo availability
- writable install dirs for conda/envs/data/logs

## 5. Next Step (after your confirmation)
- Produce first batch of version-pinned environment yml files.
- Add Linux launcher and update README with dual-shell commands.
- Implement config.py env-decoupling with backward-compatible defaults.
