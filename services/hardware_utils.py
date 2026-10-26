"""
services/hardware_utils.py — Host Hardware & Memory Constraint Utilities.

Provides reliable memory inspection across cloud containers (Render, Docker, Kubernetes)
and host operating systems to prevent catastrophic uncatchable SIGKILL / OOM terminations.
"""

import os
from pathlib import Path
from typing import Optional, Tuple


def get_system_memory_mb() -> Optional[int]:
    """Return total physical RAM or container cgroup memory limit in MB."""
    # 1. Linux cgroup v2 & v1 memory limits (crucial for Render / Docker containers)
    for cgroup_path in (
        "/sys/fs/cgroup/memory.max",                    # cgroup v2
        "/sys/fs/cgroup/memory/memory.limit_in_bytes",  # cgroup v1
    ):
        p = Path(cgroup_path)
        if p.is_file():
            try:
                val = p.read_text().strip()
                if val and val != "max":
                    bytes_val = int(val)
                    # Exclude unlimited limits (e.g., 2**63 - 1 or > 1TB)
                    if 0 < bytes_val < 1_000_000_000_000:
                        return int(bytes_val / (1024 * 1024))
            except Exception:
                pass

    # 2. Linux /proc/meminfo
    proc_mem = Path("/proc/meminfo")
    if proc_mem.is_file():
        try:
            for line in proc_mem.read_text().splitlines():
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    return int(int(parts[1]) / 1024)
        except Exception:
            pass

    # 3. os.sysconf (POSIX)
    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            if pages > 0 and page_size > 0:
                return int((pages * page_size) / (1024 * 1024))
        except Exception:
            pass

    # 4. psutil (Windows / cross-platform)
    try:
        import psutil
        return int(psutil.virtual_memory().total / (1024 * 1024))
    except Exception:
        pass

    return None


def is_inference_memory_sufficient(
    min_mb: int = 1500,
    model_name: str = "Neural Model",
) -> Tuple[bool, Optional[int], str]:
    """Check if host memory is sufficient to allocate model weights without container OOM termination.

    Returns (is_sufficient, actual_mb, message).
    """
    if os.getenv("ALLOW_UNSAFE_INFERENCE", "").lower() in ("1", "true", "yes"):
        return True, get_system_memory_mb(), "Unsafe memory allocation allowed by configuration."

    actual_mb = get_system_memory_mb()
    if actual_mb is None:
        # Unable to determine; allow inference to proceed
        return True, None, "Host memory limit could not be determined."

    if actual_mb < min_mb:
        msg = (
            f"Host hardware limitation: Host memory is {actual_mb} MB, which is below the minimum "
            f"{min_mb} MB required to allocate {model_name} weights without triggering container "
            "out-of-memory termination. Run CrimeVision AI locally or deploy on an instance with at "
            "least 2GB-4GB RAM."
        )
        return False, actual_mb, msg

    return True, actual_mb, f"Host memory ({actual_mb} MB) is sufficient for {model_name}."
