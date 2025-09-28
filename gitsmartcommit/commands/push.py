"""Command for pushing changes to remote repository."""

from typing import List, Optional

from git import Repo
from rich.console import Console

from .base import GitCommand


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
                        self.console.print(
                            f"[yellow]Setting up tracking for branch {current_branch.name}[/yellow]"
                        )
                        try:
                            # First try to push and set upstream - this will create the remote branch if it doesn't exist
                            remote.push(
                                f"{current_branch.name}:refs/heads/{current_branch.name}",
                                set_upstream=True,
                            )
                            self.console.print(
                                f"[green]✓ Successfully created upstream branch and pushed changes[/green]"
                            )
                            success = True
                        except Exception as e:
                            # If the push with set_upstream fails, try a different approach
                            self.console.print(
                                f"[yellow]First push attempt failed, trying alternative approach...[/yellow]"
                            )
                            try:
                                # Try to push without set_upstream first
                                remote.push(
                                    f"{current_branch.name}:refs/heads/{current_branch.name}"
                                )
                                # Then set upstream manually
                                current_branch.set_tracking_branch(
                                    remote.refs[f"refs/heads/{current_branch.name}"]
                                )
                                self.console.print(
                                    f"[green]✓ Successfully created upstream branch and pushed changes[/green]"
                                )
                                success = True
                            except Exception as e2:
                                self.console.print(
                                    f"[red]Failed to push changes: {str(e2)}[/red]"
                                )
                                success = False
                    else:
                        # Branch has tracking, do normal push
                        remote.push()
                        success = True

                    # Store current commit hash for potential undo (only after upstream is set)
                    if success and tracking_branch is not None:
                        self.pushed_commits = [
                            c.hexsha
                            for c in self.repo.iter_commits(
                                f"{current_branch.name}@{{u}}..{current_branch.name}"
                            )
                        ]
                    elif success:
                        # For new branches, store all commits since we're pushing everything
                        self.pushed_commits = [
                            c.hexsha
                            for c in self.repo.iter_commits(f"{current_branch.name}")
                        ]
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
            remote.push(
                f"{current_branch.name}^:refs/heads/{current_branch.name}", force=True
            )
            self.pushed_commits = []
            return True

        except Exception as e:
            self.console.print(f"[red]Failed to undo push: {str(e)}[/red]")
            return False
