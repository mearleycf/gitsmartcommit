#!/usr/bin/env python3
import asyncio
import click
from rich.console import Console
from pathlib import Path
from .core import ChangeAnalyzer, GitCommitter

console = Console()

@click.command()
@click.option(
    '--path', 
    default=".",
    help="Path to git repository (defaults to current directory)",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
@click.option(
    '--dry-run',
    is_flag=True,
    help="Show proposed commits without making changes"
)
@click.option(
    '--auto-push',
    is_flag=True,
    help="Automatically push changes after committing"
)
def main(path: Path, dry_run: bool, auto_push: bool):
    """
    Intelligent Git commit tool that analyzes changes and creates meaningful commits.
    
    This tool will:
    1. Analyze your repository changes
    2. Group related changes into logical commits
    3. Generate meaningful commit messages
    4. Optionally push changes to remote
    """
    try:
        repo_path = str(path.absolute())
        analyzer = ChangeAnalyzer(repo_path)
        commit_units = asyncio.run(analyzer.analyze_changes())
        
        # Always show the commit messages
        for unit in commit_units:
            console.print(f"[green]{unit.type.value}({unit.scope}): {unit.description}[/green]")
            console.print(f"Files: {', '.join(unit.files)}")
            if unit.body:
                console.print(f"Body: {unit.body}\n")
        
        if not dry_run:
            committer = GitCommitter(repo_path)
            success = asyncio.run(committer.commit_changes(commit_units))
            
            if success and auto_push:
                committer.push_changes()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise click.Abort()

if __name__ == "__main__":
    main()