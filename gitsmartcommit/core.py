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
import os
import re
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

    def _is_safe_path(self, path: str) -> bool:
        """Check if a path is safe to process (no path traversal)."""
        try:
            # Resolve the path to check for path traversal
            resolved_path = Path(self.repo_path).resolve()
            file_path = (Path(self.repo_path) / path).resolve()
            
            # Ensure the file is within the repository
            return str(file_path).startswith(str(resolved_path))
        except (OSError, ValueError):
            return False

    def _sanitize_content(self, content: str, max_length: int = 1024 * 1024) -> str:
        """Sanitize file content for security."""
        if not content:
            return ""
        
        # Remove null bytes and control characters
        content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
        
        # Truncate if too long (prevent memory exhaustion)
        if len(content) > max_length:
            content = content[:max_length] + "\n... [content truncated]"
        
        return content

    def _read_file_safely(self, file_path: Path) -> str:
        """Read file content safely with security checks."""
        try:
            # Check if it's a symlink and resolve it safely
            if file_path.is_symlink():
                # For symlinks, we'll read the target content but mark it as symlink
                target_path = file_path.resolve()
                if not self._is_safe_path(str(target_path.relative_to(Path(self.repo_path)))):
                    return "[symlink to external file - content not read]"
                file_path = target_path
            
            # Check file size to prevent large file attacks
            if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB limit
                return "[file too large - content not read]"
            
            # Read content with encoding handling
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            return self._sanitize_content(content)
            
        except (OSError, UnicodeDecodeError, ValueError) as e:
            return f"[error reading file: {str(e)}]"

    def _collect_changes(self) -> List[FileChange]:
        """Collect all changes in the repository with security and performance improvements."""
        changes = []
        processed_staged = set()
        processed_unstaged = set()
        
        # Get staged changes
        try:
            diff_staged = self.repo.index.diff(self.repo.head.commit)
            for diff in diff_staged:
                file_path = diff.a_path or diff.b_path
                if not file_path or not self._is_safe_path(file_path):
                    continue
                
                processed_staged.add(file_path)
                
                content = ""
                if diff.diff:
                    content = diff.diff.decode('utf-8', errors='replace') if isinstance(diff.diff, bytes) else str(diff.diff)
                    content = self._sanitize_content(content)
                
                changes.append(FileChange(
                    path=file_path,
                    status=diff.change_type,
                    content_diff=content,
                    is_staged=True
                ))
        except Exception as e:
            # Handle git errors gracefully
            print(f"Warning: Error reading staged changes: {e}")
        
        # Get unstaged changes
        try:
            diff_unstaged = self.repo.index.diff(None)
            for diff in diff_unstaged:
                file_path = diff.a_path or diff.b_path
                if not file_path or not self._is_safe_path(file_path):
                    continue
                
                processed_unstaged.add(file_path)
                
                content = ""
                if diff.diff:
                    content = diff.diff.decode('utf-8', errors='replace') if isinstance(diff.diff, bytes) else str(diff.diff)
                    content = self._sanitize_content(content)
                
                changes.append(FileChange(
                    path=file_path,
                    status=diff.change_type,
                    content_diff=content,
                    is_staged=False
                ))
        except Exception as e:
            # Handle git errors gracefully
            print(f"Warning: Error reading unstaged changes: {e}")
        
        # Get untracked files (but not symlinks to external files)
        try:
            for file_path in self.repo.untracked_files:
                if not self._is_safe_path(file_path):
                    continue
                
                if file_path in processed_staged or file_path in processed_unstaged:
                    continue
                
                full_path = Path(self.repo.working_dir) / file_path
                
                # Skip if it's a symlink to external file
                if full_path.is_symlink():
                    target_path = full_path.resolve()
                    if not self._is_safe_path(str(target_path.relative_to(Path(self.repo_path)))):
                        continue
                
                content = self._read_file_safely(full_path)
                
                changes.append(FileChange(
                    path=file_path,
                    status='untracked',
                    content_diff=content,
                    is_staged=False
                ))
        except Exception as e:
            # Handle git errors gracefully
            print(f"Warning: Error reading untracked files: {e}")
        
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
        
        # Check if the AI created proper logical grouping
        # If all files are in one group, use fallback pattern-based grouping
        if len(grouping_result.groups) == 1 and len(grouping_result.groups[0]) > 3:
            print("Warning: AI grouped all files together. Using fallback pattern-based grouping...")
            grouping_result = self._fallback_grouping(changes)
        
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

    def _fallback_grouping(self, changes: List[FileChange]) -> RelationshipResult:
        """Fallback grouping based on file patterns when AI fails to create proper logical units."""
        from pathlib import Path
        
        # Define grouping patterns
        groups = {
            "main_docs": [],
            "web_docs": [],
            "feature_specs": {},
            "other": []
        }
        
        for change in changes:
            path = Path(change.path)
            
            # Group by patterns - check full path, not just filename
            if str(path).startswith("web/"):
                groups["web_docs"].append(change.path)
            elif ".kiro/specs/" in str(path):
                # Extract feature name from path
                parts = str(path).split("/")
                if len(parts) >= 3:
                    feature_name = parts[2]  # e.g., "budget-management"
                    if feature_name not in groups["feature_specs"]:
                        groups["feature_specs"][feature_name] = []
                    groups["feature_specs"][feature_name].append(change.path)
                else:
                    groups["other"].append(change.path)
            elif len(path.parts) == 1 and path.suffix == ".md":
                # Include all root-level markdown files in main_docs
                groups["main_docs"].append(change.path)
            else:
                groups["other"].append(change.path)
        
        # Convert to RelationshipResult format
        result_groups = []
        
        # Add main docs group if not empty
        if groups["main_docs"]:
            result_groups.append(groups["main_docs"])
        
        # Add web docs group if not empty
        if groups["web_docs"]:
            result_groups.append(groups["web_docs"])
        
        # Add feature spec groups
        for feature_name, files in groups["feature_specs"].items():
            if files:
                result_groups.append(files)
        
        # Add other files group if not empty
        if groups["other"]:
            result_groups.append(groups["other"])
        
        # If we still have only one group, try more granular grouping
        if len(result_groups) == 1 and len(result_groups[0]) > 5:
            result_groups = self._granular_fallback_grouping(changes)
        
        return RelationshipResult(
            groups=result_groups,
            reasoning="Files grouped using fallback pattern-based logic due to AI grouping failure"
        )
    
    def _granular_fallback_grouping(self, changes: List[FileChange]) -> List[List[str]]:
        """More granular fallback grouping when basic patterns still result in large groups."""
        from pathlib import Path
        
        # Group by directory structure
        groups = {}
        
        for change in changes:
            path = Path(change.path)
            
            # Get the directory structure as the group key
            if len(path.parts) >= 2:
                # Group by the first two directory levels (e.g., "src/auth", "tests/auth")
                group_key = "/".join(path.parts[:2])
            else:
                group_key = "root"
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(change.path)
        
        return list(groups.values())

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