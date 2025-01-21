"""Command line interface for gitsmartcommit."""

import os
import sys
from rich.console import Console
from .smart_commit import GitSmartCommitTool

console = Console()

def main():
    """Main entry point for the command line interface."""
    try:
        tool = GitSmartCommitTool()
        result = tool.execute(repo_path=os.getcwd())
        console.print(result)
        return 0
    except KeyboardInterrupt:
        console.print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())