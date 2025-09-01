#!/usr/bin/env python3
"""Script to check and update git-smart-commit in other repositories."""

import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple
import importlib.metadata

def get_installed_version() -> Optional[str]:
    """Get the currently installed version of git-smart-commit."""
    try:
        return importlib.metadata.version("gitsmartcommit")
    except importlib.metadata.PackageNotFoundError:
        return None

def get_installation_path() -> Optional[Path]:
    """Get the installation path of git-smart-commit."""
    try:
        import gitsmartcommit
        return Path(gitsmartcommit.__file__).parent
    except ImportError:
        return None

def check_if_editable_install() -> bool:
    """Check if git-smart-commit is installed in editable mode."""
    try:
        import gitsmartcommit
        # If it's an editable install, the path will point to the source directory
        install_path = Path(gitsmartcommit.__file__).parent
        return (install_path / "pyproject.toml").exists()
    except ImportError:
        return False

def get_latest_source_version() -> Optional[str]:
    """Get the latest version from the source repository."""
    try:
        # Try to get version from the source repository
        source_path = Path("/Users/mikeearley/code/gitsmartcommit")
        if source_path.exists():
            pyproject_path = source_path / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path, 'r') as f:
                    content = f.read()
                    import re
                    match = re.search(r'version = "([^"]+)"', content)
                    if match:
                        return match.group(1)
    except Exception:
        pass
    return None

def run_command(cmd: list, capture_output: bool = True) -> Tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"

def check_git_smart_commit_available() -> bool:
    """Check if git-smart-commit command is available."""
    returncode, _, _ = run_command(["git-smart-commit", "--version"])
    return returncode == 0

def update_editable_install() -> bool:
    """Update the editable installation."""
    try:
        print("🔄 Updating editable installation...")
        
        # Get the source repository path
        source_path = Path("/Users/mikeearley/code/gitsmartcommit")
        if not source_path.exists():
            print("❌ Source repository not found at /Users/mikeearley/code/gitsmartcommit")
            return False
        
        # Change to source directory and reinstall
        original_cwd = Path.cwd()
        os.chdir(source_path)
        
        try:
            # Reinstall in editable mode
            returncode, stdout, stderr = run_command([
                sys.executable, "-m", "pip", "install", "-e", "."
            ])
            
            if returncode == 0:
                print("✅ Successfully updated editable installation")
                return True
            else:
                print(f"❌ Failed to update: {stderr}")
                return False
        finally:
            os.chdir(original_cwd)
            
    except Exception as e:
        print(f"❌ Error updating: {e}")
        return False

def update_pip_install() -> bool:
    """Update the pip installation."""
    try:
        print("🔄 Updating pip installation...")
        
        returncode, stdout, stderr = run_command([
            sys.executable, "-m", "pip", "install", "--upgrade", "gitsmartcommit"
        ])
        
        if returncode == 0:
            print("✅ Successfully updated pip installation")
            return True
        else:
            print(f"❌ Failed to update: {stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating: {e}")
        return False

def main():
    """Main function for checking and updating git-smart-commit."""
    print("🔍 Checking git-smart-commit installation...")
    
    # Check if git-smart-commit is available
    if not check_git_smart_commit_available():
        print("❌ git-smart-commit is not installed or not available in PATH")
        print("\nTo install git-smart-commit:")
        print("1. Clone the repository:")
        print("   git clone <repository-url>")
        print("2. Install in editable mode:")
        print("   cd gitsmartcommit && pip install -e .")
        sys.exit(1)
    
    # Get current version
    current_version = get_installed_version()
    if not current_version:
        print("❌ Could not determine installed version")
        sys.exit(1)
    
    print(f"📦 Current version: {current_version}")
    
    # Check installation type
    is_editable = check_if_editable_install()
    install_path = get_installation_path()
    
    if is_editable:
        print(f"📁 Editable installation at: {install_path}")
        
        # Check for updates in source repository
        latest_version = get_latest_source_version()
        if latest_version and latest_version != current_version:
            print(f"🆕 New version available: {latest_version}")
            
            response = input("Do you want to update? (y/N): ").strip().lower()
            if response in ['y', 'yes']:
                if update_editable_install():
                    print("✅ Update completed successfully!")
                    print("\nYou can now use the updated version:")
                    print("   git-smart-commit --version")
                else:
                    print("❌ Update failed")
                    sys.exit(1)
            else:
                print("⏭️  Update skipped")
        else:
            print("✅ You're running the latest version")
    else:
        print(f"📦 Pip installation at: {install_path}")
        
        # For pip installations, we can't easily check for updates
        # but we can offer to upgrade
        response = input("Do you want to upgrade to the latest pip version? (y/N): ").strip().lower()
        if response in ['y', 'yes']:
            if update_pip_install():
                print("✅ Upgrade completed successfully!")
                print("\nYou can now use the updated version:")
                print("   git-smart-commit --version")
            else:
                print("❌ Upgrade failed")
                sys.exit(1)
        else:
            print("⏭️  Upgrade skipped")
    
    # Verify installation
    print("\n🔍 Verifying installation...")
    returncode, stdout, stderr = run_command(["git-smart-commit", "--verify-install"])
    
    if returncode == 0:
        print("✅ Installation verified successfully!")
    else:
        print("❌ Installation verification failed")
        print(f"Error: {stderr}")

if __name__ == "__main__":
    import os
    main()
