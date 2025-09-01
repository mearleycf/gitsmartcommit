#!/usr/bin/env python3
"""
Global installation script for git-smart-commit.

This script installs git-smart-commit globally so it can be used from any repository.
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
    """Install git-smart-commit globally."""
    print("🚀 Installing git-smart-commit globally...")
    
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Check if we're in a git repository
    if not (project_root / ".git").exists():
        print("❌ Error: This script must be run from the git-smart-commit repository root")
        sys.exit(1)
    
    # Install globally
    print("📦 Installing package globally...")
    
    # Check if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Detected virtual environment. Installing without --user flag.")
        run_command(f"{sys.executable} -m pip install -e .")
    else:
        run_command(f"{sys.executable} -m pip install -e . --user")
    
    # Verify installation
    print("✅ Verifying installation...")
    result = run_command("git-smart-commit --help", check=False)
    
    if result.returncode == 0:
        print("🎉 Installation successful!")
        print("\nYou can now use git-smart-commit from any repository:")
        print("  git-smart-commit --help")
        print("  git-smart-commit -d  # dry run")
        print("  git-smart-commit -a  # auto-push")
        print("\nShort alias also available:")
        print("  git-smart --help")
    else:
        print("❌ Installation verification failed")
        print("Try running: git-smart-commit --help")
        sys.exit(1)

if __name__ == "__main__":
    main()
