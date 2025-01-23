"""Core functionality for git-smart-commit."""
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
import git
from git import Repo
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, Tool
from .models import CommitType, FileChange, CommitUnit, RelationshipResult, CommitMessageResult
from .commit_message import CommitMessageGenerator, CommitMessageStrategy
from .observers import GitOperationObserver
from .prompts import RELATIONSHIP_PROMPT, COMMIT_MESSAGE_PROMPT

@dataclass
class GitDependencies:
    repo: Repo
    repo_path: str

class ChangeAnalyzer:
    def __init__(self, repo_path: str, commit_strategy: Optional[CommitMessageStrategy] = None):
        self.repo = Repo(repo_path)
        self.console = Console()
        self.git_deps = GitDependencies(repo=self.repo, repo_path=repo_path)
        
        # Initialize agents
        self.relationship_agent = Agent(
            'anthropic:claude-3-5-sonnet-latest',
            result_type=RelationshipResult,
            system_prompt=RELATIONSHIP_PROMPT
        )

        self.commit_agent = CommitMessageGenerator(strategy=commit_strategy)

    def _validate_repo(self):
        """Validate repository state and raise appropriate errors."""
        if not self.repo.is_dirty() and not self.repo.untracked_files:
            raise ValueError("No changes detected in repository")
        return True

    async def analyze_changes(self) -> List[CommitUnit]:
        """Analyze repository changes and group them into logical commit units."""
        self._validate_repo()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            # Collect all changes
            task = progress.add_task("Analyzing repository changes...", total=None)
            changes = self._collect_changes()
            
            # If there's only one file changed, no need for relationship analysis
            if len(changes) == 1:
                task = progress.add_task("Generating commit message...", total=None)
                result = await self.commit_agent.generate_commit_message(changes, self.repo)
                if not result:
                    return []
                    
                commit_analysis = result.data if hasattr(result, 'data') else result
                body = commit_analysis.reasoning if commit_analysis.reasoning else ""
                
                commit_unit = CommitUnit(
                    type=commit_analysis.commit_type,
                    scope=commit_analysis.scope,
                    description=commit_analysis.description,
                    files=commit_analysis.related_files,
                    body=body
                )
                progress.update(task, completed=True)
                return [commit_unit]
            
            # Use AI to analyze relationships and group changes
            task = progress.add_task("Grouping related changes...", total=None)
            file_tuples = [(change.path, change.content_diff) for change in changes]

            analyze_result = await self.relationship_agent.run(
                """Please analyze these files and group related changes based on logical units of work. 
A single logical unit means changes that work together to achieve one goal. 
For example: implementation files with their tests, or configuration files that support a feature.

Files to analyze:
"""
                + "\n".join(f"{path}: {diff}" for path, diff in file_tuples)
            )
            
            if not analyze_result or not hasattr(analyze_result, 'data'):
                raise ValueError("Failed to analyze relationships between changes")
                
            grouping_result = analyze_result.data
            
            # Generate commit messages for each group
            commit_units = []
            for group in grouping_result.groups:
                group_changes = [c for c in changes if c.path in group]
                
                result = await self.commit_agent.generate_commit_message(group_changes, self.repo)
                if not result:
                    continue
                    
                commit_analysis = result.data if hasattr(result, 'data') else result
                body = commit_analysis.reasoning if commit_analysis.reasoning else ""
                
                commit_unit = CommitUnit(
                    type=commit_analysis.commit_type,
                    scope=commit_analysis.scope,
                    description=commit_analysis.description,
                    files=commit_analysis.related_files,
                    body=body
                )
                commit_units.append(commit_unit)
            
            progress.update(task, completed=True)
            return commit_units

    def _collect_changes(self) -> List[FileChange]:
        """Collect all changes in the repository."""
        changes = []
        print("Collecting changes...")
        
        # Get staged changes
        print("Getting staged changes...")
        diff_staged = self.repo.index.diff(self.repo.head.commit)
        for diff in diff_staged:
            print(f"Found staged change: {diff.a_path or diff.b_path}")
            content = diff.diff.decode('utf-8') if isinstance(diff.diff, bytes) else str(diff.diff)
            changes.append(FileChange(
                path=diff.a_path or diff.b_path,
                status=diff.change_type,
                content_diff=content,
                is_staged=True
            ))
        
        # Get unstaged changes
        print("Getting unstaged changes...")
        diff_unstaged = self.repo.index.diff(None)
        for diff in diff_unstaged:
            print(f"Found unstaged change: {diff.a_path or diff.b_path}")
            content = diff.diff.decode('utf-8') if isinstance(diff.diff, bytes) else str(diff.diff)
            changes.append(FileChange(
                path=diff.a_path or diff.b_path,
                status=diff.change_type,
                content_diff=content,
                is_staged=False
            ))
        
        # Get untracked files
        print("Getting untracked files...")
        for file_path in self.repo.untracked_files:
            print(f"Found untracked file: {file_path}")
            with open(Path(self.repo.working_dir) / file_path, 'r') as f:
                content = f.read()
            changes.append(FileChange(
                path=file_path,
                status='untracked',
                content_diff=content,
                is_staged=False
            ))
        
        print(f"Total changes found: {len(changes)}")
        return changes

class GitCommitter:
    def __init__(self, repo_path: str):
        self.repo = Repo(repo_path)
        self.console = Console()
        self.observers: List[GitOperationObserver] = []

    def add_observer(self, observer: GitOperationObserver) -> None:
        """Add an observer to be notified of git operations."""
        self.observers.append(observer)

    def remove_observer(self, observer: GitOperationObserver) -> None:
        """Remove an observer from the notification list."""
        self.observers.remove(observer)

    async def notify_commit_created(self, commit_unit: CommitUnit) -> None:
        """Notify all observers that a commit was created."""
        for observer in self.observers:
            await observer.on_commit_created(commit_unit)

    async def notify_push_completed(self, success: bool) -> None:
        """Notify all observers that a push operation completed."""
        for observer in self.observers:
            await observer.on_push_completed(success)

    async def commit_changes(self, commit_units: List[CommitUnit]) -> bool:
        """Create commits for each commit unit."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task("Creating commits...", total=len(commit_units))
            
            for unit in commit_units:
                # Stage files for this commit
                for file_path in unit.files:
                    file_exists = Path(self.repo.working_dir) / file_path
                    if file_exists.exists():
                        self.repo.index.add([file_path])
                    else:
                        # Handle deleted files
                        try:
                            self.repo.index.remove([file_path])
                        except git.exc.GitCommandError:
                            # If the file is already staged for deletion, continue
                            pass
                
                # Create commit message
                message = f"{unit.type.value}"
                if unit.scope:
                    message += f"({unit.scope})"
                message += f": {unit.description}"
                if unit.body:
                    message += f"\n\n{unit.body}"
                
                # Create commit
                self.repo.index.commit(message)
                await self.notify_commit_created(unit)
                progress.advance(task)
            
            return True

    async def push_changes(self) -> bool:
        """Push commits to remote repository."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task("Pushing changes to remote...", total=None)
            
            try:
                # Check if remote exists
                if not self.repo.remotes:
                    self.console.print("[red]No remote repository configured[/red]")
                    success = False
                else:
                    self.repo.remote().push()
                    progress.update(task, completed=True)
                    success = True
            except git.GitCommandError as e:
                self.console.print(f"[red]Failed to push changes: {str(e)}[/red]")
                success = False

            await self.notify_push_completed(success)
            return success