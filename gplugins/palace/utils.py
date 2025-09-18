"""Utilities for Palace execution."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def find_palace_executable() -> str | None:
    """Find Palace executable in various locations.
    
    Returns:
        Path to palace executable, or None if not found.
    """
    # First try to find palace in PATH
    palace = shutil.which("palace")
    if palace:
        return palace
    
    # Check if we're in a CI environment with Apptainer container
    if "GITHUB_WORKSPACE" in os.environ:
        # Look for palace.sif in GITHUB_WORKSPACE
        workspace = Path(os.environ["GITHUB_WORKSPACE"])
        palace_sif = workspace / "palace.sif"
        if palace_sif.exists():
            # Check if apptainer/singularity is available
            for container_cmd in ["apptainer", "singularity"]:
                if shutil.which(container_cmd):
                    # Create a temporary script to run palace via container
                    palace_script = workspace / "palace_runner.sh"
                    palace_script.write_text(
                        f'#!/bin/bash\nexec {container_cmd} run "{palace_sif}" "$@"\n'
                    )
                    palace_script.chmod(0o755)
                    return str(palace_script)
    
    # Check common container locations
    for sif_path in [
        Path.home() / "palace.sif",
        Path("/opt/palace.sif"),
        Path("/app/palace.sif"),
    ]:
        if sif_path.exists():
            # Try apptainer first, then singularity
            for container_cmd in ["apptainer", "singularity"]:
                if shutil.which(container_cmd):
                    # Create a temporary script to run palace via container
                    script_dir = Path.home() / ".local" / "bin"
                    script_dir.mkdir(parents=True, exist_ok=True)
                    palace_script = script_dir / "palace_apptainer"
                    
                    palace_script.write_text(
                        f'#!/bin/bash\nexec {container_cmd} run "{sif_path}" "$@"\n'
                    )
                    palace_script.chmod(0o755)
                    return str(palace_script)
    
    return None


def run_palace_command(
    command: list[str],
    cwd: Path | str | None = None,
    capture_output: bool = True,
    text: bool = True,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a palace command, automatically detecting the correct executable.
    
    Args:
        command: Command list where the first element should be "palace"
        cwd: Working directory
        capture_output: Whether to capture stdout/stderr
        text: Whether to use text mode
        **kwargs: Additional arguments to subprocess.run
    
    Returns:
        subprocess.CompletedProcess result
        
    Raises:
        RuntimeError: If palace is not found or execution fails
    """
    palace_exe = find_palace_executable()
    if palace_exe is None:
        raise RuntimeError(
            "palace not found. Make sure it is available in your PATH, "
            "via Spack, or via an Apptainer/Singularity container."
        )
    
    # Replace "palace" with the actual executable path
    full_command = [palace_exe] + command[1:]
    
    return subprocess.run(
        full_command,
        cwd=cwd,
        capture_output=capture_output,
        text=text,
        **kwargs,
    )