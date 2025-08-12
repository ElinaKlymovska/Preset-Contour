#!/usr/bin/env python3
"""
Quick start script for RunPod pipeline.
Simple one-command execution for common use cases.
"""
import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from runpod.run_pipeline import PipelineRunner


def quick_start():
    """Quick start with common configurations"""
    print("🚀 Quick Start: Hyperrealistic Face Enhancement Pipeline")
    print("=" * 60)
    
    # Get user preferences
    print("\n📋 Choose your configuration:")
    print("1. Quick test (realistic_vision, 1 variation)")
    print("2. Quality comparison (2 models, 1 variation each)")
    print("3. Batch testing (realistic_vision + settings testing)")
    print("4. Custom configuration")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    runner = PipelineRunner()
    
    if choice == "1":
        print("\n🎯 Running quick test with realistic_vision model...")
        success = runner.run_full_pipeline(
            models=["realistic_vision"],
            per_image=1,
            run_batch_testing=False,
            download_results=True
        )
        
    elif choice == "2":
        print("\n🔍 Running quality comparison with 2 models...")
        success = runner.run_full_pipeline(
            models=["realistic_vision", "cinematic_beauty"],
            per_image=1,
            run_batch_testing=False,
            download_results=True
        )
        
    elif choice == "3":
        print("\n🧪 Running batch testing for optimal settings...")
        success = runner.run_full_pipeline(
            models=["realistic_vision"],
            per_image=1,
            run_batch_testing=True,
            download_results=True
        )
        
    elif choice == "4":
        print("\n⚙️ Custom configuration:")
        models_input = input("Models (space-separated, default: realistic_vision): ").strip()
        models = models_input.split() if models_input else ["realistic_vision"]
        
        per_image = input("Variations per image (default: 1): ").strip()
        per_image = int(per_image) if per_image.isdigit() else 1
        
        batch_testing = input("Run batch testing? (y/N): ").strip().lower() == 'y'
        
        print(f"\n🎯 Running custom configuration...")
        success = runner.run_full_pipeline(
            models=models,
            per_image=per_image,
            run_batch_testing=batch_testing,
            download_results=True
        )
        
    else:
        print("❌ Invalid choice. Exiting.")
        return
    
    # Show results
    if success:
        print("\n✅ Pipeline completed successfully!")
        print("📁 Results downloaded to 'results/' directory")
        print("📊 Check 'runpod_pipeline.log' for detailed logs")
    else:
        print("\n❌ Pipeline failed. Check logs for details.")


def main():
    parser = argparse.ArgumentParser(description="Quick start for RunPod pipeline")
    parser.add_argument("--interactive", action="store_true", default=True,
                       help="Run in interactive mode (default)")
    parser.add_argument("--models", nargs="+", 
                       help="Models to run (non-interactive mode)")
    parser.add_argument("--per-image", type=int, default=1,
                       help="Variations per image (non-interactive mode)")
    parser.add_argument("--batch-testing", action="store_true",
                       help="Run batch testing (non-interactive mode)")
    
    args = parser.parse_args()
    
    if args.interactive or (not args.models and not args.batch_testing):
        quick_start()
    else:
        # Non-interactive mode
        runner = PipelineRunner()
        success = runner.run_full_pipeline(
            models=args.models or ["realistic_vision"],
            per_image=args.per_image,
            run_batch_testing=args.batch_testing,
            download_results=True
        )
        
        if success:
            print("✅ Pipeline completed successfully!")
            exit(0)
        else:
            print("❌ Pipeline failed!")
            exit(1)


if __name__ == "__main__":
    main()
