"""
RunPod Manager Module
Provides tools for managing RunPod instances, syncing code, and executing commands
"""
import os
import subprocess
import time
import requests
import json
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import paramiko
import logging
from dataclasses import dataclass
from .config import config, RunPodConfig


@dataclass
class PodStatus:
    """Pod status information"""
    pod_id: str
    status: str
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = None
    jupyter_url: Optional[str] = None
    is_running: bool = False


class RunPodManager:
    """Manager for RunPod operations"""
    
    def __init__(self, config: RunPodConfig = None):
        self.config = config or config
        self.api_base_url = "https://api.runpod.io/graphql"
        self.headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            self.headers["Authorization"] = f"Bearer {self.config.api_key}"
        self.current_pod = None
        self.logger = logging.getLogger(__name__)
    
    def get_pod_info(self, pod_id: str = None) -> Optional[Dict[str, Any]]:
        """Get information about the current pod using GraphQL"""
        pod_id = pod_id or self.config.pod_id
        
        query = """
        query Pod($podId: String!) {
            pod(input: { podId: $podId }) {
                id
                name
                runtime {
                    ports {
                        privatePort
                        publicPort
                        type
                    }
                }
            }
        }
        """
        
        try:
            if not self.config.api_key:
                # Without API key, we cannot query GraphQL; return minimal info
                self.logger.warning("RUNPOD_API_KEY not set; skipping GraphQL pod info fetch")
                return {
                    "id": pod_id,
                    "runtime": {"ports": []}
                }
            response = requests.post(
                self.api_base_url,
                headers=self.headers,
                json={"query": query, "variables": {"podId": pod_id}},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data'] and data['data'].get('pod'):
                    return data['data']['pod']
                else:
                    self.logger.error(f"Pod {pod_id} not found")
                    return None
            else:
                self.logger.error(f"Failed to get pod info: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting pod info: {e}")
            return None
    
    def start_pod(self, pod_id: str = None) -> bool:
        """Start the pod using GraphQL"""
        pod_id = pod_id or self.config.pod_id
        
        mutation = """
        mutation StartPod($podId: String!) {
            podStart(input: { podId: $podId }) {
                id
                status
            }
        }
        """
        
        try:
            if not self.config.api_key:
                self.logger.error("Cannot start pod without RUNPOD_API_KEY")
                return False
            response = requests.post(
                self.api_base_url,
                headers=self.headers,
                json={"query": mutation, "variables": {"podId": pod_id}},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data'] and data['data'].get('podStart'):
                    self.logger.info(f"Pod {pod_id} started successfully")
                    return True
                else:
                    self.logger.error(f"Failed to start pod: {data}")
                    return False
            else:
                self.logger.error(f"Failed to start pod: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting pod: {e}")
            return False
    
    def stop_pod(self, pod_id: str = None) -> bool:
        """Stop the pod using GraphQL"""
        pod_id = pod_id or self.config.pod_id
        
        mutation = """
        mutation StopPod($podId: String!) {
            podStop(input: { podId: $podId }) {
                id
                status
            }
        }
        """
        
        try:
            if not self.config.api_key:
                self.logger.error("Cannot stop pod without RUNPOD_API_KEY")
                return False
            response = requests.post(
                self.api_base_url,
                headers=self.headers,
                json={"query": mutation, "variables": {"podId": pod_id}},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data'] and data['data'].get('podStop'):
                    self.logger.info(f"Pod {pod_id} stopped successfully")
                    return True
                else:
                    self.logger.error(f"Failed to stop pod: {data}")
                    return False
            else:
                self.logger.error(f"Failed to stop pod: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error stopping pod: {e}")
            return False
    
    def wait_for_pod_ready(self, pod_id: str = None, timeout: int = 300) -> bool:
        """Wait for pod to be ready"""
        pod_id = pod_id or self.config.pod_id
        start_time = time.time()
        
        # Fast-path: if SSH is already reachable, consider pod ready even without GraphQL
        try:
            if self.test_ssh_connection():
                self.current_pod = PodStatus(
                    pod_id=pod_id,
                    status="RUNNING",
                    ssh_host=self.config.ssh_host,
                    ssh_port=self.config.ssh_port,
                    is_running=True,
                )
                self.logger.info("SSH reachable; considering pod ready")
                return True
        except Exception:
            pass

        while time.time() - start_time < timeout:
            pod_info = self.get_pod_info(pod_id)
            if pod_info:
                runtime = pod_info.get('runtime', {})
                
                # If runtime exists, pod is running
                if runtime:
                    # Use configured SSH details
                    ssh_host = self.config.ssh_host
                    ssh_port = self.config.ssh_port
                    if ssh_host and ssh_port and self.test_ssh_connection(ssh_host, ssh_port):
                        self.current_pod = PodStatus(
                            pod_id=pod_id,
                            status="RUNNING",
                            ssh_host=ssh_host,
                            ssh_port=ssh_port,
                            is_running=True,
                        )
                        self.logger.info(f"Pod {pod_id} is ready")
                        return True
                    
                    self.logger.info("Pod is running, waiting for SSH...")
                    time.sleep(10)
                else:
                    self.logger.info("Pod is starting...")
                    time.sleep(10)
            else:
                self.logger.warning("Could not get pod info")
                time.sleep(10)
        
        self.logger.error(f"Pod did not become ready within {timeout} seconds")
        return False
    
    def test_ssh_connection(self, host: str = None, port: int = None, 
                          user: str = None, key_path: str = None) -> bool:
        """Test SSH connection to the pod"""
        host = host or self.config.ssh_host
        port = port or self.config.ssh_port
        user = user or self.config.ssh_user
        key_path = key_path or self.config.ssh_key_path
        
        if not host or not port:
            self.logger.error("No SSH connection details available")
            return False
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                hostname=host,
                port=port,
                username=user,
                key_filename=key_path,
                timeout=10
            )
            
            ssh.close()
            return True
            
        except Exception as e:
            self.logger.warning(f"SSH connection failed: {e}")
            return False
    
    def execute_ssh_command(self, command: str, host: str = None, port: int = None,
                          user: str = None, key_path: str = None, 
                          timeout: int = 300) -> Tuple[bool, str, str]:
        """Execute command via SSH"""
        host = host or self.config.ssh_host
        port = port or self.config.ssh_port
        user = user or self.config.ssh_user
        key_path = key_path or self.config.ssh_key_path
        
        if not host or not port:
            return False, "", "No SSH connection details available"
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                hostname=host,
                port=port,
                username=user,
                key_filename=key_path,
                timeout=timeout
            )
            
            stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
            
            stdout_str = stdout.read().decode('utf-8')
            stderr_str = stderr.read().decode('utf-8')
            
            # Determine exit status
            try:
                exit_status = stdout.channel.recv_exit_status()
            except Exception:
                exit_status = 0
            
            ssh.close()
            
            return exit_status == 0, stdout_str, stderr_str
            
        except Exception as e:
            return False, "", str(e)
    
    def upload_file(self, local_path: str, remote_path: str, host: str = None, 
                   port: int = None, user: str = None, key_path: str = None) -> bool:
        """Upload a file via SCP"""
        host = host or self.config.ssh_host
        port = port or self.config.ssh_port
        user = user or self.config.ssh_user
        key_path = key_path or self.config.ssh_key_path
        
        if not host or not port:
            self.logger.error("No SSH connection details available")
            return False
        
        scp_cmd = f"scp -P {port} -i {key_path} '{local_path}' {user}@{host}:'{remote_path}'"
        
        try:
            result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"Uploaded {Path(local_path).name}")
                return True
            else:
                self.logger.error(f"Upload failed: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            return False
    
    def download_file(self, remote_path: str, local_path: str, host: str = None,
                     port: int = None, user: str = None, key_path: str = None) -> bool:
        """Download a file via SCP"""
        host = host or self.config.ssh_host
        port = port or self.config.ssh_port
        user = user or self.config.ssh_user
        key_path = key_path or self.config.ssh_key_path
        
        if not host or not port:
            self.logger.error("No SSH connection details available")
            return False
        
        scp_cmd = f"scp -P {port} -i {key_path} {user}@{host}:'{remote_path}' '{local_path}'"
        
        try:
            result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"Downloaded {Path(local_path).name}")
                return True
            else:
                self.logger.error(f"Download failed: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Download error: {e}")
            return False
    
    def setup_workspace(self) -> bool:
        """Setup workspace on the pod"""
        if not self.current_pod or not self.current_pod.is_running:
            self.logger.error("No running pod available")
            return False
        
        commands = [
            "mkdir -p /workspace",
            "mkdir -p /workspace/data",
            "mkdir -p /workspace/data/input",
            "mkdir -p /workspace/data/outputs",
            "mkdir -p /workspace/scripts",
            "mkdir -p /workspace/logs"
        ]
        
        for cmd in commands:
            success, stdout, stderr = self.execute_ssh_command(cmd)
            if not success:
                self.logger.error(f"Failed to execute: {cmd}")
                return False
        
        self.logger.info("Workspace setup completed")
        return True
    
    def install_dependencies(self) -> bool:
        """Install required dependencies on the pod"""
        if not self.current_pod or not self.current_pod.is_running:
            self.logger.error("No running pod available")
            return False
        
        commands = [
            "apt-get update",
            "apt-get install -y git python3-pip python3-venv wget curl",
            "cd /workspace && git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git || true",
            "python3 -m pip install --upgrade pip",
            # Install WebUI basic deps
            "cd /workspace/stable-diffusion-webui && pip install -r requirements.txt",
            # Extensions
            "cd /workspace/stable-diffusion-webui && git clone https://github.com/Bing-su/adetailer.git extensions/adetailer || true",
            "cd /workspace/stable-diffusion-webui && git clone https://github.com/Mikubill/sd-webui-controlnet extensions/sd-webui-controlnet || true",
            # Pipeline deps (match environment.yml)
            "python3 -m pip install insightface==0.7.3 face_recognition==1.3.0 opencv-python-headless==4.10.0.84 pillow==10.4.0 requests==2.32.3 numpy==1.26.4 python-dotenv==1.0.1"
        ]
        
        for cmd in commands:
            self.logger.info(f"Executing: {cmd}")
            success, stdout, stderr = self.execute_ssh_command(cmd, timeout=600)
            if not success:
                self.logger.error(f"Failed to execute: {cmd}")
                self.logger.error(f"Error: {stderr}")
                return False
        
        self.logger.info("Dependencies installed successfully")
        return True
    
    def get_pod_status(self) -> Optional[PodStatus]:
        """Get current pod status"""
        return self.current_pod
    
    def cleanup(self):
        """Cleanup resources"""
        if self.current_pod and self.current_pod.is_running:
            self.logger.info("Cleaning up pod connection")
            self.current_pod = None

# Global manager instance
manager = RunPodManager(config)
