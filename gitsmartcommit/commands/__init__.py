"""Git operation commands using the Command Pattern.

This package implements the Command Pattern for git operations, allowing for:
1. Encapsulation of git operations as objects
2. Support for undo operations
3. Command history tracking
4. Integration with the Observer Pattern for notifications

Example:
    ```python
    # Create and execute a commit command
    from gitsmartcommit.commands import CommitCommand

    commit_cmd = CommitCommand(repo, commit_unit)
    success = await commit_cmd.execute()

    # Add an observer to be notified of git operations
    from gitsmartcommit.observers import FileLogObserver
    observer = FileLogObserver("git.log")
    commit_cmd.add_observer(observer)

    # Undo the commit if needed
    success = await commit_cmd.undo()
    ```
"""

from .base import GitCommand
from .commit import CommitCommand
from .merge import MergeCommand
from .push import PushCommand
from .upstream import SetUpstreamCommand

__all__ = [
    "GitCommand",
    "CommitCommand",
    "MergeCommand",
    "PushCommand",
    "SetUpstreamCommand",
]
