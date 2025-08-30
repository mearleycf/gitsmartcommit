"""Git operation commands using the Command Pattern.

This module implements the Command Pattern for git operations, allowing for:
1. Encapsulation of git operations as objects
2. Support for undo operations
3. Command history tracking
4. Integration with the Observer Pattern for notifications

Example:
    ```python
    # Create and execute a commit command
    commit_cmd = CommitCommand(repo, commit_unit)
    success = await commit_cmd.execute()
    
    # Add an observer to be notified of git operations
    observer = FileLogObserver("git.log")
    commit_cmd.add_observer(observer)
    
    # Undo the commit if needed
    success = await commit_cmd.undo()
    ```
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path
from git import Repo
from rich.console import Console

from .models import CommitUnit
from .observers import GitOperationObserver

class GitCommand(ABC):
    """Abstract base class for git commands.
    
    This class defines the interface for all git commands and provides common
    functionality for observer management. Concrete commands should implement
    the execute() and undo() methods.
    
    Attributes:
        repo (Repo): The git repository to operate on
        console (Console): Rich console for output
        observers (List[GitOperationObserver]): List of observers to notify
    """
    
    def __init__(self, repo: Repo, console: Optional[Console] = None):
        """Initialize the command.
        
        Args:
            repo: The git repository to operate on
            console: Optional Rich console for output
        """
        self.repo = repo
        self.console = console or Console()
        self.observers: List[GitOperationObserver] = []
    
    def add_observer(self, observer: GitOperationObserver) -> None:
        """Add an observer to be notified of command execution.
        
        Args:
            observer: The observer to add
        """
        self.observers.append(observer)
    
    def remove_observer(self, observer: GitOperationObserver) -> None:
        """Remove an observer from the notification list.
        
        Args:
            observer: The observer to remove
        """
        self.observers.remove(observer)
    
    @abstractmethod
    async def execute(self) -> bool:
        """Execute the git command.
        
        Returns:
            bool: True if the command was executed successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def undo(self) -> bool:
        """Undo the git command.
        
        Returns:
            bool: True if the command was undone successfully, False otherwise
        """
        pass

class SetUpstreamCommand(GitCommand):
    """Command for setting the upstream branch.
    
    This command handles:
    1. Checking if the current branch has an upstream set
    2. Setting the upstream to origin/<branch-name> if not set
    3. Notifying observers of the operation
    4. Supporting undo (though this is limited)
    
    Attributes:
        branch_name (str): The name of the current branch
    """
    
    def __init__(self, repo: Repo, console: Optional[Console] = None):
        """Initialize the command.
        
        Args:
            repo: The git repository to operate on
            console: Optional Rich console for output
        """
        super().__init__(repo, console)
        self.branch_name = repo.active_branch.name
        self.had_upstream = False
        self.previous_upstream = None
    
    async def execute(self) -> bool:
        """Set the upstream branch if not already set.
        
        Returns:
            bool: True if the operation was successful, False otherwise
        """
        try:
            # Check if current branch has upstream set
            current_branch = self.repo.active_branch
            
            # Check if upstream is set
            try:
                upstream = current_branch.tracking_branch()
                if upstream is not None:
                    self.console.print(f"[green]✓ Branch '{self.branch_name}' already has upstream set to '{upstream.name}'[/green]")
                    self.had_upstream = True
                    self.previous_upstream = upstream.name
                    return True
            except Exception:
                pass
            
            # No upstream set, so set it
            upstream_name = f"origin/{self.branch_name}"
            
            # Check if the remote branch exists
            try:
                remote_ref = self.repo.refs[f"origin/{self.branch_name}"]
                remote_exists = True
            except (KeyError, IndexError):
                remote_exists = False
            
            if not remote_exists:
                self.console.print(f"[yellow]⚠ Remote branch '{upstream_name}' does not exist yet[/yellow]")
                self.console.print(f"[yellow]  This is normal for new branches. Upstream will be set when you first push.[/yellow]")
                return True
            
            # Set the upstream
            self.console.print(f"[blue]Setting upstream for '{self.branch_name}' to '{upstream_name}'...[/blue]")
            
            # Use git command to set upstream
            result = self.repo.git.branch('--set-upstream-to', upstream_name)
            
            if result is None or result == "":
                self.console.print(f"[green]✓ Successfully set upstream for '{self.branch_name}' to '{upstream_name}'[/green]")
                
                # Notify observers
                for observer in self.observers:
                    observer.on_git_operation(
                        operation="set_upstream",
                        details=f"Set upstream for {self.branch_name} to {upstream_name}",
                        success=True
                    )
                
                return True
            else:
                self.console.print(f"[red]✗ Failed to set upstream: {result}[/red]")
                return False
                
        except Exception as e:
            self.console.print(f"[red]✗ Error setting upstream: {str(e)}[/red]")
            
            # Notify observers
            for observer in self.observers:
                observer.on_git_operation(
                    operation="set_upstream",
                    details=f"Failed to set upstream: {str(e)}",
                    success=False
                )
            
            return False
    
    async def undo(self) -> bool:
        """Undo the upstream setting (limited functionality).
        
        Returns:
            bool: True if the operation was successful, False otherwise
        """
        try:
            if self.had_upstream:
                # If there was already an upstream, we can't easily restore it
                self.console.print(f"[yellow]⚠ Cannot undo upstream setting (previous upstream was '{self.previous_upstream}')[/yellow]")
                return False
            
            # Remove the upstream setting
            self.console.print(f"[blue]Removing upstream for '{self.branch_name}'...[/blue]")
            
            # Use git command to unset upstream
            result = self.repo.git.branch('--unset-upstream')
            
            if result is None or result == "":
                self.console.print(f"[green]✓ Successfully removed upstream for '{self.branch_name}'[/green]")
                return True
            else:
                self.console.print(f"[red]✗ Failed to remove upstream: {result}[/red]")
                return False
                
        except Exception as e:
            self.console.print(f"[red]✗ Error removing upstream: {str(e)}[/red]")
            return False

class CommitCommand(GitCommand):
    """Command for creating a git commit.
    
    This command handles:
    1. Staging files for commit
    2. Creating the commit with the specified message
    3. Notifying observers of the commit
    4. Supporting undo via reset
    
    Attributes:
        commit_unit (CommitUnit): The commit unit containing files and message
        commit_hash (Optional[str]): The hash of the created commit
    """
    
    def __init__(self, repo: Repo, commit_unit: CommitUnit, console: Optional[Console] = None):
        """Initialize the commit command.
        
        Args:
            repo: The git repository to operate on
            commit_unit: The commit unit containing files and message
            console: Optional Rich console for output
        """
        super().__init__(repo, console)
        self.commit_unit = commit_unit
        self.commit_hash: Optional[str] = None
    
    async def execute(self) -> bool:
        """Create a commit with the specified commit unit.
        
        This method will:
        1. Stage all files in the commit unit
        2. Create the commit with the formatted message
        3. Store the commit hash for potential undo
        4. Notify observers
        
        Returns:
            bool: True if the commit was created successfully, False otherwise
        """
        try:
            # Stage files for this commit
            for file_path in self.commit_unit.files:
                file_exists = Path(self.repo.working_dir) / file_path
                if file_exists.exists():
                    self.repo.index.add([file_path])
                else:
                    # Handle deleted files
                    try:
                        self.repo.index.remove([file_path])
                    except:
                        # If the file is already staged for deletion, continue
                        pass
            
            # Create commit message
            message = f"{self.commit_unit.type.value}"
            if self.commit_unit.scope:
                message += f"({self.commit_unit.scope})"
            message += f": {self.commit_unit.description}"
            if self.commit_unit.body:
                message += f"\n\n{self.commit_unit.body}"
            
            # Create commit
            commit = self.repo.index.commit(message)
            self.commit_hash = commit.hexsha
            
            # Notify observers
            for observer in self.observers:
                await observer.on_commit_created(self.commit_unit)
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]Failed to create commit: {str(e)}[/red]")
            return False
    
    async def undo(self) -> bool:
        """Undo the commit by resetting to the previous commit.
        
        This method will:
        1. Check if there's a commit to undo
        2. Reset the repository to the parent commit
        3. Clear the stored commit hash
        
        Returns:
            bool: True if the commit was undone successfully, False otherwise
        """
        if not self.commit_hash:
            self.console.print("[yellow]No commit to undo[/yellow]")
            return False
        
        try:
            # Reset to the parent commit
            self.repo.git.reset('--hard', 'HEAD~1')
            self.commit_hash = None
            return True
            
        except Exception as e:
            self.console.print(f"[red]Failed to undo commit: {str(e)}[/red]")
            return False

class PushCommand(GitCommand):
    """Command for pushing changes to a remote repository.
    
    This command handles:
    1. Checking for remote repository
    2. Setting up tracking branches
    3. Pushing changes
    4. Supporting undo via force push
    
    Attributes:
        pushed_commits (List[str]): List of commit hashes that were pushed
    """
    
    def __init__(self, repo: Repo, console: Optional[Console] = None):
        """Initialize the push command.
        
        Args:
            repo: The git repository to operate on
            console: Optional Rich console for output
        """
        super().__init__(repo, console)
        self.pushed_commits: List[str] = []
    
    async def execute(self) -> bool:
        """Push commits to the remote repository.
        
        This method will:
        1. Check if a remote repository is configured
        2. Check if the current branch has an upstream
        3. Set up tracking if needed
        4. Push the changes
        5. Store pushed commits for potential undo
        6. Notify observers
        
        Returns:
            bool: True if the push was successful, False otherwise
        """
        try:
            # Check if remote exists
            if not self.repo.remotes:
                self.console.print("[red]No remote repository configured[/red]")
                success = False
            else:
                remote = self.repo.remote()
                current_branch = self.repo.active_branch
                
                # Check if branch has upstream tracking
                try:
                    tracking_branch = current_branch.tracking_branch()
                    if tracking_branch is None:
                        # Try to set up tracking to origin/current_branch
                        self.console.print(f"[yellow]Setting up tracking for branch {current_branch.name}[/yellow]")
                        try:
                            # First try to push and set upstream
                            remote.push(f"{current_branch.name}:refs/heads/{current_branch.name}", set_upstream=True)
                            success = True
                        except Exception as e:
                            if "remote ref does not exist" in str(e):
                                # Remote branch doesn't exist, give clear instructions
                                self.console.print(
                                    f"[red]Branch '{current_branch.name}' does not exist on remote.\n"
                                    "To create it, run:[/red]\n"
                                    f"[yellow]git push --set-upstream origin {current_branch.name}[/yellow]"
                                )
                            else:
                                # Some other push error
                                self.console.print(f"[red]Failed to push changes: {str(e)}[/red]")
                            success = False
                    else:
                        # Branch has tracking, do normal push
                        remote.push()
                        success = True
                        
                    # Store current commit hash for potential undo (only after upstream is set)
                    if success and tracking_branch is not None:
                        self.pushed_commits = [c.hexsha for c in self.repo.iter_commits(f"{current_branch.name}@{{u}}..{current_branch.name}")]
                    elif success:
                        # For new branches, store all commits since we're pushing everything
                        self.pushed_commits = [c.hexsha for c in self.repo.iter_commits(f"{current_branch.name}")]
                except Exception as e:
                    self.console.print(f"[red]Failed to push changes: {str(e)}[/red]")
                    success = False
            
            # Notify observers
            for observer in self.observers:
                await observer.on_push_completed(success)
            
            return success
            
        except Exception as e:
            self.console.print(f"[red]Failed to push changes: {str(e)}[/red]")
            return False
    
    async def undo(self) -> bool:
        """Undo the push by force pushing to the previous state.
        
        This method will:
        1. Check if there are commits to undo
        2. Force push to the commit before our pushed commits
        3. Clear the stored commit hashes
        
        Returns:
            bool: True if the push was undone successfully, False otherwise
        
        Warning:
            This operation uses force push and should be used with caution
            as it can potentially overwrite remote changes.
        """
        if not self.pushed_commits:
            self.console.print("[yellow]No pushed commits to undo[/yellow]")
            return False
        
        try:
            current_branch = self.repo.active_branch
            remote = self.repo.remote()
            
            # Force push to the commit before our pushed commits
            remote.push(f"{current_branch.name}^:refs/heads/{current_branch.name}", force=True)
            self.pushed_commits = []
            return True
            
        except Exception as e:
            self.console.print(f"[red]Failed to undo push: {str(e)}[/red]")
            return False

class MergeCommand(GitCommand):
    """Command for merging changes into the main branch.
    
    This command handles:
    1. Storing the current branch name
    2. Checking out the main branch
    3. Merging the feature branch
    4. Pushing the merged changes
    5. Restoring the original branch (on undo)
    
    Attributes:
        main_branch (str): Name of the main branch to merge into
        original_branch (str): Name of the branch we were on before merging
        merge_commit_hash (Optional[str]): Hash of the merge commit
    """
    
    def __init__(self, repo: Repo, main_branch: str, console: Optional[Console] = None):
        """Initialize the merge command.
        
        Args:
            repo: The git repository to operate on
            main_branch: Name of the main branch to merge into
            console: Optional Rich console for output
        """
        super().__init__(repo, console)
        self.main_branch = main_branch
        self.original_branch = None
        self.merge_commit_hash = None
    
    async def execute(self) -> bool:
        """Merge the current branch into the main branch.
        
        This method will:
        1. Store current branch name
        2. Check out the main branch
        3. Merge the feature branch
        4. Push the merged changes
        5. Notify observers
        
        Returns:
            bool: True if the merge was successful, False otherwise
        """
        try:
            # Store current branch
            self.original_branch = self.repo.active_branch.name
            
            # Check if main branch exists (either locally or remotely)
            main_exists = False
            
            # First check if the branch exists locally
            try:
                # List all local branches
                local_branches = [ref.name.split('/')[-1] for ref in self.repo.refs if ref.name.startswith('refs/heads/')]
                if self.main_branch in local_branches:
                    main_exists = True
                    self.console.print(f"[green]Found local branch '{self.main_branch}'[/green]")
            except Exception as e:
                self.console.print(f"[yellow]Warning checking local branches: {str(e)}[/yellow]")
            
            # If not found locally, check remote
            if not main_exists:
                try:
                    remote = self.repo.remote()
                    remote_refs = [ref.name.split('/')[-1] for ref in remote.refs]
                    self.console.print(f"[dim]Available remote branches: {', '.join(remote_refs)}[/dim]")
                    
                    if self.main_branch in remote_refs:
                        try:
                            # Try to check out the remote branch
                            self.repo.git.checkout(self.main_branch)
                            main_exists = True
                            self.console.print(f"[green]Found remote branch '{self.main_branch}'[/green]")
                        except Exception:
                            # If checkout fails, try to create tracking branch
                            self.repo.git.checkout("-b", self.main_branch, f"{remote.name}/{self.main_branch}")
                            main_exists = True
                            self.console.print(f"[green]Created tracking branch for '{self.main_branch}'[/green]")
                except Exception as e:
                    self.console.print(f"[yellow]Warning checking remote branches: {str(e)}[/yellow]")
            
            if not main_exists:
                self.console.print(f"[red]Main branch '{self.main_branch}' does not exist locally or remotely[/red]")
                return False
            
            try:
                # Check out main branch if we haven't already
                if self.repo.active_branch.name != self.main_branch:
                    self.repo.git.checkout(self.main_branch)
                
                # Merge the feature branch
                self.repo.git.merge(self.original_branch)
                self.merge_commit_hash = self.repo.head.commit.hexsha
                
                # Push the merged changes to remote
                remote = self.repo.remote()
                remote.push(refspec=f"{self.main_branch}:{self.main_branch}")
                
                # Notify observers
                for observer in self.observers:
                    await observer.on_merge_completed(True, self.original_branch, self.main_branch)
                
                # Stay on main branch after successful merge
                self.console.print(f"[green]Successfully merged {self.original_branch} into {self.main_branch}[/green]")
                
                return True
                
            except Exception as e:
                self.console.print(f"[red]Failed to merge changes: {str(e)}[/red]")
                # Try to restore original branch on failure
                try:
                    if self.original_branch:
                        self.repo.git.checkout(self.original_branch)
                except:
                    pass
                return False
                
        except Exception as e:
            self.console.print(f"[red]Failed to merge changes: {str(e)}[/red]")
            return False
    
    async def undo(self) -> bool:
        """Undo the merge by resetting main branch and restoring original branch.
        
        This method will:
        1. Check out main branch
        2. Reset to before merge
        3. Force push the reset
        4. Restore original branch
        
        Returns:
            bool: True if the merge was undone successfully, False otherwise
        """
        if not self.merge_commit_hash or not self.original_branch:
            self.console.print("[yellow]No merge to undo[/yellow]")
            return False
        
        try:
            # Check out main branch
            self.repo.git.checkout(self.main_branch)
            
            # Reset to before merge
            self.repo.git.reset('--hard', f'{self.merge_commit_hash}^')
            
            # Force push the reset
            remote = self.repo.remote()
            remote.push(force=True)
            
            # Restore original branch
            self.repo.git.checkout(self.original_branch)
            
            self.merge_commit_hash = None
            return True
            
        except Exception as e:
            self.console.print(f"[red]Failed to undo merge: {str(e)}[/red]")
            return False 