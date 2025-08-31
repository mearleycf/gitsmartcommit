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
from .factories import AgentFactory, ClaudeAgentFactory
from .commands import GitCommand, CommitCommand, PushCommand, MergeCommand, SetUpstreamCommand

@dataclass
class GitDependencies:
    repo: Repo
    repo_path: str

class ChangeAnalyzer:
    """Analyzes changes in a Git repository."""

    def __init__(self, repo_path: str, factory: Optional[AgentFactory] = None, commit_strategy: Optional[CommitMessageStrategy] = None):
        """Initialize the analyzer with a Git repository."""
        self.repo = Repo(repo_path)
        self.repo_path = repo_path
        
        # Use provided factory or default to Claude
        self.agent_factory = factory or ClaudeAgentFactory()
        
        if commit_strategy:
            self.commit_strategy = commit_strategy
        else:
            self.commit_strategy = self.agent_factory.create_commit_strategy()
            
        self.relationship_agent = self.agent_factory.create_relationship_agent()
        self.commit_generator = CommitMessageGenerator(self.commit_strategy)

    def _validate_repo(self) -> bool:
        """Validate repository state and raise appropriate errors."""
        if not self.repo.is_dirty() and not self.repo.untracked_files:
            raise ValueError("No changes detected in repository")
        return True

    def _collect_changes(self) -> List[FileChange]:
        """Collect all changes in the repository."""
        changes = []
        
        # Get staged changes
        diff_staged = self.repo.index.diff(self.repo.head.commit)
        for diff in diff_staged:
            content = diff.diff.decode('utf-8') if isinstance(diff.diff, bytes) else str(diff.diff)
            changes.append(FileChange(
                path=diff.a_path or diff.b_path,
                status=diff.change_type,
                content_diff=content,
                is_staged=True
            ))
        
        # Get unstaged changes
        diff_unstaged = self.repo.index.diff(None)
        for diff in diff_unstaged:
            content = diff.diff.decode('utf-8') if isinstance(diff.diff, bytes) else str(diff.diff)
            changes.append(FileChange(
                path=diff.a_path or diff.b_path,
                status=diff.change_type,
                content_diff=content,
                is_staged=False
            ))
        
        # Get untracked files
        for file_path in self.repo.untracked_files:
            full_path = Path(self.repo.working_dir) / file_path
            try:
                # Try to read as text first
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except (UnicodeDecodeError, UnicodeError):
                # If it's a binary file, just indicate that it's binary
                content = f"[Binary file: {file_path}]"
            except Exception:
                # If there's any other error reading the file, use a generic message
                content = f"[File: {file_path}]"
            
            changes.append(FileChange(
                path=file_path,
                status='untracked',
                content_diff=content,
                is_staged=False
            ))
        
        return changes

    async def analyze_changes(self) -> List[CommitUnit]:
        """Analyze the changes in the repository and suggest commit units."""
        self._validate_repo()
        
        # Collect all changes
        changes = self._collect_changes()
        
        # If there's only one file changed, no need for relationship analysis
        if len(changes) == 1:
            result = await self.commit_generator.generate_commit_message(
                [changes[0]], self.repo
            )
            
            # Handle different result structures
            if hasattr(result, 'output'):
                message = result.output
            elif hasattr(result, 'data'):
                message = result.data
            else:
                message = result
                
            return [CommitUnit(
                type=message.commit_type,
                scope=message.scope,
                description=message.description,
                files=[changes[0].path],
                message=f"{message.commit_type.value}({message.scope}): {message.description}",
                body=message.reasoning or ""
            )]
        
        # Analyze relationships between changes
        diffs = []
        for change in changes:
            diffs.append(f"Changes in {change.path}:\n{change.content_diff}")
        
        prompt = """Please analyze these files and group related changes based on logical units of work. 
A single logical unit means changes that work together to achieve one goal. 
For example: implementation files with their tests, or configuration files that support a feature.

Files to analyze:
""" + "\n".join(diffs)
        
        result = await self.relationship_agent.run(prompt)
        
        if not result:
            raise ValueError("Failed to analyze relationships between changes")
            
        # Handle different result structures
        if hasattr(result, 'output'):
            grouping_result = result.output
        elif hasattr(result, 'data'):
            grouping_result = result.data
        else:
            grouping_result = result
        
        # Generate commit messages for each unit
        commit_units = []
        for group in grouping_result.groups:
            group_changes = [c for c in changes if c.path in group]
            
            result = await self.commit_generator.generate_commit_message(group_changes, self.repo)
            if not result:
                continue
                
            # Handle different result structures
            if hasattr(result, 'output'):
                commit_analysis = result.output
            elif hasattr(result, 'data'):
                commit_analysis = result.data
            else:
                commit_analysis = result
            body = commit_analysis.reasoning if commit_analysis.reasoning else ""
            
            commit_unit = CommitUnit(
                type=commit_analysis.commit_type,
                scope=commit_analysis.scope,
                description=commit_analysis.description,
                files=commit_analysis.related_files,
                body=body,
                message=f"{commit_analysis.commit_type.value}({commit_analysis.scope}): {commit_analysis.description}"
            )
            commit_units.append(commit_unit)
        
        return commit_units

class GitCommitter:
    """Handles git operations using the Command Pattern."""
    
    def __init__(self, repo_path: str):
        self.repo = Repo(repo_path)
        self.console = Console()
        self.observers: List[GitOperationObserver] = []
        self.command_history: List[GitCommand] = []
    
    def add_observer(self, observer: GitOperationObserver) -> None:
        """Add an observer to be notified of git operations."""
        self.observers.append(observer)
    
    def remove_observer(self, observer: GitOperationObserver) -> None:
        """Remove an observer from the notification list."""
        self.observers.remove(observer)
    
    async def execute_command(self, command: GitCommand) -> bool:
        """Execute a git command and store it in history if successful."""
        # Add observers to the command
        for observer in self.observers:
            command.add_observer(observer)
        
        # Execute the command
        success = await command.execute()
        
        # Store in history if successful
        if success:
            self.command_history.append(command)
        
        return success
    
    async def undo_last_command(self) -> bool:
        """Undo the last executed command."""
        if not self.command_history:
            self.console.print("[yellow]No commands to undo[/yellow]")
            return False
        
        command = self.command_history.pop()
        return await command.undo()
    
    async def set_upstream(self) -> bool:
        """Set the upstream branch if not already set.
        
        Returns:
            bool: True if the operation was successful, False otherwise
        """
        command = SetUpstreamCommand(self.repo, self.console)
        return await self.execute_command(command)
    
    async def commit_changes(self, commit_units: List[CommitUnit]) -> bool:
        """Create commits for each commit unit using the Command Pattern."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task("Creating commits...", total=len(commit_units))
            
            success = True
            for unit in commit_units:
                command = CommitCommand(self.repo, unit, self.console)
                if not await self.execute_command(command):
                    success = False
                    break
                progress.advance(task)
            
            return success
    
    async def push_changes(self) -> bool:
        """Push commits to remote repository using the Command Pattern."""
        command = PushCommand(self.repo, self.console)
        return await self.execute_command(command)
    
    async def merge_to_main(self, main_branch: str) -> bool:
        """Merge current branch into main branch and push changes."""
        command = MergeCommand(self.repo, main_branch, self.console)
        return await self.execute_command(command)