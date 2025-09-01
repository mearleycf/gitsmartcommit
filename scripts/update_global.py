#!/usr/bin/env python3
"""
Update script for git-smart-commit.

This script updates the globally installed git-smart-commit with the latest changes.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, check=True):
    """Run a command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result

def main():
    """Update git-smart-commit globally."""
    print("🔄 Updating git-smart-commit...")
    
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Check if we're in a git repository
    if not (project_root / ".git").exists():
        print("❌ Error: This script must be run from the git-smart-commit repository root")
        sys.exit(1)
    
    # Check for uncommitted changes
    result = run_command("git status --porcelain", check=False)
    if result.stdout.strip():
        print("⚠️  Warning: You have uncommitted changes")
        print("Consider committing your changes before updating")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Update cancelled")
            sys.exit(0)
    
    # Update the installation
    print("📦 Updating package...")
    
    # Check if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Detected virtual environment. Updating without --user flag.")
        run_command(f"{sys.executable} -m pip install -e . --force-reinstall")
    else:
        run_command(f"{sys.executable} -m pip install -e . --user --force-reinstall")
    
    # Verify the update
    print("✅ Verifying update...")
    result = run_command("git-smart-commit --help", check=False)
    
    if result.returncode == 0:
        print("🎉 Update successful!")
        print("\nYou can now use the updated git-smart-commit from any repository")
    else:
        print("❌ Update verification failed")
        print("Try running: git-smart-commit --help")
        sys.exit(1)

if __name__ == "__main__":
    main()
