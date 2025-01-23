"""Observer pattern implementation for git operations."""
from abc import ABC, abstractmethod
from typing import List
from .models import CommitUnit

class GitOperationObserver(ABC):
    """Abstract base class for git operation observers."""
    
    @abstractmethod
    async def on_commit_created(self, commit_unit: CommitUnit) -> None:
        """Called when a commit is created."""
        pass
    
    @abstractmethod
    async def on_push_completed(self, success: bool) -> None:
        """Called when a push operation completes."""
        pass

class ConsoleLogObserver(GitOperationObserver):
    """Observer that logs git operations to the console."""
    
    def __init__(self, console):
        self.console = console
    
    async def on_commit_created(self, commit_unit: CommitUnit) -> None:
        self.console.print(
            f"[green]Created commit: {commit_unit.type.value}"
            f"({commit_unit.scope}): {commit_unit.description}[/green]"
        )
    
    async def on_push_completed(self, success: bool) -> None:
        if success:
            self.console.print("[green]Successfully pushed changes to remote[/green]")
        else:
            self.console.print("[red]Failed to push changes to remote[/red]")

class FileLogObserver(GitOperationObserver):
    """Observer that logs git operations to a file."""
    
    def __init__(self, log_file: str):
        self.log_file = log_file
    
    async def on_commit_created(self, commit_unit: CommitUnit) -> None:
        with open(self.log_file, 'a') as f:
            f.write(
                f"COMMIT: {commit_unit.type.value}"
                f"({commit_unit.scope}): {commit_unit.description}\n"
                f"Files: {', '.join(commit_unit.files)}\n"
                f"Body: {commit_unit.body}\n\n"
            )
    
    async def on_push_completed(self, success: bool) -> None:
        with open(self.log_file, 'a') as f:
            if success:
                f.write("PUSH: Successfully pushed changes to remote\n\n")
            else:
                f.write("PUSH: Failed to push changes to remote\n\n") 