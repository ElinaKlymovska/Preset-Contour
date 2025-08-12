"""
RunPod Integration Module
Provides tools for connecting to and managing RunPod instances
"""

from .config import config, RunPodConfig
from .manager import manager, RunPodManager
from .utils import get_system_info, ensure_pod_running, upload_project_files, create_backup, restore_backup, monitor_process, get_logs

__all__ = [
    'config', 'RunPodConfig', 
    'manager', 'RunPodManager', 
    'get_system_info', 'ensure_pod_running', 'upload_project_files', 
    'create_backup', 'restore_backup', 'monitor_process', 'get_logs'
]

# Version info
__version__ = "1.0.0"
