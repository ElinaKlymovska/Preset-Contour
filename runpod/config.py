"""
RunPod Configuration Module
"""
import os
from dataclasses import dataclass
from typing import Optional
# Optional dotenv import for local CLI usage; not required on pod
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(_path: str = '.env') -> None:  # fallback no-op
        return None

# Load environment variables
load_dotenv('.env')

@dataclass
class RunPodConfig:
    """Configuration for RunPod connection and management"""
    
    # Pod details from your RunPod dashboard
    pod_id: str = "nstyyroc81ocnm"
    pod_name: str = "lonely_cyan_ox"
    
    # API settings
    api_key: Optional[str] = None  # Will be loaded from environment variable
    
    # Connection details (will be populated dynamically when pod is running)
    pod_url: Optional[str] = None
    ssh_host: Optional[str] = "194.68.245.201"  # Updated pod SSH host
    ssh_port: Optional[int] = 22075  # Updated pod SSH port
    ssh_user: str = "root"
    ssh_key_path: str = "/Users/ElinaKlymovska/.ssh/id_ed25519"
    jupyter_port: Optional[int] = 8888
    
    # Resource specifications
    gpu_type: str = "A40"
    gpu_count: int = 1
    cpu_count: int = 9
    memory_gb: int = 50
    
    # Container details
    container_image: str = "runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04"
    workspace_path: str = "/workspace"
    volume_name: str = "matrix"
    
    # Local paths
    local_scripts_path: str = "./pipelines"
    local_data_path: str = "./data"
    
    def __post_init__(self):
        """Load configuration from environment variables"""
        self.api_key = os.getenv("RUNPOD_API_KEY")
        
        # Create local directories if they don't exist
        os.makedirs(self.local_scripts_path, exist_ok=True)
        os.makedirs(self.local_data_path, exist_ok=True)

# Global configuration instance
config = RunPodConfig()