"""Git operation commands using the Command Pattern."""
from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path
from git import Repo
from rich.console import Console

from .models import CommitUnit
from .observers import GitOperationObserver

class GitCommand(ABC):
    """Abstract base class for git commands."""
    
    def __init__(self, repo: Repo, console: Optional[Console] = None):
        self.repo = repo
        self.console = console or Console()
        self.observers: List[GitOperationObserver] = []
    
    def add_observer(self, observer: GitOperationObserver) -> None:
        """Add an observer to be notified of command execution."""
        self.observers.append(observer)
    
    def remove_observer(self, observer: GitOperationObserver) -> None:
        """Remove an observer from the notification list."""
        self.observers.remove(observer)
    
    @abstractmethod
    async def execute(self) -> bool:
        """Execute the git command."""
        pass
    
    @abstractmethod
    async def undo(self) -> bool:
        """Undo the git command."""
        pass

class CommitCommand(GitCommand):
    """Command for creating a git commit."""
    
    def __init__(self, repo: Repo, commit_unit: CommitUnit, console: Optional[Console] = None):
        super().__init__(repo, console)
        self.commit_unit = commit_unit
        self.commit_hash: Optional[str] = None
    
    async def execute(self) -> bool:
        """Create a commit with the specified commit unit."""
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
        """Undo the commit by resetting to the previous commit."""
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
    """Command for pushing changes to a remote repository."""
    
    def __init__(self, repo: Repo, console: Optional[Console] = None):
        super().__init__(repo, console)
        self.pushed_commits: List[str] = []
    
    async def execute(self) -> bool:
        """Push commits to the remote repository."""
        try:
            # Check if remote exists
            if not self.repo.remotes:
                self.console.print("[red]No remote repository configured[/red]")
                success = False
            else:
                remote = self.repo.remote()
                current_branch = self.repo.active_branch
                
                # Store current commit hash for potential undo
                self.pushed_commits = [c.hexsha for c in self.repo.iter_commits(f"{current_branch.name}@{{u}}..{current_branch.name}")]
                
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
        """Undo the push by force pushing to the previous state."""
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