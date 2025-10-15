#!/usr/bin/env python3
import asyncio
import os
from pathlib import Path
from typing import Optional

import click
import pyperclip
from rich.console import Console

from .commit_message import ConventionalCommitStrategy, SimpleCommitStrategy
from .config import Config
from .core import ChangeAnalyzer, GitCommitter
from .factories import ClaudeAgentFactory, GeminiAgentFactory, QwenAgentFactory
from .observers import ConsoleLogObserver, FileLogObserver

console = Console()


def run_async(coro):
    """Run an async coroutine, handling both test and production environments."""
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        # If we're in a test environment with a running loop, create a task
        if loop.is_running():
            # For testing, we'll need to handle this differently
            # For now, we'll use asyncio.run() but catch the error
            try:
                return asyncio.run(coro)
            except RuntimeError:
                # If asyncio.run() fails, we're probably in a test environment
                # Create a new event loop for this coroutine
                import nest_asyncio

                nest_asyncio.apply()
                return asyncio.run(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop running, use asyncio.run()
        return asyncio.run(coro)


def get_agent_factory(model: str, api_key: Optional[str] = None):
    """Get the appropriate agent factory based on the model name."""
    if model.startswith("anthropic:") or model.startswith("claude-"):
        return ClaudeAgentFactory(model=model)
    elif model.startswith("google:") or model.startswith("gemini-"):
        return GeminiAgentFactory(model=model, api_key=api_key)
    elif model.startswith("qwen:") or "qwen" in model.lower():
        return QwenAgentFactory(model=model, api_key=api_key)
    else:
        # Default to Claude if no specific prefix
        return ClaudeAgentFactory(model=model)


@click.command()
@click.option(
    "--config-dir",
    is_flag=True,
    help="Display the config file location and copy it to clipboard",
)
@click.option(
    "--config-list", is_flag=True, help="Display current configuration settings"
)
@click.option(
    "-p",
    "--path",
    default=".",
    help="Path to git repository (defaults to current directory)",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "-d", "--dry-run", is_flag=True, help="Show proposed commits without making changes"
)
@click.option(
    "-a",
    "--auto-push",
    is_flag=True,
    help="Automatically push changes after committing (overrides config setting)",
)
@click.option(
    "-m",
    "--merge",
    is_flag=True,
    help="After pushing changes, merge into main branch and push",
)
@click.option(
    "--main-branch",
    help="Name of the main branch to merge into (overrides config setting)",
)
@click.option(
    "-c",
    "--commit-style",
    type=click.Choice(["conventional", "simple"], case_sensitive=False),
    help="Style of commit messages to generate (overrides config setting)",
)
@click.option(
    "-l",
    "--log-file",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Optional file to log git operations (overrides config setting)",
)
@click.option(
    "--simple",
    is_flag=True,
    help="Use simple commit message format instead of conventional commits",
)
@click.option(
    "--model",
    default="qwen2.5-coder:7b",
    help="AI model to use (e.g. claude-3-5-sonnet-latest, gemini-pro, qwen2.5-coder:7b, ollama:qwen2.5-coder:7b)",
)
@click.option(
    "--api-key",
    envvar=[
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
        "QWEN_API_KEY",
        "HF_TOKEN",
    ],
    help="API key for the selected model. Can also be set via environment variables: GEMINI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY, QWEN_API_KEY, or HF_TOKEN. Not needed for Ollama models.",
)
@click.option("--version", is_flag=True, help="Display version information and exit")
@click.option("--check-updates", is_flag=True, help="Check for available updates")
@click.option("--verify-install", is_flag=True, help="Verify installation integrity")
@click.option(
    "--no-verify",
    is_flag=True,
    help="Skip pre-commit hooks when creating commits",
)
@click.option(
    "--no-auto-stage",
    is_flag=True,
    help="Don't automatically stage all changes before analysis (default: auto-stage)",
)
def main(
    config_list: bool,
    config_dir: bool,
    path: Path,
    dry_run: bool,
    auto_push: bool,
    merge: bool,
    main_branch: str,
    commit_style: str,
    log_file: Optional[Path],
    simple: bool,
    model: str,
    api_key: Optional[str],
    version: bool,
    check_updates: bool,
    verify_install: bool,
    no_verify: bool,
    no_auto_stage: bool,
):
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
        # Handle version management commands first
        if version:
            from .version import display_version_info

            display_version_info()
            return

        if check_updates:
            from .version import check_updates_and_display

            check_updates_and_display()
            return

        if verify_install:
            from .version import verify_and_display

            verify_and_display()
            return

        repo_path = path.absolute()

        if config_list:
            config = Config.load(repo_path)
            config_path = repo_path / ".gitsmartcommit.toml"

            console.print("\n[bold]Current Configuration Settings:[/bold]")
            if config_path.exists():
                console.print(
                    f"[dim]Config file: {str(config_path).replace(os.sep, '/')}[/dim]"
                )
            else:
                console.print("[dim]Using default values (no config file found)[/dim]")

            console.print(f"\n{'Setting':<20} {'Value':<20} {'Source':<10}")
            console.print("-" * 50)

            def print_setting(name: str, value: any, source: str):
                console.print(f"{name:<20} {str(value):<20} {source:<10}")

            print_setting(
                "main_branch",
                config.main_branch,
                "config" if config_path.exists() else "default",
            )
            print_setting(
                "commit_style",
                config.commit_style,
                "config" if config_path.exists() else "default",
            )
            print_setting(
                "remote_name",
                config.remote_name,
                "config" if config_path.exists() else "default",
            )
            print_setting(
                "auto_push",
                config.auto_push,
                "config" if config_path.exists() else "default",
            )
            print_setting(
                "always_log",
                config.always_log,
                "config" if config_path.exists() else "default",
            )
            print_setting(
                "log_file",
                config.log_file or "None",
                "config" if config_path.exists() else "default",
            )
            print_setting(
                "model", config.model, "config" if config_path.exists() else "default"
            )

            console.print(
                "\nTo modify these settings, create or edit .gitsmartcommit.toml in your repository root"
            )
            return

        if config_dir:
            config_path = repo_path / ".gitsmartcommit.toml"
            config_path_str = str(config_path)

            # Create default config file if it doesn't exist
            if not config_path.exists():
                config = Config()
                config.save(repo_path)
                console.print(
                    "[yellow]Created new config file with default values[/yellow]"
                )

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
        else:
            # Use default model if no --model specified
            config.model = "qwen2.5-coder:7b"

        # Create the appropriate factory based on model selection
        factory = get_agent_factory(config.model, api_key)

        # Initialize analyzer with the factory
        analyzer = ChangeAnalyzer(
            str(repo_path), factory=factory, auto_stage=not no_auto_stage
        )

        # Select commit strategy based on configuration
        strategy = (
            ConventionalCommitStrategy()
            if config.commit_style == "conventional"
            else SimpleCommitStrategy()
        )

        # Always show the commit messages
        commit_units = run_async(analyzer.analyze_changes())
        for unit in commit_units:
            console.print(
                f"[green]{unit.type.value}({unit.scope}): {unit.description}[/green]"
            )
            console.print(f"Files: {', '.join(unit.files)}")
            if unit.body:
                console.print(f"Body: {unit.body}\n")

        if not dry_run:
            committer = GitCommitter(str(repo_path), no_verify=no_verify)

            # Add observers
            committer.add_observer(ConsoleLogObserver(console))

            # Set up logging based on configuration
            log_file_path = log_file or config.get_log_file()
            if log_file_path:
                committer.add_observer(FileLogObserver(str(log_file_path)))

            # Set upstream before committing
            console.print("\n[blue]Checking upstream branch...[/blue]")
            upstream_success = run_async(committer.set_upstream())
            if not upstream_success:
                console.print(
                    "[yellow]Warning: Failed to set upstream branch. Continuing with commits...[/yellow]"
                )

            success = run_async(committer.commit_changes(commit_units))

            # Handle push and merge operations
            if success and (auto_push or config.auto_push):
                success = run_async(committer.push_changes())

            # Handle merge operation (independent of auto-push)
            if success and merge:
                # If auto-push wasn't enabled, we need to push first before merging
                if not (auto_push or config.auto_push):
                    console.print("\n[blue]Pushing changes before merge...[/blue]")
                    push_success = run_async(committer.push_changes())
                    if not push_success:
                        console.print(
                            "[red]Failed to push changes. Cannot proceed with merge.[/red]"
                        )
                        success = False

                if success:
                    merge_success = run_async(
                        committer.merge_to_main(config.main_branch)
                    )
                    if not merge_success:
                        console.print(
                            f"\n[yellow]Note: Changes were pushed but could not be merged into '{config.main_branch}'.[/yellow]"
                        )
                        console.print(
                            "[yellow]Please ensure the main branch exists and try merging manually.[/yellow]"
                        )
                        success = False
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise click.Abort()


if __name__ == "__main__":
    main()
