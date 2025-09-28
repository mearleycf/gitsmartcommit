"""Command for merging changes into the main branch."""

from typing import Optional

from git import Repo
from rich.console import Console

from .base import GitCommand


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
        self.created_main_branch = False

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
                local_branches = [
                    ref.name.split("/")[-1]
                    for ref in self.repo.refs
                    if ref.name.startswith("refs/heads/")
                ]
                if self.main_branch in local_branches:
                    main_exists = True
                    self.console.print(
                        f"[green]Found local branch '{self.main_branch}'[/green]"
                    )
            except Exception as e:
                self.console.print(
                    f"[yellow]Warning checking local branches: {str(e)}[/yellow]"
                )

            # If not found locally, check remote
            if not main_exists:
                try:
                    remote = self.repo.remote()
                    remote_refs = [ref.name.split("/")[-1] for ref in remote.refs]
                    self.console.print(
                        f"[dim]Available remote branches: {', '.join(remote_refs)}[/dim]"
                    )

                    if self.main_branch in remote_refs:
                        try:
                            # Try to check out the remote branch
                            self.repo.git.checkout(self.main_branch)
                            main_exists = True
                            self.console.print(
                                f"[green]Found remote branch '{self.main_branch}'[/green]"
                            )
                        except Exception:
                            # If checkout fails, try to create tracking branch
                            self.repo.git.checkout(
                                "-b",
                                self.main_branch,
                                f"{remote.name}/{self.main_branch}",
                            )
                            main_exists = True
                            self.console.print(
                                f"[green]Created tracking branch for '{self.main_branch}'[/green]"
                            )
                except Exception as e:
                    self.console.print(
                        f"[yellow]Warning checking remote branches: {str(e)}[/yellow]"
                    )

            if not main_exists:
                # Try to create the main branch from the current branch
                self.console.print(
                    f"[yellow]Main branch '{self.main_branch}' does not exist, creating it from current branch...[/yellow]"
                )
                try:
                    # Create the main branch from the current branch
                    self.repo.git.checkout("-b", self.main_branch)
                    self.console.print(
                        f"[green]✓ Created main branch '{self.main_branch}' from current branch[/green]"
                    )
                    main_exists = True
                    self.created_main_branch = True
                except Exception as e:
                    self.console.print(
                        f"[red]Failed to create main branch: {str(e)}[/red]"
                    )
                    return False

            try:
                # Check out main branch if we haven't already (and didn't just create it)
                if (
                    self.repo.active_branch.name != self.main_branch
                    and not self.created_main_branch
                ):
                    self.repo.git.checkout(self.main_branch)

                # Only merge if we didn't just create the main branch
                if self.created_main_branch:
                    # We just created main branch from current branch, so no merge needed
                    self.merge_commit_hash = self.repo.head.commit.hexsha
                    self.console.print(
                        f"[green]✓ Main branch '{self.main_branch}' is ready (no merge needed)[/green]"
                    )
                elif self.original_branch != self.main_branch:
                    # Merge the feature branch
                    self.repo.git.merge(self.original_branch)
                    self.merge_commit_hash = self.repo.head.commit.hexsha
                    self.console.print(
                        f"[green]✓ Successfully merged '{self.original_branch}' into '{self.main_branch}'[/green]"
                    )
                else:
                    # We're already on main branch, so no merge needed
                    self.merge_commit_hash = self.repo.head.commit.hexsha
                    self.console.print(
                        f"[green]✓ Main branch '{self.main_branch}' is ready (no merge needed)[/green]"
                    )

                # Push the merged changes to remote
                remote = self.repo.remote()
                remote.push(refspec=f"{self.main_branch}:{self.main_branch}")
                self.console.print(
                    f"[green]✓ Successfully pushed '{self.main_branch}' to remote[/green]"
                )

                # Notify observers
                for observer in self.observers:
                    await observer.on_merge_completed(
                        True, self.original_branch, self.main_branch
                    )

                # Stay on main branch after successful merge
                self.console.print(
                    f"[green]Successfully merged {self.original_branch} into {self.main_branch}[/green]"
                )

                return True

            except Exception as e:
                self.console.print(f"[red]Failed to merge changes: {str(e)}[/red]")
                # Try to restore original branch on failure
                try:
                    if self.original_branch:
                        self.repo.git.checkout(self.original_branch)
                except (ValueError, AttributeError) as e:
                    self.console.print(
                        f"[yellow]Warning: Could not restore original branch {self.original_branch}: {e}[/yellow]"
                    )
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
            self.repo.git.reset("--hard", f"{self.merge_commit_hash}^")

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
