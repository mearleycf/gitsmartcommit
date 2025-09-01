"""Version management for git-smart-commit."""

import importlib.metadata
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from . import __version__

console = Console()


def get_current_version() -> str:
    """Get the current version of git-smart-commit."""
    return __version__


def get_installed_version() -> str:
    """Get the installed version from pip metadata."""
    try:
        return importlib.metadata.version("gitsmartcommit")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def get_installation_path() -> Optional[Path]:
    """Get the installation path of git-smart-commit."""
    try:
        # Try to get the path from the package
        import gitsmartcommit
        return Path(gitsmartcommit.__file__).parent
    except ImportError:
        return None


def check_for_updates() -> Tuple[bool, Optional[str]]:
    """Check if there's a newer version available on PyPI."""
    try:
        current_version = get_current_version()
        
        # Check PyPI for the latest version
        async def fetch_latest_version():
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://pypi.org/pypi/gitsmartcommit/json",
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("info", {}).get("version")
                return None
        
        # Use asyncio to fetch the latest version
        import asyncio
        try:
            latest_version = asyncio.run(fetch_latest_version())
            if latest_version and latest_version != current_version:
                # Compare versions properly
                from packaging import version
                if version.parse(latest_version) > version.parse(current_version):
                    return True, latest_version
        except Exception as e:
            console.print(f"[yellow]Warning: Could not fetch latest version: {e}[/yellow]")
        
        return False, current_version
        
    except Exception as e:
        console.print(f"[yellow]Warning: Could not check for updates: {e}[/yellow]")
        return False, None


def verify_installation() -> bool:
    """Verify that git-smart-commit is properly installed."""
    try:
        # Check if the package can be imported
        import gitsmartcommit
        
        # Check if the CLI entry point exists
        try:
            result = subprocess.run(
                ["git-smart-commit", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Check if we can access the main modules
        from gitsmartcommit import cli, core, config
        from gitsmartcommit.commit_message import strategy, generator
        
        return True
        
    except ImportError as e:
        console.print(f"[red]Installation verification failed: {e}[/red]")
        return False


def display_version_info() -> None:
    """Display comprehensive version information."""
    current_version = get_current_version()
    installed_version = get_installed_version()
    installation_path = get_installation_path()
    
    # Create version info text
    version_text = Text()
    version_text.append("git-smart-commit\n", style="bold blue")
    version_text.append(f"Current version: {current_version}\n", style="green")
    version_text.append(f"Installed version: {installed_version}\n", style="cyan")
    
    if installation_path:
        version_text.append(f"Installation path: {installation_path}\n", style="yellow")
    
    # Check if versions match
    if current_version != installed_version:
        version_text.append("\n⚠️  Version mismatch detected!\n", style="red")
        version_text.append("Consider reinstalling: pip install -e .\n", style="yellow")
    
    # Verify installation
    if verify_installation():
        version_text.append("\n✅ Installation verified successfully\n", style="green")
    else:
        version_text.append("\n❌ Installation verification failed\n", style="red")
    
    # Display in a panel
    panel = Panel(
        version_text,
        title="Version Information",
        border_style="blue"
    )
    console.print(panel)


def check_updates_and_display() -> None:
    """Check for updates and display results."""
    console.print("🔍 Checking for updates...")
    
    has_updates, latest_version = check_for_updates()
    current_version = get_current_version()
    
    if has_updates and latest_version:
        console.print(f"[green]🎉 New version available: {latest_version}[/green]")
        console.print(f"[yellow]Current version: {current_version}[/yellow]")
        console.print("\nTo update, run:")
        console.print("[cyan]pip install --upgrade gitsmartcommit[/cyan]")
    else:
        console.print(f"[green]✅ You're running the latest version: {current_version}[/green]")


def verify_and_display() -> None:
    """Verify installation and display results."""
    console.print("🔍 Verifying installation...")
    
    if verify_installation():
        console.print("[green]✅ Installation verified successfully![/green]")
        console.print("[green]All components are working correctly.[/green]")
    else:
        console.print("[red]❌ Installation verification failed![/red]")
        console.print("[yellow]Try reinstalling: pip install -e .[/yellow]")


def get_version_summary() -> str:
    """Get a brief version summary for CLI output."""
    current_version = get_current_version()
    installed_version = get_installed_version()
    
    if current_version == installed_version:
        return f"git-smart-commit {current_version}"
    else:
        return f"git-smart-commit {current_version} (installed: {installed_version})"
