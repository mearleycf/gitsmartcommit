"""Base command class for git operations.

This module provides the abstract base class for all git commands,
implementing the Command Pattern with observer support.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from git import Repo
from rich.console import Console

from ..observers import GitOperationObserver


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
