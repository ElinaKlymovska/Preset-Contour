#!/usr/bin/env python3
"""
RunPod CLI Interface
Command-line interface for managing RunPod instances
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional

from .manager import manager
from .utils import (
    get_system_info,
    ensure_pod_running,
    upload_project_files,
    create_backup,
    restore_backup,
    monitor_process,
    get_logs,
    download_and_extract_outputs,
    clear_remote_directory,
    prune_local_batches,
)
from .config import config

def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def cmd_status(args):
    """Show pod status"""
    print("🔍 Checking pod status...")
    
    pod_info = manager.get_pod_info()
    if not pod_info:
        print("❌ Could not get pod information")
        return 1
    
    pod_id = pod_info.get("id", "UNKNOWN")
    runtime = pod_info.get("runtime", {})
    
    print(f"📊 Pod ID: {pod_id}")
    
    # Determine status based on runtime
    if runtime:
        print("✅ Pod is running")
        
        # Get connection details
        if manager.wait_for_pod_ready():
            pod_status = manager.get_pod_status()
            if pod_status:
                print(f"🔗 SSH: {pod_status.ssh_host}:{pod_status.ssh_port}")
                if pod_status.jupyter_url:
                    print(f"📓 Jupyter: {pod_status.jupyter_url}")
                
                # Test SSH connection
                if manager.test_ssh_connection():
                    print("✅ SSH connection: OK")
                else:
                    print("❌ SSH connection: Failed")
        
        # Get system info
        print("\n💻 System Information:")
        system_info = get_system_info()
        for key, value in system_info.items():
            print(f"   {key}: {value}")
    else:
        print("⏸️  Pod is stopped or starting")
    
    return 0

def cmd_start(args):
    """Start the pod"""
    print("🚀 Starting pod...")
    
    if manager.start_pod():
        print("✅ Pod started successfully")
        
        if args.wait:
            print("⏳ Waiting for pod to be ready...")
            if manager.wait_for_pod_ready():
                print("✅ Pod is ready")
                return 0
            else:
                print("❌ Pod failed to become ready")
                return 1
        else:
            print("💡 Use 'runpod status' to check when pod is ready")
            return 0
    else:
        print("❌ Failed to start pod")
        return 1

def cmd_stop(args):
    """Stop the pod"""
    print("🛑 Stopping pod...")
    
    if manager.stop_pod():
        print("✅ Pod stopped successfully")
        return 0
    else:
        print("❌ Failed to stop pod")
        return 1

def cmd_connect(args):
    """Connect to the pod"""
    print("🔗 Connecting to pod...")
    
    if not ensure_pod_running(auto_start=args.auto_start):
        print("❌ Could not ensure pod is running")
        return 1
    
    if manager.test_ssh_connection():
        print("✅ Successfully connected to pod")
        
        if args.cmd:
            print(f"🔧 Executing command: {args.cmd}")
            success, stdout, stderr = manager.execute_ssh_command(args.cmd)
            if success:
                print("✅ Command executed successfully")
                if stdout:
                    print("📤 Output:")
                    print(stdout)
            else:
                print("❌ Command failed")
                if stderr:
                    print(f"Error: {stderr}")
                return 1
        else:
            print("💡 Use 'runpod connect --cmd \"your_command\"' to execute commands")
        
        return 0
    else:
        print("❌ Failed to connect to pod")
        return 1

def cmd_upload(args):
    """Upload files to the pod"""
    print("📤 Uploading files...")
    
    if not ensure_pod_running(auto_start=args.auto_start):
        print("❌ Could not ensure pod is running")
        return 1
    
    local_path = Path(args.local_path)
    if not local_path.exists():
        print(f"❌ Local path does not exist: {local_path}")
        return 1
    
    remote_path = args.remote_path or f"/workspace/{local_path.name}"
    
    if local_path.is_file():
        success = manager.upload_file(str(local_path), remote_path)
    else:
        success = upload_project_files(str(local_path))
    
    if success:
        print(f"✅ Uploaded {local_path} to {remote_path}")
        return 0
    else:
        print("❌ Upload failed")
        return 1

def cmd_download(args):
    """Download files from the pod"""
    print("📥 Downloading files...")
    
    if not ensure_pod_running(auto_start=args.auto_start):
        print("❌ Could not ensure pod is running")
        return 1
    
    local_path = Path(args.local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    
    success = manager.download_file(args.remote_path, str(local_path))
    
    if success:
        print(f"✅ Downloaded {args.remote_path} to {local_path}")
        return 0
    else:
        print("❌ Download failed")
        return 1

def cmd_setup(args):
    """Setup workspace on the pod"""
    print("🔧 Setting up workspace...")
    
    if not ensure_pod_running(auto_start=args.auto_start):
        print("❌ Could not ensure pod is running")
        return 1
    
    if manager.setup_workspace():
        print("✅ Workspace setup completed")
        
        if args.upload:
            print("📤 Uploading project files to pod...")
            if upload_project_files("./"):
                print("✅ Project uploaded")
            else:
                print("❌ Project upload failed")
                return 1

        if args.install_deps:
            print("📦 Installing dependencies...")
            if manager.install_dependencies():
                print("✅ Dependencies installed successfully")
            else:
                print("❌ Failed to install dependencies")
                return 1
        
        return 0
    else:
        print("❌ Workspace setup failed")
        return 1

def cmd_execute(args):
    """Execute a script on the pod"""
    print(f"🔧 Executing script: {args.script}")
    
    if not ensure_pod_running(auto_start=args.auto_start):
        print("❌ Could not ensure pod is running")
        return 1
    
    script_args = args.args if args.args else []
    
    # Execute script using manager
    # Optional: purge remote outputs before run
    if getattr(args, 'purge_remote_outputs', False):
        remote_dir = args.remote_output or "/workspace/data/outputs"
        print(f"🧹 Clearing remote outputs: {remote_dir}")
        ok = clear_remote_directory(remote_dir)
        if ok:
            print("✅ Remote outputs cleared")
        else:
            print("⚠️ Failed to clear remote outputs")

    success, stdout, stderr = manager.execute_ssh_command(f"python3 {args.script} {' '.join(script_args)}")
    if success:
        print("✅ Script executed successfully")
        # Print remote stdout (expected to contain JSON result)
        if stdout:
            try:
                print(stdout.strip())
            except Exception:
                pass
        # Optional: fetch results from remote after execution
        if getattr(args, 'fetch_outputs', False):
            remote_dir = args.remote_output or "/workspace/data/outputs"
            local_base = args.local_output or "data/output_images"
            print(f"📥 Fetching outputs from {remote_dir} → {local_base} ...")
            extracted = download_and_extract_outputs(remote_dir=remote_dir, local_base_dir=local_base)
            if extracted:
                print(f"✅ Outputs downloaded to: {extracted}")
                if getattr(args, 'prune_local', False):
                    keep = int(args.keep_local if args.keep_local is not None else 5)
                    removed = prune_local_batches(local_base, keep=keep)
                    print(f"🧹 Pruned local batches: removed {removed}, kept {keep}")
            else:
                print("❌ Failed to download outputs")
        return 0
    else:
        print("❌ Script execution failed")
        return 1

def cmd_pipeline(args):
    """Run the face pipeline and auto-download results locally.

    Steps:
    - Ensure pod is running (optionally auto-start)
    - Optionally setup workspace and install deps
    - Optionally upload current project files
    - Optionally clear remote outputs
    - Execute process_faces.py with provided args
    - Auto-download outputs and optionally prune local batches
    """
    print("🚀 Running pipeline with auto-download...")

    if not ensure_pod_running(auto_start=args.auto_start):
        print("❌ Could not ensure pod is running")
        return 1

    if getattr(args, 'setup', False):
        print("🔧 Setting up workspace on pod...")
        if not manager.setup_workspace():
            print("❌ Workspace setup failed")
            return 1

    if getattr(args, 'install_deps', False):
        print("📦 Installing dependencies on pod...")
        if not manager.install_dependencies():
            print("❌ Dependency installation failed")
            return 1

    if getattr(args, 'upload', False):
        print("📤 Uploading project files to /workspace...")
        if not upload_project_files("./"):
            print("❌ Project upload failed")
            return 1

    # Optionally purge remote outputs
    remote_output_dir = args.remote_output or "/workspace/data/outputs"
    if getattr(args, 'purge_remote_outputs', False):
        print(f"🧹 Clearing remote outputs: {remote_output_dir}")
        if not clear_remote_directory(remote_output_dir):
            print("⚠️ Failed to clear remote outputs")

    # Compose script and arguments
    script_path = args.script or "/workspace/hyperrealistic/pipelines/process_faces.py"
    script_args = []
    # Map known arguments to process_faces.py
    if args.model:
        script_args += ["--model", args.model]
    if args.per_image is not None:
        script_args += ["--per-image", str(args.per_image)]
    if args.input:
        script_args += ["--input", args.input]
    if args.output:
        script_args += ["--output", args.output]
    if args.seed is not None:
        script_args += ["--seed", str(args.seed)]
    if args.prompt_extra:
        script_args += ["--prompt-extra", args.prompt_extra]
    if args.negative_extra:
        script_args += ["--negative-extra", args.negative_extra]
    if args.disable_controlnet:
        script_args += ["--disable-controlnet"]
    if args.mask_shape:
        script_args += ["--mask-shape", args.mask_shape]
    if args.mask_feather is not None:
        script_args += ["--mask-feather", str(args.mask_feather)]
    if args.mask_inset is not None:
        script_args += ["--mask-inset", str(args.mask_inset)]
    if args.webui:
        script_args += ["--webui", args.webui]

    # Ensure WebUI API reachable; try to start if not
    probe_url = args.webui if args.webui else "http://127.0.0.1:7860"
    probe_cmd = f"bash -lc 'curl -s --max-time 5 {probe_url}/sdapi/v1/progress >/dev/null 2>&1 && echo UP || echo DOWN'"
    ok, probe_out, _ = manager.execute_ssh_command(probe_cmd)
    if not ok or 'DOWN' in (probe_out or ''):
        print("🟡 WebUI not reachable, attempting to start it...")
        start_cmd = (
            "bash -lc 'mkdir -p /workspace/logs; "
            "setsid python3 /workspace/hyperrealistic/pipelines/start_webui.py </dev/null > /workspace/logs/webui_boot.log 2>&1 & "
            "sleep 5; "
            "for i in $(seq 1 60); do curl -s --max-time 5 " + probe_url + "/sdapi/v1/progress >/dev/null 2>&1 && echo READY && break; sleep 5; done'"
        )
        manager.execute_ssh_command(start_cmd)

    remote_cmd = (
        "bash -lc 'export PYTHONPATH=/workspace; "
        + f"python3 {script_path} {' '.join(script_args)}"
        + "'"
    )
    print(f"🔧 Executing: {remote_cmd}")
    success, stdout, stderr = manager.execute_ssh_command(remote_cmd)

    if not success:
        print("❌ Pipeline execution failed")
        if stderr:
            print(f"Error: {stderr}")
        return 1

    print("✅ Pipeline completed")
    if stdout:
        try:
            print(stdout.strip())
        except Exception:
            pass

    # Auto-fetch outputs
    local_base = args.local_output or "data/output_images"
    print(f"📥 Downloading outputs from {remote_output_dir} → {local_base} ...")
    extracted = download_and_extract_outputs(remote_dir=remote_output_dir, local_base_dir=local_base)
    if extracted:
        print(f"✅ Outputs downloaded to: {extracted}")
        if getattr(args, 'prune_local', False):
            keep = int(args.keep_local if args.keep_local is not None else 5)
            removed = prune_local_batches(local_base, keep=keep)
            print(f"🧹 Pruned local batches: removed {removed}, kept {keep}")
        return 0
    else:
        print("❌ Failed to download outputs")
        return 1

def cmd_monitor(args):
    """Monitor a process on the pod"""
    print(f"📊 Monitoring process: {args.process}")
    
    if not ensure_pod_running(auto_start=args.auto_start):
        print("❌ Could not ensure pod is running")
        return 1
    
    if monitor_process(args.process, args.timeout):
        print("✅ Process completed successfully")
        return 0
    else:
        print("❌ Process monitoring failed or timed out")
        return 1

def cmd_backup(args):
    """Create or restore backup"""
    if args.action == "create":
        print(f"💾 Creating backup of {args.path}")
        
        if not ensure_pod_running(auto_start=args.auto_start):
            print("❌ Could not ensure pod is running")
            return 1
        
        if create_backup(args.path, args.name):
            print("✅ Backup created successfully")
            return 0
        else:
            print("❌ Backup creation failed")
            return 1
    
    elif args.action == "restore":
        print(f"📦 Restoring backup from {args.backup_path}")
        
        if not ensure_pod_running(auto_start=args.auto_start):
            print("❌ Could not ensure pod is running")
            return 1
        
        if restore_backup(args.backup_path, args.path):
            print("✅ Backup restored successfully")
            return 0
        else:
            print("❌ Backup restoration failed")
            return 1

def cmd_config(args):
    """Show or update configuration"""
    if args.show:
        print("⚙️  Current Configuration:")
        print(f"   Pod ID: {config.pod_id}")
        print(f"   SSH User: {config.ssh_user}")
        print(f"   SSH Key: {config.ssh_key_path}")
        print(f"   GPU Type: {config.gpu_type}")
        print(f"   Container: {config.container_image}")
        print(f"   Workspace: {config.workspace_path}")
        
        if config.api_key:
            print(f"   API Key: {'*' * 10}{config.api_key[-4:]}")
        else:
            print("   API Key: Not configured")
    
    return 0

def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="RunPod Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  runpod status                    # Check pod status
  runpod start --wait              # Start pod and wait for ready
  runpod connect --command "ls"    # Execute command on pod
  runpod upload ./data /workspace  # Upload local directory
  runpod setup --install-deps      # Setup workspace and install dependencies
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--auto-start', action='store_true', help='Auto-start pod if stopped')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands', required=True)
    
    # Status command
    subparsers.add_parser('status', help='Show pod status')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start the pod')
    start_parser.add_argument('--wait', action='store_true', help='Wait for pod to be ready')
    
    # Stop command
    subparsers.add_parser('stop', help='Stop the pod')
    
    # Connect command
    connect_parser = subparsers.add_parser('connect', help='Connect to the pod')
    connect_parser.add_argument('--cmd', help='Command to execute')
    
    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload files to the pod')
    upload_parser.add_argument('local_path', help='Local file or directory path')
    upload_parser.add_argument('remote_path', nargs='?', help='Remote path (optional)')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download files from the pod')
    download_parser.add_argument('remote_path', help='Remote file path')
    download_parser.add_argument('local_path', help='Local file path')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Setup workspace on the pod')
    setup_parser.add_argument('--install-deps', action='store_true', help='Install dependencies')
    setup_parser.add_argument('--upload', action='store_true', help='Upload current project to /workspace')
    
    # Execute command
    execute_parser = subparsers.add_parser('execute', help='Execute a script on the pod')
    execute_parser.add_argument('script', help='Script path on the pod')
    execute_parser.add_argument('args', nargs='*', help='Script arguments')
    execute_parser.add_argument('--fetch-outputs', action='store_true', help='Download and extract outputs after execution')
    execute_parser.add_argument('--remote-output', default='/workspace/data/outputs', help='Remote outputs directory on the pod')
    execute_parser.add_argument('--local-output', default='data/output_images', help='Local base directory to extract outputs into')
    execute_parser.add_argument('--purge-remote-outputs', action='store_true', help='Clear remote outputs directory before execution')
    execute_parser.add_argument('--prune-local', action='store_true', help='Prune old local batch_* folders after download')
    execute_parser.add_argument('--keep-local', type=int, default=5, help='How many newest local batches to keep when pruning')
    
    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor a process on the pod')
    monitor_parser.add_argument('process', help='Process name to monitor')
    monitor_parser.add_argument('--timeout', type=int, default=3600, help='Timeout in seconds')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create or restore backup')
    backup_parser.add_argument('action', choices=['create', 'restore'], help='Backup action')
    backup_parser.add_argument('path', help='Path to backup/restore')
    backup_parser.add_argument('--name', help='Backup name (for create)')
    backup_parser.add_argument('--backup-path', help='Backup path (for restore)')
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Show configuration')
    config_parser.add_argument('--show', action='store_true', help='Show current configuration')

    # Pipeline command
    pipeline_parser = subparsers.add_parser('pipeline', help='Run face pipeline and auto-download outputs')
    pipeline_parser.add_argument('--model', type=str, help='Model key defined in pipelines.config (e.g., gonzalomo_xl)')
    pipeline_parser.add_argument('--per-image', dest='per_image', type=int, default=1, help='Number of images to generate per source')
    pipeline_parser.add_argument('--input', help='Remote input directory on pod (default /workspace/data/input)', default='/workspace/data/input')
    pipeline_parser.add_argument('--output', help='Remote output directory on pod (default /workspace/data/outputs)', default='/workspace/data/outputs')
    pipeline_parser.add_argument('--seed', type=int, default=None)
    pipeline_parser.add_argument('--prompt-extra', dest='prompt_extra', type=str, default='')
    pipeline_parser.add_argument('--negative-extra', dest='negative_extra', type=str, default='')
    pipeline_parser.add_argument('--disable-controlnet', action='store_true')
    pipeline_parser.add_argument('--mask-shape', choices=['ellipse','rect'], default=None)
    pipeline_parser.add_argument('--mask-feather', dest='mask_feather', type=float, default=None)
    pipeline_parser.add_argument('--mask-inset', dest='mask_inset', type=float, default=None)
    pipeline_parser.add_argument('--webui', type=str, default=None, help='Override WebUI base URL')
    pipeline_parser.add_argument('--script', type=str, default='/workspace/hyperrealistic/pipelines/process_faces.py', help='Remote script path to execute')
    # Orchestration flags
    pipeline_parser.add_argument('--setup', action='store_true', help='Setup workspace directories on pod')
    pipeline_parser.add_argument('--install-deps', dest='install_deps', action='store_true', help='Install dependencies on pod')
    pipeline_parser.add_argument('--upload', action='store_true', help='Upload current project to /workspace before run')
    pipeline_parser.add_argument('--purge-remote-outputs', action='store_true', help='Clear remote outputs directory before execution')
    pipeline_parser.add_argument('--remote-output', default='/workspace/data/outputs', help='Remote outputs directory on the pod')
    pipeline_parser.add_argument('--local-output', default='data/output_images', help='Local base directory to extract outputs into')
    pipeline_parser.add_argument('--prune-local', action='store_true', help='Prune old local batch_* folders after download')
    pipeline_parser.add_argument('--keep-local', type=int, default=5, help='How many newest local batches to keep when pruning')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Execute command
    if args.command == 'status':
        return cmd_status(args)
    elif args.command == 'start':
        return cmd_start(args)
    elif args.command == 'stop':
        return cmd_stop(args)
    elif args.command == 'connect':
        return cmd_connect(args)
    elif args.command == 'upload':
        return cmd_upload(args)
    elif args.command == 'download':
        return cmd_download(args)
    elif args.command == 'setup':
        return cmd_setup(args)
    elif args.command == 'execute':
        return cmd_execute(args)
    elif args.command == 'monitor':
        return cmd_monitor(args)
    elif args.command == 'backup':
        return cmd_backup(args)
    elif args.command == 'config':
        return cmd_config(args)
    elif args.command == 'pipeline':
        return cmd_pipeline(args)
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
