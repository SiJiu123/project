#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# setup_server_env.sh (Draft)
# Purpose:
#   Bootstrap Miniconda and create isolated runtime envs for this project on
#   legacy Linux servers.
#
# Usage (online):
#   bash deploy/setup_server_env.sh --mode online
#
# Usage (offline explicit lock files):
#   bash deploy/setup_server_env.sh --mode offline --lock-dir /path/to/locks
#
# Notes:
#   - This is a migration draft. Review paths/channels before production use.
#   - Prefer explicit lock files on old systems to avoid solver drift.
# -----------------------------------------------------------------------------

MODE="online"                        # online | offline
LOCK_DIR=""                          # required for offline
MINICONDA_DIR="${HOME}/miniconda3"
CONDA_SH="${MINICONDA_DIR}/etc/profile.d/conda.sh"
PKGS_CACHE_DIR="${HOME}/.conda/pkgs"
ENVS_DIR="${HOME}/.conda/envs"

# Channels and policy (strict priority helps avoid mixed ABI conflicts)
CHANNELS=("conda-forge" "defaults")

# Env names
ORCH_ENV="dzwdecode"
SCADEN_ENV="scaden_env"
SCP_ENV="scp_env"
TAPE_ENV="tape_env"
MUSIC_ENV="music_env"

# ------------------------------ arg parsing -----------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --lock-dir)
      LOCK_DIR="$2"
      shift 2
      ;;
    --miniconda-dir)
      MINICONDA_DIR="$2"
      CONDA_SH="${MINICONDA_DIR}/etc/profile.d/conda.sh"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

if [[ "${MODE}" == "offline" && -z "${LOCK_DIR}" ]]; then
  echo "ERROR: --lock-dir is required in offline mode"
  exit 1
fi

# ------------------------------ helpers ---------------------------------------
log() { echo "[$(date +'%F %T')] $*"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: missing command: $1"
    exit 1
  }
}

install_miniconda_if_needed() {
  if [[ -x "${MINICONDA_DIR}/bin/conda" ]]; then
    log "Miniconda already exists at ${MINICONDA_DIR}"
    return
  fi

  require_cmd curl
  require_cmd bash

  local installer="/tmp/miniconda.sh"
  local url="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"

  log "Downloading Miniconda installer"
  curl -L "${url}" -o "${installer}"

  log "Installing Miniconda to ${MINICONDA_DIR}"
  bash "${installer}" -b -p "${MINICONDA_DIR}"
}

init_conda() {
  # shellcheck source=/dev/null
  source "${CONDA_SH}"

  log "Configuring conda defaults"
  conda config --set channel_priority strict
  conda config --set auto_activate_base false
  conda config --set show_channel_urls true
  conda config --add pkgs_dirs "${PKGS_CACHE_DIR}" || true
  conda config --add envs_dirs "${ENVS_DIR}" || true

  for ch in "${CHANNELS[@]}"; do
    conda config --add channels "${ch}" || true
  done
}

create_env_online() {
  local env_name="$1"
  local yml_path="$2"

  if [[ ! -f "${yml_path}" ]]; then
    log "Skip ${env_name}: missing ${yml_path}"
    return
  fi

  log "Creating env ${env_name} from ${yml_path}"
  conda env remove -n "${env_name}" -y >/dev/null 2>&1 || true
  conda env create -n "${env_name}" -f "${yml_path}"
}

create_env_offline() {
  local env_name="$1"
  local lock_file="$2"

  if [[ ! -f "${lock_file}" ]]; then
    log "Skip ${env_name}: missing ${lock_file}"
    return
  fi

  log "Creating env ${env_name} from explicit lock ${lock_file}"
  conda env remove -n "${env_name}" -y >/dev/null 2>&1 || true
  conda create -n "${env_name}" --file "${lock_file}" -y
}

verify_env() {
  local env_name="$1"
  log "Verifying env: ${env_name}"
  conda run -n "${env_name}" python -V || true
}

# ------------------------------ preflight -------------------------------------
log "Running preflight checks"
require_cmd uname
require_cmd awk
require_cmd grep

log "Kernel: $(uname -srmo)"
if command -v ldd >/dev/null 2>&1; then
  log "GLIBC: $(ldd --version | head -n 1)"
fi
if command -v nvidia-smi >/dev/null 2>&1; then
  log "GPU: $(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -n 1)"
else
  log "GPU: nvidia-smi not found (CPU mode or missing driver)"
fi

# ------------------------------ main ------------------------------------------
install_miniconda_if_needed
init_conda

if [[ "${MODE}" == "online" ]]; then
  create_env_online "${ORCH_ENV}"   "deploy/envs/orchestrator.environment.yml"
  create_env_online "${SCADEN_ENV}" "deploy/envs/scaden.environment.yml"
  create_env_online "${SCP_ENV}"    "deploy/envs/scpdeconv.environment.yml"
  create_env_online "${TAPE_ENV}"   "deploy/envs/tape.environment.yml"
  create_env_online "${MUSIC_ENV}"  "deploy/envs/music.environment.yml"
else
  create_env_offline "${ORCH_ENV}"   "${LOCK_DIR}/orchestrator.explicit.txt"
  create_env_offline "${SCADEN_ENV}" "${LOCK_DIR}/scaden.explicit.txt"
  create_env_offline "${SCP_ENV}"    "${LOCK_DIR}/scpdeconv.explicit.txt"
  create_env_offline "${TAPE_ENV}"   "${LOCK_DIR}/tape.explicit.txt"
  create_env_offline "${MUSIC_ENV}"  "${LOCK_DIR}/music.explicit.txt"
fi

verify_env "${ORCH_ENV}"
verify_env "${SCADEN_ENV}"
verify_env "${SCP_ENV}"
verify_env "${TAPE_ENV}"
verify_env "${MUSIC_ENV}"

log "Done. Next: run project smoke tests in each env."
