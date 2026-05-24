import shutil
import subprocess
from pathlib import Path
from typing import Optional, Sequence


def _run_streaming(command, cwd: Optional[Path] = None, shell: bool = False) -> None:
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    chunks = []
    assert process.stdout is not None
    while True:
        chunk = process.stdout.read(1)
        if not chunk and process.poll() is not None:
            break
        if chunk:
            print(chunk, end="", flush=True)
            chunks.append(chunk)

    process.wait()
    output = "".join(chunks)
    if process.returncode != 0:
        raise RuntimeError(output)


def check_executable(name: str) -> None:
    path_like = Path(name)
    if path_like.exists():
        return
    if shutil.which(name) is None:
        raise RuntimeError(f"Executable not found in PATH: {name}")


def run_command(command: Sequence[str], cwd: Optional[Path] = None) -> None:
    try:
        _run_streaming(command=command, cwd=cwd, shell=False)
    except RuntimeError as e:
        raise RuntimeError(
            "Command failed:\n"
            f"CMD: {' '.join(command)}\n"
            f"CWD: {cwd}\n"
            f"OUTPUT:\n{e}"
        ) from None


def run_shell(command: str, cwd: Optional[Path] = None) -> None:
    try:
        _run_streaming(command=command, cwd=cwd, shell=True)
    except RuntimeError as e:
        raise RuntimeError(
            "Shell command failed:\n"
            f"CMD: {command}\n"
            f"CWD: {cwd}\n"
            f"OUTPUT:\n{e}"
        ) from None


def run_in_conda_env(conda_bat: str, env_name: str, command: Sequence[str], cwd: Optional[Path] = None) -> None:
    cmd_text = subprocess.list2cmdline(list(command))
    shell_cmd = f'call "{conda_bat}" activate {env_name} && {cmd_text}'
    try:
        _run_streaming(command=shell_cmd, cwd=cwd, shell=True)
    except RuntimeError as e:
        raise RuntimeError(
            "Conda command failed:\n"
            f"CMD: {cmd_text}\n"
            f"ENV: {env_name}\n"
            f"CWD: {cwd}\n"
            f"OUTPUT:\n{e}"
        ) from None
