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
   - Explain the reasoning and context behind the changes
   - Focus on WHY the changes were made, not what was changed
   - Explain the purpose, motivation, or problem being solved
   - Wrap at 72 characters
   - No bullet points or lists
   - NEVER just list the files that were changed

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
                
                # Check if we got a valid response
                if not content or len(content.strip()) == 0:
                    # Generate a fallback commit message based on the changes
                    return self._generate_fallback_message(changes, context)
                
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
                    commit_type=type_part,
                    scope=scope_part,
                    description=description_part,
                    reasoning=body or self._generate_meaningful_reasoning(changes),
                    related_files=[change.path for change in changes]
                )
        except Exception as e:
            # Fallback to a simple commit message
            return CommitMessageResult(
                commit_type="feat",
                scope="general",
                description="update code",
                reasoning=self._generate_meaningful_reasoning(changes),
                related_files=[change.path for change in changes]
            )
    
    def _generate_meaningful_reasoning(self, changes: List[FileChange]) -> str:
        """Generate meaningful reasoning about why changes were made."""
        file_paths = [change.path for change in changes]
        
        # Analyze file patterns to understand the purpose
        patterns = {
            'frontend': ['src/', 'pages/', 'components/', '.astro', '.jsx', '.tsx', '.vue', '.css'],
            'backend': ['api/', 'server/', '.py', '.java', '.go', '.rb'],
            'database': ['.sql', 'migration', 'schema'],
            'testing': ['test', 'spec', '__tests__', '.test.', '.spec.'],
            'documentation': ['README', 'CHANGELOG', 'docs/', '.md'],
            'configuration': ['.config.', '.json', '.yaml', '.yml', '.toml', '.env'],
            'deployment': ['.github/', 'jenkins', 'travis', 'gitlab-ci', 'docker', 'kubernetes'],
            'styling': ['.css', '.scss', '.sass', '.less', 'styles/'],
            'routing': ['pages/', 'routes/', 'router/']
        }
        
        # Categorize files
        categories = {}
        for change in changes:
            path = change.path.lower()
            for category, pattern_list in patterns.items():
                if any(pattern in path for pattern in pattern_list):
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(change.path)
                    break
        
        # Generate reasoning based on categories
        if len(categories) == 1:
            category = list(categories.keys())[0]
            if category == 'frontend':
                return f"Update frontend components and styling to improve user experience and interface consistency."
            elif category == 'backend':
                return f"Enhance backend functionality and improve system performance and reliability."
            elif category == 'database':
                return f"Update database schema and queries to support new features and improve data integrity."
            elif category == 'testing':
                return f"Improve test coverage and ensure code quality through comprehensive testing."
            elif category == 'documentation':
                return f"Update documentation to reflect current system state and improve developer experience."
            elif category == 'configuration':
                return f"Update configuration settings to optimize system behavior and enable new features."
            elif category == 'deployment':
                return f"Update deployment configuration to improve CI/CD pipeline and deployment reliability."
            elif category == 'styling':
                return f"Improve visual design and user interface consistency across the application."
            elif category == 'routing':
                return f"Update application routing to support new pages and improve navigation structure."
        elif len(categories) > 1:
            # Multiple categories - focus on the most significant
            if 'frontend' in categories and 'styling' in categories:
                return f"Enhance frontend functionality and improve user interface design for better user experience."
            elif 'backend' in categories and 'database' in categories:
                return f"Improve backend functionality and update data layer to support enhanced features."
            elif 'testing' in categories:
                return f"Update implementation and corresponding tests to ensure code quality and reliability."
            else:
                return f"Implement cross-cutting improvements across multiple system components to enhance overall functionality."
        else:
            # No specific patterns detected
            return f"Update application code to improve functionality and maintain code quality."

    def _generate_fallback_message(self, changes: List[FileChange], context: str) -> CommitMessageResult:
        """Generate a fallback commit message when Ollama is not available."""
        # Analyze the changes to generate a meaningful message
        file_paths = [change.path for change in changes]
        
        # Determine commit type based on file patterns
        commit_type = "feat"
        scope = "general"
        description = "update code"
        
        # Look for patterns in file paths to determine the type of changes
        if any("test" in path.lower() for path in file_paths):
            commit_type = "test"
            scope = "testing"
            description = "add or update tests"
        elif any("doc" in path.lower() or "readme" in path.lower() for path in file_paths):
            commit_type = "docs"
            scope = "documentation"
            description = "update documentation"
        elif any("config" in path.lower() or "toml" in path.lower() for path in file_paths):
            commit_type = "chore"
            scope = "config"
            description = "update configuration"
        elif any("factory" in path.lower() or "strategy" in path.lower() for path in file_paths):
            commit_type = "feat"
            scope = "ai-integration"
            description = "add AI model integration"
        
        # Generate reasoning based on the changes
        reasoning = self._generate_meaningful_reasoning(changes)
        
        return CommitMessageResult(
            commit_type=commit_type,
            scope=scope,
            description=description,
            reasoning=reasoning,
            related_files=file_paths
        )

class ConventionalCommitStrategy(CommitMessageStrategy):
    """Strategy for generating conventional commit messages."""
    
    def __init__(self, model: str = 'anthropic:claude-3-5-sonnet-latest'):
        self.agent = Agent(
            model=model,
            output_type=CommitMessageResult,
            system_prompt=COMMIT_MESSAGE_PROMPT
        )
    
    def _generate_meaningful_reasoning(self, changes: List[FileChange]) -> str:
        """Generate meaningful reasoning about why changes were made."""
        file_paths = [change.path for change in changes]
        
        # Analyze file patterns to understand the purpose
        patterns = {
            'frontend': ['src/', 'pages/', 'components/', '.astro', '.jsx', '.tsx', '.vue', '.css'],
            'backend': ['api/', 'server/', '.py', '.java', '.go', '.rb'],
            'database': ['.sql', 'migration', 'schema'],
            'testing': ['test', 'spec', '__tests__', '.test.', '.spec.'],
            'documentation': ['README', 'CHANGELOG', 'docs/', '.md'],
            'configuration': ['.config.', '.json', '.yaml', '.yml', '.toml', '.env'],
            'deployment': ['.github/', 'jenkins', 'travis', 'gitlab-ci', 'docker', 'kubernetes'],
            'styling': ['.css', '.scss', '.sass', '.less', 'styles/'],
            'routing': ['pages/', 'routes/', 'router/']
        }
        
        # Categorize files
        categories = {}
        for change in changes:
            path = change.path.lower()
            for category, pattern_list in patterns.items():
                if any(pattern in path for pattern in pattern_list):
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(change.path)
                    break
        
        # Generate reasoning based on categories
        if len(categories) == 1:
            category = list(categories.keys())[0]
            if category == 'frontend':
                return f"Update frontend components and styling to improve user experience and interface consistency."
            elif category == 'backend':
                return f"Enhance backend functionality and improve system performance and reliability."
            elif category == 'database':
                return f"Update database schema and queries to support new features and improve data integrity."
            elif category == 'testing':
                return f"Improve test coverage and ensure code quality through comprehensive testing."
            elif category == 'documentation':
                return f"Update documentation to reflect current system state and improve developer experience."
            elif category == 'configuration':
                return f"Update configuration settings to optimize system behavior and enable new features."
            elif category == 'deployment':
                return f"Update deployment configuration to improve CI/CD pipeline and deployment reliability."
            elif category == 'styling':
                return f"Improve visual design and user interface consistency across the application."
            elif category == 'routing':
                return f"Update application routing to support new pages and improve navigation structure."
        elif len(categories) > 1:
            # Multiple categories - focus on the most significant
            if 'frontend' in categories and 'styling' in categories:
                return f"Enhance frontend functionality and improve user interface design for better user experience."
            elif 'backend' in categories and 'database' in categories:
                return f"Improve backend functionality and update data layer to support enhanced features."
            elif 'testing' in categories:
                return f"Update implementation and corresponding tests to ensure code quality and reliability."
            else:
                return f"Implement cross-cutting improvements across multiple system components to enhance overall functionality."
        else:
            # No specific patterns detected
            return f"Update application code to improve functionality and maintain code quality."
    
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
   - Explain the reasoning and context behind the changes
   - Focus on WHY the changes were made, not what was changed
   - Explain the purpose, motivation, or problem being solved
   - Wrap at 72 characters
   - No bullet points or lists
   - NEVER just list the files that were changed

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
    
    def _generate_meaningful_reasoning(self, changes: List[FileChange]) -> str:
        """Generate meaningful reasoning about why changes were made."""
        file_paths = [change.path for change in changes]
        
        # Analyze file patterns to understand the purpose
        patterns = {
            'frontend': ['src/', 'pages/', 'components/', '.astro', '.jsx', '.tsx', '.vue', '.css'],
            'backend': ['api/', 'server/', '.py', '.java', '.go', '.rb'],
            'database': ['.sql', 'migration', 'schema'],
            'testing': ['test', 'spec', '__tests__', '.test.', '.spec.'],
            'documentation': ['README', 'CHANGELOG', 'docs/', '.md'],
            'configuration': ['.config.', '.json', '.yaml', '.yml', '.toml', '.env'],
            'deployment': ['.github/', 'jenkins', 'travis', 'gitlab-ci', 'docker', 'kubernetes'],
            'styling': ['.css', '.scss', '.sass', '.less', 'styles/'],
            'routing': ['pages/', 'routes/', 'router/']
        }
        
        # Categorize files
        categories = {}
        for change in changes:
            path = change.path.lower()
            for category, pattern_list in patterns.items():
                if any(pattern in path for pattern in pattern_list):
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(change.path)
                    break
        
        # Generate reasoning based on categories
        if len(categories) == 1:
            category = list(categories.keys())[0]
            if category == 'frontend':
                return f"Update frontend components and styling to improve user experience and interface consistency."
            elif category == 'backend':
                return f"Enhance backend functionality and improve system performance and reliability."
            elif category == 'database':
                return f"Update database schema and queries to support new features and improve data integrity."
            elif category == 'testing':
                return f"Improve test coverage and ensure code quality through comprehensive testing."
            elif category == 'documentation':
                return f"Update documentation to reflect current system state and improve developer experience."
            elif category == 'configuration':
                return f"Update configuration settings to optimize system behavior and enable new features."
            elif category == 'deployment':
                return f"Update deployment configuration to improve CI/CD pipeline and deployment reliability."
            elif category == 'styling':
                return f"Improve visual design and user interface consistency across the application."
            elif category == 'routing':
                return f"Update application routing to support new pages and improve navigation structure."
        elif len(categories) > 1:
            # Multiple categories - focus on the most significant
            if 'frontend' in categories and 'styling' in categories:
                return f"Enhance frontend functionality and improve user interface design for better user experience."
            elif 'backend' in categories and 'database' in categories:
                return f"Improve backend functionality and update data layer to support enhanced features."
            elif 'testing' in categories:
                return f"Update implementation and corresponding tests to ensure code quality and reliability."
            else:
                return f"Implement cross-cutting improvements across multiple system components to enhance overall functionality."
        else:
            # No specific patterns detected
            return f"Update application code to improve functionality and maintain code quality."
    
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
2. Explain the purpose and reasoning behind the changes
3. Focus on WHY the changes were made, not what was changed
4. Use present tense
5. Keep subject line under 50 characters
6. Add a brief body explaining the context and motivation if needed
7. NEVER just list the files that were changed

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