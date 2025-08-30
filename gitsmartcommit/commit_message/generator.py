"""Enhanced commit message generation."""
from typing import Optional, List
from pathlib import Path
from git import Repo

from ..models import FileChange, CommitMessageResult
from .strategy import CommitMessageStrategy, ConventionalCommitStrategy, OllamaCommitStrategy
from .validator import CommitMessageValidator

class CommitMessageGenerator:
    """Enhanced commit message generator with validation and context enrichment."""
    
    def __init__(self, strategy: Optional[CommitMessageStrategy] = None):
        if strategy is None:
            raise ValueError("Strategy must be provided to CommitMessageGenerator")
        self.strategy = strategy
        self.validator = CommitMessageValidator()
        
    def _enrich_context(self, changes: List[FileChange], repo: Repo) -> str:
        """Add additional context to help generate better commit messages."""
        context = []
        
        # Analyze file types and patterns
        patterns = {
            'test': ['test', 'spec', '__tests__'],
            'config': ['.config.', '.json', '.yaml', '.yml'],
            'docs': ['README', 'CHANGELOG', 'docs/', '.md'],
            'ci': ['.github/', 'jenkins', 'travis', 'gitlab-ci'],
        }
        
        file_contexts = []
        for change in changes:
            path = Path(change.path)
            contexts = []
            
            for category, pattern_list in patterns.items():
                if any(pattern in str(path) for pattern in pattern_list):
                    contexts.append(category)
                    
            if contexts:
                file_contexts.append(f"{change.path}: {', '.join(contexts)}")
            
        if file_contexts:
            context.append("File types:")
            context.extend(f"- {fc}" for fc in file_contexts)
            
        # Add branch context
        try:
            branch = repo.active_branch.name
            context.append(f"\nCurrent branch: {branch}")
            
            # Get recent commits from this branch
            commits = list(repo.iter_commits(max_count=3))
            if commits:
                context.append("\nRecent commits:")
                for commit in commits:
                    # Get first line of commit message
                    msg = commit.message.split('\n')[0]
                    context.append(f"- {msg}")
        except Exception:
            # Handle detached HEAD or other git issues gracefully
            pass
            
        return "\n".join(context)
        
    async def generate_commit_message(self, changes: List[FileChange], repo: Repo) -> CommitMessageResult:
        """Generate a validated commit message with enriched context."""
        # Get enriched context
        context = self._enrich_context(changes, repo)
        
        # Generate message using the strategy
        result = await self.strategy.generate_message(changes, context)
        if not result:
            return None

        # Validate the result
        message = (f"{result.commit_type.value}" +
                  (f"({result.scope}): " if result.scope else ": ") +
                  f"{result.description}")

        if result.reasoning:
            message += "\n\n" + result.reasoning

        # Validate and regenerate if needed
        is_valid, validation_msg = self.validator.validate(message)
        if not is_valid:
            # Try one more time with validation feedback
            result = await self.strategy.generate_message(
                changes,
                context + f"\n\nPrevious attempt failed validation: {validation_msg}\n"
                "Please make sure to follow all formatting rules exactly."
            )

        return result 