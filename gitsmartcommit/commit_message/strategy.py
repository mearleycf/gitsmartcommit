"""Commit message generation strategies."""
from abc import ABC, abstractmethod
from typing import List
from pydantic_ai import Agent

from ..models import FileChange, CommitMessageResult
from ..prompts import COMMIT_MESSAGE_PROMPT

class CommitMessageStrategy(ABC):
    """Abstract base class for commit message generation strategies."""
    
    @abstractmethod
    async def generate_message(self, changes: List[FileChange], context: str) -> CommitMessageResult:
        """Generate a commit message for the given changes and context."""
        pass

class ConventionalCommitStrategy(CommitMessageStrategy):
    """Strategy for generating conventional commit messages."""
    
    def __init__(self, model: str = 'anthropic:claude-3-5-sonnet-latest'):
        self.agent = Agent(
            model=model,
            result_type=CommitMessageResult,
            system_prompt=COMMIT_MESSAGE_PROMPT
        )
    
    async def generate_message(self, changes: List[FileChange], context: str) -> CommitMessageResult:
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

        result = await self.agent.run(prompt)
        if not result:
            return None
            
        if hasattr(result, 'data'):
            result = result.data
        elif isinstance(result, dict):
            result = CommitMessageResult(**result)
            
        return result

class SimpleCommitStrategy(CommitMessageStrategy):
    """Strategy for generating simple, non-conventional commit messages."""
    
    def __init__(self, model: str = 'anthropic:claude-3-5-sonnet-latest'):
        self.agent = Agent(
            model=model,
            result_type=CommitMessageResult,
            system_prompt="""You are a Git commit message generator that creates simple, clear commit messages.
            Focus on clarity and brevity while still explaining the purpose of the changes."""
        )
    
    async def generate_message(self, changes: List[FileChange], context: str) -> CommitMessageResult:
        changes_desc = []
        for change in changes:
            diff = change.content_diff[:1000] + "..." if len(change.content_diff) > 1000 else change.content_diff
            changes_desc.append(f"{change.path} ({change.status}):\n{diff}")
            
        prompt = f"""Please analyze these changes and generate a simple commit message:

Changes to analyze:
{chr(10).join(changes_desc)}

Context:
{context}

Requirements:
1. Keep the message clear and concise
2. Explain the purpose of the changes
3. Use present tense
4. Keep subject line under 50 characters
5. Add a brief body explaining the context if needed

Please generate a clear commit message that follows these requirements."""

        result = await self.agent.run(prompt)
        if not result:
            return None
            
        if hasattr(result, 'data'):
            result = result.data
        elif isinstance(result, dict):
            result = CommitMessageResult(**result)
            
        return result 