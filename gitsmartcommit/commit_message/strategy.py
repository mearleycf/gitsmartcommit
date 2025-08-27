"""Commit message generation strategies."""
from abc import ABC, abstractmethod
from typing import List
from pydantic_ai import Agent
import httpx
import json

from ..models import FileChange, CommitMessageResult
from ..prompts import COMMIT_MESSAGE_PROMPT

class CommitMessageStrategy(ABC):
    """Abstract base class for commit message generation strategies."""
    
    @abstractmethod
    async def generate_message(self, changes: List[FileChange], context: str) -> CommitMessageResult:
        """Generate a commit message for the given changes and context."""
        pass

class OllamaCommitStrategy(CommitMessageStrategy):
    """Strategy for generating commit messages using Ollama."""
    
    def __init__(self, model_name: str = 'qwen2.5-coder:7b', base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        
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

        # Use Ollama API directly
        url = f"{self.base_url}/api/generate"
        
        messages = [
            {"role": "system", "content": COMMIT_MESSAGE_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=60.0)
                response.raise_for_status()
                result = response.json()
                content = result.get("message", {}).get("content", "")
                
                # Parse the response to extract commit message components
                lines = content.strip().split('\n')
                subject_line = lines[0] if lines else "feat: update code"
                
                # Extract type and scope from subject line
                if '(' in subject_line and ')' in subject_line:
                    type_part = subject_line.split('(')[0].strip()
                    scope_part = subject_line.split('(')[1].split(')')[0].strip()
                    description_part = subject_line.split('): ')[1] if '): ' in subject_line else subject_line
                else:
                    type_part = "feat"
                    scope_part = "general"
                    description_part = subject_line
                
                # Get body (everything after the first line)
                body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
                
                return CommitMessageResult(
                    type=type_part,
                    scope=scope_part,
                    description=description_part,
                    body=body
                )
        except Exception as e:
            # Fallback to a simple commit message
            return CommitMessageResult(
                type="feat",
                scope="general",
                description="update code",
                body=f"Changes made to {len(changes)} files"
            )

class ConventionalCommitStrategy(CommitMessageStrategy):
    """Strategy for generating conventional commit messages."""
    
    def __init__(self, model: str = 'anthropic:claude-3-5-sonnet-latest'):
        self.agent = Agent(
            model=model,
            output_type=CommitMessageResult,
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
            
        # Handle different result structures
        if hasattr(result, 'output'):
            result = result.output
        elif hasattr(result, 'data'):
            result = result.data
        elif isinstance(result, dict):
            result = CommitMessageResult(**result)
            
        return result

class SimpleCommitStrategy(CommitMessageStrategy):
    """Strategy for generating simple, non-conventional commit messages."""
    
    def __init__(self, model: str = 'anthropic:claude-3-5-sonnet-latest'):
        self.agent = Agent(
            model=model,
            output_type=CommitMessageResult,
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
            
        # Handle different result structures
        if hasattr(result, 'output'):
            result = result.output
        elif hasattr(result, 'data'):
            result = result.data
        elif isinstance(result, dict):
            result = CommitMessageResult(**result)
            
        return result 