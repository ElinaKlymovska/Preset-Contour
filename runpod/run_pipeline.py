#!/usr/bin/env python3
"""
Automated pipeline runner for RunPod with enhanced face enhancement capabilities.
Handles model selection, batch processing, and result analysis.
"""
import argparse
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional
import json

from .manager import RunPodManager
from .config import config


class PipelineRunner:
    """Automated pipeline runner for RunPod"""
    
    def __init__(self):
        self.manager = RunPodManager()
        self.logger = logging.getLogger(__name__)
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('runpod_pipeline.log'),
                logging.StreamHandler()
            ]
        )
    
    def wait_for_webui(self, timeout: int = 300) -> bool:
        """Wait for WebUI to be ready"""
        self.logger.info("Waiting for WebUI to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Try to connect to WebUI
                response = self.manager.execute_ssh_command(
                    "curl -s http://localhost:7860 > /dev/null && echo 'ready' || echo 'not_ready'"
                )
                
                if response[0] and 'ready' in response[1]:
                    self.logger.info("WebUI is ready!")
                    return True
                    
            except Exception as e:
                self.logger.debug(f"WebUI check failed: {e}")
            
            time.sleep(10)
        
        self.logger.error(f"WebUI failed to start within {timeout} seconds")
        return False
    
    def run_model_pipeline(self, model: str, per_image: int = 1, 
                          extra_prompt: str = "", negative_prompt: str = "") -> bool:
        """Run pipeline for a specific model"""
        self.logger.info(f"Running pipeline for model: {model}")
        
        cmd_parts = [
            "python3", "/workspace/hyperrealistic/pipelines/process_faces.py",
            "--model", model,
            "--per-image", str(per_image)
        ]
        
        if extra_prompt:
            cmd_parts.extend(["--prompt-extra", f"'{extra_prompt}'"])
        
        if negative_prompt:
            cmd_parts.extend(["--negative-extra", f"'{negative_prompt}'"])
        
        cmd = " ".join(cmd_parts)
        
        try:
            success, stdout, stderr = self.manager.execute_ssh_command(cmd, timeout=600)
            
            if success:
                self.logger.info(f"Pipeline completed successfully for {model}")
                self.logger.debug(f"Output: {stdout}")
                return True
            else:
                self.logger.error(f"Pipeline failed for {model}: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error running pipeline for {model}: {e}")
            return False
    
    def run_batch_testing(self, model: str = "realistic_vision") -> bool:
        """Run batch testing for different settings"""
        self.logger.info(f"Running batch testing for model: {model}")
        
        cmd = f"python3 /workspace/hyperrealistic/pipelines/batch_test_settings.py --model {model}"
        
        try:
            success, stdout, stderr = self.manager.execute_ssh_command(cmd, timeout=1800)
            
            if success:
                self.logger.info("Batch testing completed successfully")
                self.logger.debug(f"Output: {stdout}")
                return True
            else:
                self.logger.error(f"Batch testing failed: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error running batch testing: {e}")
            return False
    
    def analyze_results(self) -> bool:
        """Analyze and compare results"""
        self.logger.info("Analyzing results...")
        
        cmd = "python3 /workspace/hyperrealistic/pipelines/compare_results.py --output-dir /workspace/data/outputs"
        
        try:
            success, stdout, stderr = self.manager.execute_ssh_command(cmd, timeout=300)
            
            if success:
                self.logger.info("Results analysis completed successfully")
                self.logger.info(f"Analysis output: {stdout}")
                return True
            else:
                self.logger.error(f"Results analysis failed: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error analyzing results: {e}")
            return False
    
    def download_results(self, local_dir: str = "results") -> bool:
        """Download results from RunPod"""
        self.logger.info(f"Downloading results to {local_dir}")
        
        local_path = Path(local_dir)
        local_path.mkdir(exist_ok=True)
        
        try:
            # Download outputs
            success = self.manager.download_file(
                "/workspace/data/outputs",
                str(local_path / "outputs")
            )
            
            if success:
                self.logger.info("Results downloaded successfully")
                return True
            else:
                self.logger.error("Failed to download results")
                return False
                
        except Exception as e:
            self.logger.error(f"Error downloading results: {e}")
            return False
    
    def run_full_pipeline(self, models: List[str] = None, 
                         per_image: int = 1,
                         run_batch_testing: bool = False,
                         download_results: bool = True) -> bool:
        """Run the complete enhanced pipeline"""
        if models is None:
            models = ["realistic_vision", "cinematic_beauty"]
        
        self.logger.info("Starting enhanced face enhancement pipeline...")
        
        # Wait for WebUI
        if not self.wait_for_webui():
            return False
        
        # Run pipeline for each model
        for model in models:
            if not self.run_model_pipeline(model, per_image):
                self.logger.warning(f"Pipeline failed for {model}, continuing with next model...")
        
        # Run batch testing if requested
        if run_batch_testing:
            if not self.run_batch_testing(models[0]):
                self.logger.warning("Batch testing failed, but continuing...")
        
        # Analyze results
        if not self.analyze_results():
            self.logger.warning("Results analysis failed, but continuing...")
        
        # Download results if requested
        if download_results:
            if not self.download_results():
                self.logger.warning("Failed to download results")
        
        self.logger.info("Enhanced pipeline completed!")
        return True


def main():
    parser = argparse.ArgumentParser(description="Run enhanced face enhancement pipeline on RunPod")
    parser.add_argument("--models", nargs="+", 
                       default=["realistic_vision", "cinematic_beauty"],
                       help="Models to run (default: realistic_vision cinematic_beauty)")
    parser.add_argument("--per-image", type=int, default=1,
                       help="Number of variations per image (default: 1)")
    parser.add_argument("--batch-testing", action="store_true",
                       help="Run batch testing for different settings")
    parser.add_argument("--no-download", action="store_true",
                       help="Don't download results automatically")
    parser.add_argument("--wait-webui", type=int, default=300,
                       help="Timeout for WebUI startup in seconds (default: 300)")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Create and run pipeline
    runner = PipelineRunner()
    
    try:
        success = runner.run_full_pipeline(
            models=args.models,
            per_image=args.per_image,
            run_batch_testing=args.batch_testing,
            download_results=not args.no_download
        )
        
        if success:
            print("✅ Pipeline completed successfully!")
            exit(0)
        else:
            print("❌ Pipeline failed!")
            exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Pipeline interrupted by user")
        exit(130)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
