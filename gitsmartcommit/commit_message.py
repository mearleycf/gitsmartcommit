"""Enhanced commit message generation."""
from typing import List, Optional, Tuple
from pathlib import Path
from git import Repo
from pydantic_ai import Agent

from .models import FileChange, CommitMessageResult
from .prompts import COMMIT_MESSAGE_PROMPT

class CommitMessageValidator:
    """Validates commit messages against conventional commit standards."""
    
    def __init__(self):
        self.max_subject_length = 50
        self.max_body_line_length = 72
        
    def validate(self, message: str) -> Tuple[bool, str]:
        """Validate a commit message against standards."""
        lines = message.split('\n')
        if not lines:
            return False, "Empty commit message"
            
        subject = lines[0]
        
        # Validate subject line
        if len(subject) > self.max_subject_length:
            return False, f"Subject line too long ({len(subject)} > {self.max_subject_length})"
            
        if subject.endswith('.'):
            return False, "Subject line should not end with a period"
            
        # Validate conventional commit format
        if ':' not in subject:
            return False, "Subject line must follow format: type(scope): description"
            
        # Validate body
        if len(lines) > 1:
            if not lines[1] == '':
                return False, "Leave one blank line after subject"
                
            for line in lines[2:]:
                if len(line) > self.max_body_line_length:
                    return False, f"Body line too long: {line}"
                    
        return True, "Valid commit message"

class CommitMessageGenerator(Agent):
    """Enhanced commit message generator with validation and context enrichment."""
    
    def __init__(self, model: str = 'anthropic:claude-3-5-sonnet-latest'):
        super().__init__(
            model=model,
            result_type=CommitMessageResult,
            system_prompt=COMMIT_MESSAGE_PROMPT
        )
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
        
        # Prepare change descriptions
        changes_desc = []
        for change in changes:
            # Truncate very large diffs to avoid prompt size issues
            diff = change.content_diff[:1000] + "..." if len(change.content_diff) > 1000 else change.content_diff
            changes_desc.append(f"{change.path} ({change.status}):\n{diff}")
            
        prompt = f"""Please analyze these changes and generate a commit message following these guidelines:

Changes to analyze:
{chr(10).join(changes_desc)}

Context:
{context}

Key Requirements:
1. Each commit should represent ONE logical unit of work
2. Explain WHY changes were made, not WHAT was changed
3. Use conventional commit format: type(scope): description
4. Subject line must:
   - Start with lowercase
   - Use imperative mood ("add" not "added")
   - No period at end
   - Max 50 characters
5. Message body must:
   - Explain the reasoning and context
   - Focus on WHY, not what
   - Wrap at 72 characters
   - No bullet points

Please generate a high-quality commit message that follows these requirements exactly."""

        # Generate initial message
        result = await self.run(prompt)
        if not result:
            return None
            
        if hasattr(result, 'data'):
            result = result.data
        elif isinstance(result, dict):
            result = CommitMessageResult(**result)

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
            retry_result = await self.run(
                f"{prompt}\n\nPrevious attempt failed validation: {validation_msg}\n"
                f"Please make sure to follow all formatting rules exactly."
            )
            if retry_result and hasattr(retry_result, 'data'):
                result = retry_result.data

        return result