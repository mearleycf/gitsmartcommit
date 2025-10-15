"""Observer pattern for git operations."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.console import Console

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

    @abstractmethod
    async def on_merge_completed(
        self, success: bool, source_branch: str, target_branch: str
    ) -> None:
        """Called when a merge operation completes."""
        pass


class ConsoleLogObserver(GitOperationObserver):
    """Observer that logs git operations to the console."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    async def on_commit_created(self, commit_unit: CommitUnit) -> None:
        self.console.print(f"[green]Created commit: {commit_unit.message}[/green]")

    async def on_push_completed(self, success: bool) -> None:
        if success:
            self.console.print("[green]Successfully pushed changes to remote[/green]")
        else:
            self.console.print("[red]Failed to push changes to remote[/red]")

    async def on_merge_completed(
        self, success: bool, source_branch: str, target_branch: str
    ) -> None:
        if success:
            self.console.print(
                f"[green]Successfully merged {source_branch} into {target_branch}[/green]"
            )
        else:
            self.console.print(
                f"[red]Failed to merge {source_branch} into {target_branch}[/red]"
            )


class FileLogObserver(GitOperationObserver):
    """Observer that logs git operations to a file."""

    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
        # Ensure the parent directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    async def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.log_file.open("a") as f:
            f.write(f"{timestamp} - {message}\n")

    async def on_commit_created(self, commit_unit: CommitUnit) -> None:
        await self._log(f"Created commit: {commit_unit.message}")

    async def on_push_completed(self, success: bool) -> None:
        status = "Successfully" if success else "Failed to"
        await self._log(f"{status} push changes to remote")

    async def on_merge_completed(
        self, success: bool, source_branch: str, target_branch: str
    ) -> None:
        status = "Successfully" if success else "Failed to"
        await self._log(f"{status} merge {source_branch} into {target_branch}")
