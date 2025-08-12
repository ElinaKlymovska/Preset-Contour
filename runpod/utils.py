"""
RunPod Utilities
Utility functions for RunPod operations
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from .manager import manager
from .config import config

logger = logging.getLogger(__name__)

def ensure_pod_running(auto_start: bool = False) -> bool:
    """Ensure pod is running and initialize manager context.

    Returns True only when an SSH connection is confirmed and
    manager.current_pod is populated (so downstream calls that
    require it do not fail).
    """
    # Fast path: if SSH works, also set current pod context
    if manager.test_ssh_connection():
        # Populate current pod context to satisfy manager.setup_workspace()
        manager.wait_for_pod_ready(timeout=30)
        return True

    if auto_start:
        logger.info("Pod not running, attempting to start...")
        if manager.start_pod():
            return manager.wait_for_pod_ready(timeout=300)
        return False

    return False

def upload_project_files(local_path: str = "./") -> bool:
    """Upload project files to RunPod by creating a compressed archive locally.

    Excludes common bulky or volatile folders/files and uses Python's tarfile
    module to reduce reliance on system tar, which may fail on some systems.
    """
    if not ensure_pod_running():
        logger.error("No running pod available")
        return False
    
    # Create a temporary archive
    import tempfile
    import tarfile
    from pathlib import Path as _Path

    try:
        base_path = _Path(local_path).resolve()
        if not base_path.exists():
            logger.error(f"Local path does not exist: {base_path}")
            return False

        with tempfile.NamedTemporaryFile(prefix="project_", suffix=".tar.gz", delete=False) as tmp:
            archive_name = tmp.name

        def _exclude(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
            name = tarinfo.name
            # Normalize path inside archive to be relative to base
            # Exclude typical large/irrelevant paths
            excluded = [
                ".git/", "node_modules/", "__pycache__/", ".mypy_cache/", ".pytest_cache/",
            ]
            for token in excluded:
                if token in name:
                    return None
            if name.endswith(".pyc") or name.endswith(".pyo"):
                return None
            return tarinfo

        with tarfile.open(archive_name, mode="w:gz") as tf:
            tf.add(str(base_path), arcname=base_path.name, filter=_exclude)

        # Upload archive
        success = manager.upload_file(archive_name, f"/workspace/{_Path(archive_name).name}")

        try:
            # Always attempt to remove local temp archive
            if os.path.exists(archive_name):
                os.remove(archive_name)
        except Exception:
            pass

        if not success:
            return False

        remote_archive = f"/workspace/{_Path(archive_name).name}"
        # Extract on RunPod and remove archive
        cmd = f"cd /workspace && tar -xzf '{remote_archive}' && rm -f '{remote_archive}'"
        ok, _, err = manager.execute_ssh_command(cmd)
        if ok:
            logger.info("Project files uploaded and extracted successfully")
            return True
        logger.error(f"Remote extraction failed: {err}")
        return False

    except Exception as e:
        logger.error(f"Error uploading project files: {e}")
        return False

def get_system_info() -> Dict[str, Any]:
    """Get system information from RunPod"""
    if not ensure_pod_running():
        return {"error": "No running pod available"}
    
    info = {}
    
    # GPU info
    success, stdout, stderr = manager.execute_ssh_command("nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader,nounits")
    if success and stdout.strip():
        gpu_info = stdout.strip().split(', ')
        info['gpu'] = f"{gpu_info[0]} ({gpu_info[1]}MB total, {gpu_info[2]}MB used)"
    else:
        info['gpu'] = "Not available"
    
    # Memory info
    success, stdout, stderr = manager.execute_ssh_command("free -h | grep Mem")
    if success and stdout.strip():
        parts = stdout.split()
        info['memory'] = f"{parts[1]} total, {parts[2]} used, {parts[3]} free"
    else:
        info['memory'] = "Not available"
    
    # Disk info
    success, stdout, stderr = manager.execute_ssh_command("df -h /workspace")
    if success and stdout.strip():
        lines = stdout.strip().split('\n')
        if len(lines) > 1:
            parts = lines[1].split()
            info['disk'] = f"{parts[1]} total, {parts[2]} used, {parts[3]} available"
    else:
        info['disk'] = "Not available"
    
    # Python version
    success, stdout, stderr = manager.execute_ssh_command("python3 --version")
    if success:
        info['python'] = stdout.strip()
    else:
        info['python'] = "Not available"
    
    return info

def create_backup(path: str, backup_name: str = None) -> bool:
    """Create backup of specified path on RunPod"""
    if not ensure_pod_running():
        logger.error("No running pod available")
        return False
    
    if not backup_name:
        from datetime import datetime
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"
    
    cmd = f"cd /workspace && tar -czf {backup_name} {path}"
    success, stdout, stderr = manager.execute_ssh_command(cmd)
    
    if success:
        logger.info(f"Backup created: {backup_name}")
        return True
    else:
        logger.error(f"Backup failed: {stderr}")
        return False

def restore_backup(backup_path: str, target_path: str = "/workspace") -> bool:
    """Restore backup from specified path"""
    if not ensure_pod_running():
        logger.error("No running pod available")
        return False
    
    cmd = f"cd {target_path} && tar -xzf {backup_path}"
    success, stdout, stderr = manager.execute_ssh_command(cmd)
    
    if success:
        logger.info(f"Backup restored from: {backup_path}")
        return True
    else:
        logger.error(f"Restore failed: {stderr}")
        return False

def monitor_process(process_name: str, timeout: int = 3600) -> bool:
    """Monitor a process on RunPod"""
    if not ensure_pod_running():
        logger.error("No running pod available")
        return False
    
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Check if process is running
        cmd = f"pgrep -f '{process_name}'"
        success, stdout, stderr = manager.execute_ssh_command(cmd)
        
        if success and stdout.strip():
            logger.info(f"Process {process_name} is running (PID: {stdout.strip()})")
            time.sleep(30)  # Check every 30 seconds
        else:
            logger.info(f"Process {process_name} is not running")
            return False
    
    logger.warning(f"Process monitoring timed out after {timeout} seconds")
    return False

def get_logs(log_path: str = "/workspace/logs", lines: int = 50) -> str:
    """Get recent logs from RunPod"""
    if not ensure_pod_running():
        return "No running pod available"
    
    cmd = f"find {log_path} -name '*.log' -exec tail -n {lines} {{}} \\;"
    success, stdout, stderr = manager.execute_ssh_command(cmd)
    
    if success:
        return stdout
    else:
        return f"Error getting logs: {stderr}"

# --- New maintenance helpers ---
def clear_remote_directory(remote_dir: str) -> bool:
    """Dangerous: recursively delete contents of a remote directory.

    For safety, only allows paths under /workspace.
    """
    if not ensure_pod_running():
        logger.error("No running pod available")
        return False
    remote_dir = remote_dir.strip()
    if not remote_dir.startswith("/workspace"):
        logger.error("Refusing to delete outside /workspace")
        return False
    # Ensure directory exists, then remove contents only
    cmd = f"bash -lc 'set -e; mkdir -p " + remote_dir.replace("'", "'\\''") + "; rm -rf " + remote_dir.replace("'", "'\\''") + "/*'"
    ok, _, err = manager.execute_ssh_command(cmd)
    if not ok:
        logger.error(f"Failed to clear remote directory: {err}")
    return ok

def prune_local_batches(local_base_dir: str, keep: int = 5) -> int:
    """Remove old local batch_* folders, keeping the newest N.

    Returns number of removed folders.
    """
    base = Path(local_base_dir)
    if not base.exists():
        return 0
    candidates: List[Path] = [p for p in base.iterdir() if p.is_dir() and p.name.startswith("batch_")]
    # Sort by modification time, newest first
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    to_remove = candidates[keep:] if keep >= 0 else []
    removed = 0
    for path in to_remove:
        try:
            import shutil
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
        except Exception:
            pass
    return removed
# Export functions directly
__all__ = [
    'ensure_pod_running',
    'upload_project_files', 
    'get_system_info',
    'create_backup',
    'restore_backup',
    'monitor_process',
    'get_logs',
    'download_and_extract_outputs',
    'clear_remote_directory',
    'prune_local_batches'
]

def download_and_extract_outputs(remote_dir: str, local_base_dir: str = "data/output_images",
                                 archive_name_prefix: str = "facial_outputs") -> Optional[str]:
    """Archive remote output directory on the pod, download and extract locally into timestamped folder.

    Args:
        remote_dir: Remote directory path on the pod (absolute or relative to /workspace)
        local_base_dir: Local base directory for extraction
        archive_name_prefix: Prefix for temporary archive names

    Returns:
        Optional[str]: Path to the local extracted directory if successful, None otherwise
    """
    if not ensure_pod_running():
        logger.error("No running pod available")
        return None

    # Normalize remote paths
    remote_dir = remote_dir.strip()
    remote_dir_quoted = remote_dir.replace("'", "'\\''")

    # Verify remote directory exists
    check_cmd = f"test -d '{remote_dir_quoted}' && echo OK || echo MISSING"
    ok, stdout, _ = manager.execute_ssh_command(check_cmd)
    if not ok or 'OK' not in stdout:
        logger.error(f"Remote directory not found: {remote_dir}")
        return None

    # Timestamp for names
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    remote_archive = f"/workspace/{archive_name_prefix}_{ts}.tar.gz"

    # Create archive on pod (archive by parent dir and name to ensure relative paths)
    # Example: tar -C /workspace/data/output_images -czf /workspace/facial_outputs_...tar.gz batch
    parent_dir_cmd = f"python3 -c 'import os,sys; p=\"{remote_dir_quoted}\"; import pathlib; q=str(pathlib.Path(p).parent); print(q)'"
    ok, parent_stdout, _ = manager.execute_ssh_command(parent_dir_cmd)
    if not ok or not parent_stdout.strip():
        logger.error("Failed to resolve remote parent directory")
        return None
    remote_parent = parent_stdout.strip().splitlines()[0]
    remote_name_cmd = f"python3 -c 'import pathlib; print(pathlib.Path(\"{remote_dir_quoted}\").name)'"
    ok, name_stdout, _ = manager.execute_ssh_command(remote_name_cmd)
    if not ok or not name_stdout.strip():
        logger.error("Failed to resolve remote directory name")
        return None
    remote_name = name_stdout.strip().splitlines()[0]

    tar_cmd = f"tar -C '{remote_parent}' -czf '{remote_archive}' '{remote_name}'"
    ok, _, stderr = manager.execute_ssh_command(tar_cmd)
    if not ok:
        logger.error(f"Failed to create remote archive: {stderr}")
        return None

    # Download archive locally
    local_archive = Path(f"./{Path(remote_archive).name}")
    if not manager.download_file(remote_archive, str(local_archive)):
        logger.error("Failed to download remote archive")
        return None

    # Prepare local extraction directory
    local_base = Path(local_base_dir)
    target_dir = local_base / f"batch_{ts}"
    target_dir.mkdir(parents=True, exist_ok=True)

    # Extract archive
    try:
        import tarfile
        with tarfile.open(local_archive, 'r:gz') as tf:
            tf.extractall(path=target_dir)
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return None
    finally:
        # Clean up local archive
        try:
            if local_archive.exists():
                local_archive.unlink()
        except Exception:
            pass

    # Optionally remove remote archive
    manager.execute_ssh_command(f"rm -f {remote_archive}")

    logger.info(f"Outputs downloaded and extracted to: {target_dir}")
    return str(target_dir)
