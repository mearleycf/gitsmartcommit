#!/usr/bin/env python3
import asyncio
import click
from rich.console import Console
from pathlib import Path
from .core import ChangeAnalyzer, GitCommitter
from .commit_message import ConventionalCommitStrategy, SimpleCommitStrategy
from .observers import ConsoleLogObserver, FileLogObserver
from .config import Config
from .factories import ClaudeAgentFactory, GeminiAgentFactory
from typing import Optional
import pyperclip
import os

console = Console()

def get_agent_factory(model: str, api_key: Optional[str] = None):
    """Get the appropriate agent factory based on the model name."""
    if model.startswith('anthropic:') or model.startswith('claude-'):
        return ClaudeAgentFactory(model=model)
    elif model.startswith('google:') or model.startswith('gemini-'):
        return GeminiAgentFactory(model=model, api_key=api_key)
    else:
        # Default to Claude if no specific prefix
        return ClaudeAgentFactory(model=model)

@click.command()
@click.option(
    '--config-dir',
    is_flag=True,
    help="Display the config file location and copy it to clipboard"
)
@click.option(
    '--config-list',
    is_flag=True,
    help="Display current configuration settings"
)
@click.option(
    '-p',
    '--path', 
    default=".",
    help="Path to git repository (defaults to current directory)",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
@click.option(
    '-d',
    '--dry-run',
    is_flag=True,
    help="Show proposed commits without making changes"
)
@click.option(
    '-a',
    '--auto-push',
    is_flag=True,
    help="Automatically push changes after committing (overrides config setting)"
)
@click.option(
    '-m',
    '--merge',
    is_flag=True,
    help="After pushing changes, merge into main branch and push"
)
@click.option(
    '--main-branch',
    help="Name of the main branch to merge into (overrides config setting)"
)
@click.option(
    '-c',
    '--commit-style',
    type=click.Choice(['conventional', 'simple'], case_sensitive=False),
    help="Style of commit messages to generate (overrides config setting)"
)
@click.option(
    '-l',
    '--log-file',
    type=click.Path(dir_okay=False, path_type=Path),
    help="Optional file to log git operations (overrides config setting)"
)
@click.option('--simple', is_flag=True, help='Use simple commit message format instead of conventional commits')
@click.option('--model', default='claude-3-5-sonnet-latest', 
              help='AI model to use (e.g. claude-3-5-sonnet-latest, gemini-pro)')
@click.option('--api-key', envvar=['GEMINI_API_KEY', 'GOOGLE_API_KEY', 'ANTHROPIC_API_KEY'],
              help='API key for the selected model. Can also be set via environment variables: GEMINI_API_KEY, GOOGLE_API_KEY, or ANTHROPIC_API_KEY')
def main(config_list: bool, config_dir: bool, path: Path, dry_run: bool, auto_push: bool, merge: bool, main_branch: str, commit_style: str, log_file: Optional[Path], simple: bool, model: str, api_key: Optional[str]):
    """
    Intelligent Git commit tool that analyzes changes and creates meaningful commits.
    
    This tool will:
    1. Analyze your repository changes
    2. Group related changes into logical commits
    3. Generate meaningful commit messages
    4. Optionally push changes to remote
    5. Optionally merge changes into main branch
    
    Configuration can be set in .gitsmartcommit.toml in the repository root.
    Command line options override configuration file settings.
    """
    try:
        repo_path = path.absolute()
        
        if config_list:
            config = Config.load(repo_path)
            config_path = repo_path / ".gitsmartcommit.toml"
            
            console.print("\n[bold]Current Configuration Settings:[/bold]")
            if config_path.exists():
                console.print(f"[dim]Config file: {str(config_path).replace(os.sep, '/')}[/dim]")
            else:
                console.print("[dim]Using default values (no config file found)[/dim]")
            
            console.print(f"\n{'Setting':<20} {'Value':<20} {'Source':<10}")
            console.print("-" * 50)
            
            def print_setting(name: str, value: any, source: str):
                console.print(f"{name:<20} {str(value):<20} {source:<10}")
            
            print_setting("main_branch", config.main_branch, "config" if config_path.exists() else "default")
            print_setting("commit_style", config.commit_style, "config" if config_path.exists() else "default")
            print_setting("remote_name", config.remote_name, "config" if config_path.exists() else "default")
            print_setting("auto_push", config.auto_push, "config" if config_path.exists() else "default")
            print_setting("always_log", config.always_log, "config" if config_path.exists() else "default")
            print_setting("log_file", config.log_file or "None", "config" if config_path.exists() else "default")
            print_setting("model", config.model, "config" if config_path.exists() else "default")
            
            console.print("\nTo modify these settings, create or edit .gitsmartcommit.toml in your repository root")
            return
        
        if config_dir:
            config_path = repo_path / ".gitsmartcommit.toml"
            config_path_str = str(config_path)
            
            # Create default config file if it doesn't exist
            if not config_path.exists():
                config = Config()
                config.save(repo_path)
                console.print("[yellow]Created new config file with default values[/yellow]")
            
            pyperclip.copy(config_path_str)
            console.print(f"[green]Config file location:[/green] {config_path_str}")
            console.print("[green]Path copied to clipboard![/green]")
            return

        # Load configuration
        config = Config.load(repo_path)
        
        # Command line options override config
        if main_branch is not None:
            config.main_branch = main_branch
        if commit_style is not None:
            config.commit_style = commit_style
        if auto_push:
            config.auto_push = True
        if log_file is not None:
            config.log_file = str(log_file)
        if model is not None:
            config.model = model
        
        # Create the appropriate factory based on model selection
        factory = get_agent_factory(config.model, api_key)
        
        # Initialize analyzer with the factory
        analyzer = ChangeAnalyzer(str(repo_path), factory=factory)
        
        # Select commit strategy based on configuration
        strategy = ConventionalCommitStrategy() if config.commit_style == 'conventional' else SimpleCommitStrategy()
        
        # Always show the commit messages
        for unit in asyncio.run(analyzer.analyze_changes()):
            console.print(f"[green]{unit.type.value}({unit.scope}): {unit.description}[/green]")
            console.print(f"Files: {', '.join(unit.files)}")
            if unit.body:
                console.print(f"Body: {unit.body}\n")
        
        if not dry_run:
            committer = GitCommitter(str(repo_path))
            
            # Add observers
            committer.add_observer(ConsoleLogObserver(console))
            
            # Set up logging based on configuration
            log_file_path = config.get_log_file()
            if log_file_path:
                committer.add_observer(FileLogObserver(str(log_file_path)))
            
            success = asyncio.run(committer.commit_changes(asyncio.run(analyzer.analyze_changes())))
            
            if success and (auto_push or config.auto_push):
                success = asyncio.run(committer.push_changes())
                
                if success and merge:
                    merge_success = asyncio.run(committer.merge_to_main(config.main_branch))
                    if not merge_success:
                        console.print(f"\n[yellow]Note: Changes were pushed but could not be merged into '{config.main_branch}'.[/yellow]")
                        console.print("[yellow]Please ensure the main branch exists and try merging manually.[/yellow]")
                        success = False
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise click.Abort()

if __name__ == "__main__":
    main()