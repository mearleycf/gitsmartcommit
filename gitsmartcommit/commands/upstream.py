"""Command for setting the upstream branch."""

from typing import Optional

from git import Repo
from rich.console import Console

from .base import GitCommand


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
                    self.console.print(
                        f"[green]✓ Branch '{self.branch_name}' already has upstream set to '{upstream.name}'[/green]"
                    )
                    self.had_upstream = True
                    self.previous_upstream = upstream.name
                    return True
            except (AttributeError, ValueError) as e:
                # These are expected exceptions when no upstream is set
                self.console.print(f"[dim]No upstream tracking branch found: {e}[/dim]")

            # No upstream set, so set it
            upstream_name = f"origin/{self.branch_name}"

            # Check if the remote branch exists
            try:
                remote_ref = self.repo.refs[f"origin/{self.branch_name}"]
                remote_exists = True
            except (KeyError, IndexError):
                remote_exists = False

            if not remote_exists:
                self.console.print(
                    f"[yellow]⚠ Remote branch '{upstream_name}' does not exist yet[/yellow]"
                )
                self.console.print(
                    f"[yellow]  This is normal for new branches. Upstream will be set when you first push.[/yellow]"
                )
                # For new branches, we'll set upstream during the first push
                # Store this information for the PushCommand to use
                self.had_upstream = False
                self.previous_upstream = None
                return True

            # Set the upstream
            self.console.print(
                f"[blue]Setting upstream for '{self.branch_name}' to '{upstream_name}'...[/blue]"
            )

            # Use git command to set upstream
            result = self.repo.git.branch("--set-upstream-to", upstream_name)

            if result is None or result == "":
                self.console.print(
                    f"[green]✓ Successfully set upstream for '{self.branch_name}' to '{upstream_name}'[/green]"
                )

                # Notify observers
                for observer in self.observers:
                    observer.on_git_operation(
                        operation="set_upstream",
                        details=f"Set upstream for {self.branch_name} to {upstream_name}",
                        success=True,
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
                    success=False,
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
                self.console.print(
                    f"[yellow]⚠ Cannot undo upstream setting (previous upstream was '{self.previous_upstream}')[/yellow]"
                )
                return False

            # Remove the upstream setting
            self.console.print(
                f"[blue]Removing upstream for '{self.branch_name}'...[/blue]"
            )

            # Use git command to unset upstream
            result = self.repo.git.branch("--unset-upstream")

            if result is None or result == "":
                self.console.print(
                    f"[green]✓ Successfully removed upstream for '{self.branch_name}'[/green]"
                )
                return True
            else:
                self.console.print(f"[red]✗ Failed to remove upstream: {result}[/red]")
                return False

        except Exception as e:
            self.console.print(f"[red]✗ Error removing upstream: {str(e)}[/red]")
            return False
