"""gimp_bridge.py - GIMP Integration Module

Opens processed screenshots in GIMP for final human review.
Detects running GIMP instances and reuses them when possible.
Supports Windows, WSL2, and native Linux.
"""

import subprocess
import os
import sys
import time
import platform
import shutil

GIMP_EXE_WINDOWS = r"C:\Program Files\GIMP 2\bin\gimp-2.10.exe"


def _is_windows() -> bool:
    """Check if running on Windows (not WSL)."""
    return platform.system() == "Windows"


def _is_wsl() -> bool:
    """Check if running inside WSL."""
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def find_gimp() -> str:
    """Find GIMP executable path (cross-platform)."""
    if _is_windows():
        # Windows: check the well-known install path, then PATH
        if os.path.exists(GIMP_EXE_WINDOWS):
            return GIMP_EXE_WINDOWS
        for path_dir in os.environ.get('PATH', '').split(os.pathsep):
            for name in ('gimp-2.10.exe', 'gimp.exe'):
                candidate = os.path.join(path_dir, name)
                if os.path.exists(candidate):
                    return candidate
    else:
        # Linux / WSL: use shutil.which (respects PATH)
        for name in ('gimp', 'gimp-2.10'):
            path = shutil.which(name)
            if path:
                return path

    raise FileNotFoundError(
        "GIMP not found. "
        + ("Install from https://www.gimp.org/downloads/"
           if _is_windows()
           else "Install with: sudo apt install gimp")
    )


def is_gimp_running() -> bool:
    """Check if GIMP is already running."""
    if _is_windows():
        try:
            result = subprocess.run(
                ['powershell', '-Command',
                 'Get-Process -Name "gimp*" -ErrorAction SilentlyContinue '
                 '| Select-Object -First 1 Id'],
                capture_output=True, text=True, timeout=5
            )
            return bool(result.stdout.strip())
        except Exception:
            return False
    else:
        # Linux / WSL: use pgrep
        try:
            result = subprocess.run(
                ['pgrep', '-x', 'gimp'],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False


def get_gimp_pid() -> int | None:
    """Get PID of running GIMP instance."""
    if _is_windows():
        try:
            result = subprocess.run(
                ['powershell', '-Command',
                 '(Get-Process -Name "gimp*" -ErrorAction SilentlyContinue '
                 '| Select-Object -First 1).Id'],
                capture_output=True, text=True, timeout=5
            )
            pid_str = result.stdout.strip()
            return int(pid_str) if pid_str else None
        except Exception:
            return None
    else:
        try:
            result = subprocess.run(
                ['pgrep', '-x', 'gimp'],
                capture_output=True, text=True, timeout=5
            )
            pid_str = result.stdout.strip().split('\n')[0]
            return int(pid_str) if pid_str else None
        except Exception:
            return None


def open_in_gimp(image_paths: list[str], reuse_window: bool = True) -> bool:
    """
    Open one or more images in GIMP.

    Args:
        image_paths: List of absolute paths to image files
        reuse_window: If True, try to open in existing GIMP instance

    Returns:
        True if successful
    """
    gimp_exe = find_gimp()

    # Normalize paths
    abs_paths = [os.path.abspath(p) for p in image_paths]
    for p in abs_paths:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Image not found: {p}")

    if reuse_window and is_gimp_running():
        return _open_in_existing_gimp(gimp_exe, abs_paths)
    else:
        return _launch_new_gimp(gimp_exe, abs_paths)


def _open_in_existing_gimp(gimp_exe: str, image_paths: list[str]) -> bool:
    """Open images in an already-running GIMP instance using Script-Fu."""
    script_parts = []
    for path in image_paths:
        escaped_path = path.replace('\\', '\\\\') if _is_windows() else path
        script_parts.append(
            f'(gimp-file-load RUN-NONINTERACTIVE "{escaped_path}" "{os.path.basename(path)}")'
        )
        script_parts.append('(gimp-display-new (car (gimp-image-list)))')

    script = ' '.join(script_parts)

    try:
        result = subprocess.run(
            [gimp_exe, '-i', '-b', script, '-b', '(gimp-quit 0)'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return _launch_new_gimp(gimp_exe, image_paths)
        return True
    except subprocess.TimeoutExpired:
        return _launch_new_gimp(gimp_exe, image_paths)
    except Exception as e:
        print(f"Warning: Script-Fu approach failed ({e}), launching new GIMP", file=sys.stderr)
        return _launch_new_gimp(gimp_exe, image_paths)


def _launch_new_gimp(gimp_exe: str, image_paths: list[str]) -> bool:
    """Launch a new GIMP instance with images."""
    cmd = [gimp_exe] + image_paths
    try:
        popen_kwargs = dict(
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if _is_windows():
            popen_kwargs['creationflags'] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            popen_kwargs['start_new_session'] = True

        subprocess.Popen(cmd, **popen_kwargs)
        time.sleep(2)
        return True
    except Exception as e:
        print(f"Error launching GIMP: {e}", file=sys.stderr)
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python gimp_bridge.py <image_path> [image_path2 ...]")
        sys.exit(1)

    paths = sys.argv[1:]
    running = is_gimp_running()
    print(f"GIMP running: {running}")
    print(f"Opening {len(paths)} image(s)...")
    success = open_in_gimp(paths, reuse_window=True)
    print(f"{'Success' if success else 'Failed'}")
