"""Command for creating git commits."""

import os
import tempfile
from pathlib import Path
from typing import Optional

from git import Repo
from rich.console import Console

from ..models import CommitUnit
from .base import GitCommand


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

    def __init__(
        self,
        repo: Repo,
        commit_unit: CommitUnit,
        console: Optional[Console] = None,
        no_verify: bool = False,
    ):
        """Initialize the commit command.

        Args:
            repo: The git repository to operate on
            commit_unit: The commit unit containing files and message
            console: Optional Rich console for output
            no_verify: Skip pre-commit hooks when creating commits
        """
        super().__init__(repo, console)
        self.commit_unit = commit_unit
        self.commit_hash: Optional[str] = None
        self.no_verify = no_verify

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
            # Check if there are any changes to commit first
            if not self.repo.is_dirty() and not self.repo.untracked_files:
                self.console.print("[yellow]No changes to commit, skipping...[/yellow]")
                return True

            # Stage files for this commit
            staged_files = []
            for file_path in self.commit_unit.files:
                file_exists = Path(self.repo.working_dir) / file_path
                if file_exists.exists():
                    # Check if file is already staged
                    try:
                        # Get the diff to see if there are actual changes
                        diff = self.repo.index.diff(
                            self.repo.head.commit, paths=[file_path]
                        )
                        if diff or file_path in self.repo.untracked_files:
                            self.repo.index.add([file_path])
                            staged_files.append(file_path)
                    except Exception:
                        # If there's an error checking diff, try to stage anyway
                        self.repo.index.add([file_path])
                        staged_files.append(file_path)
                else:
                    # Handle deleted files
                    try:
                        self.repo.index.remove([file_path])
                        staged_files.append(file_path)
                    except (ValueError, KeyError) as e:
                        # If the file is already staged for deletion or doesn't exist, continue
                        self.console.print(
                            f"[dim]File {file_path} already staged for deletion or not found: {e}[/dim]"
                        )

            # Check if we actually staged anything
            if not staged_files:
                self.console.print(
                    f"[yellow]No changes to stage for commit unit: {self.commit_unit.description}[/yellow]"
                )
                return True

            # Double-check that we have staged changes before committing
            staged_diff = self.repo.index.diff(self.repo.head.commit)
            if not staged_diff and not self.repo.untracked_files:
                self.console.print(
                    "[yellow]No staged changes to commit, skipping...[/yellow]"
                )
                return True

            # Create commit message
            message = f"{self.commit_unit.type.value}"
            if self.commit_unit.scope:
                message += f"({self.commit_unit.scope})"
            message += f": {self.commit_unit.description}"
            if self.commit_unit.body:
                message += f"\n\n{self.commit_unit.body}"

            # Create commit
            if self.no_verify:
                # Use git command directly to bypass pre-commit hooks
                # Properly handle multi-line messages by using the -F flag with a temporary file
                with tempfile.NamedTemporaryFile(
                    mode="w", delete=False, suffix=".commitmsg"
                ) as f:
                    f.write(message)
                    temp_file = f.name

                try:
                    commit = self.repo.git.commit("-F", temp_file, "--no-verify")
                    # Get the commit hash from the last commit
                    self.commit_hash = self.repo.head.commit.hexsha
                finally:
                    # Clean up the temporary file
                    try:
                        os.unlink(temp_file)
                    except OSError:
                        pass
            else:
                # Use the standard index.commit method
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
            self.repo.git.reset("--hard", "HEAD~1")
            self.commit_hash = None
            return True

        except Exception as e:
            self.console.print(f"[red]Failed to undo commit: {str(e)}[/red]")
            return False
