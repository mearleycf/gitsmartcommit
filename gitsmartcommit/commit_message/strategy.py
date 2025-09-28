"""Commit message generation strategies."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

import httpx
from pydantic_ai import Agent

from ..models import CommitMessageResult, FileChange
from ..prompts import COMMIT_MESSAGE_PROMPT


class CommitMessageStrategy(ABC):
    """Abstract base class for commit message generation strategies."""

    @abstractmethod
    async def generate_message(
        self, changes: List[FileChange], context: str
    ) -> CommitMessageResult:
        """Generate a commit message for the given changes and context."""
        pass


class OllamaCommitStrategy(CommitMessageStrategy):
    """Strategy for generating commit messages using Ollama."""

    def __init__(
        self,
        model_name: str = "qwen2.5-coder:7b",
        base_url: str = "http://localhost:11434",
    ):
        self.model_name = model_name
        self.base_url = base_url

    async def generate_message(
        self, changes: List[FileChange], context: str
    ) -> CommitMessageResult:
        changes_desc = []
        for change in changes:
            # Truncate very large diffs to avoid prompt size issues
            diff = (
                change.content_diff[:1000] + "..."
                if len(change.content_diff) > 1000
                else change.content_diff
            )
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
   - Be specific and descriptive (avoid generic terms like "update code", "fix stuff", etc.)
   - Focus on the main purpose or feature being changed
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
            {"role": "user", "content": prompt},
        ]

        payload = {"model": self.model_name, "messages": messages, "stream": False}

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
                lines = content.strip().split("\n")
                subject_line = lines[0] if lines else ""

                # Extract type and scope from subject line
                if (
                    "(" in subject_line
                    and ")" in subject_line
                    and "): " in subject_line
                ):
                    type_part = subject_line.split("(")[0].strip()
                    scope_part = subject_line.split("(")[1].split(")")[0].strip()
                    description_part = (
                        subject_line.split("): ")[1]
                        if "): " in subject_line
                        else subject_line
                    )
                else:
                    # If parsing fails, analyze the changes to generate a better description
                    type_part, scope_part, description_part = (
                        self._analyze_changes_for_description(changes)
                    )

                # Get body (everything after the first line)
                body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

                # If no meaningful body was generated, create one
                if not body or len(body.strip()) < 20:
                    body = self._generate_meaningful_reasoning(changes)

                return CommitMessageResult(
                    commit_type=type_part,
                    scope=scope_part,
                    description=description_part,
                    reasoning=body,
                    related_files=[change.path for change in changes],
                )
        except Exception as e:
            # Fallback to a simple commit message with better analysis
            commit_type, scope, description = self._analyze_changes_for_description(
                changes
            )
            return CommitMessageResult(
                commit_type=commit_type,
                scope=scope,
                description=description,
                reasoning=self._generate_meaningful_reasoning(changes),
                related_files=[change.path for change in changes],
            )

    def _generate_fallback_message(
        self, changes: List[FileChange], context: str
    ) -> CommitMessageResult:
        """Generate a fallback commit message when Ollama is not available."""
        # Analyze the changes to generate a meaningful message
        file_paths = [change.path for change in changes]

        # Determine commit type and scope based on file patterns and content
        commit_type, scope, description = self._analyze_changes_for_description(changes)

        # Generate meaningful reasoning based on the changes
        if len(changes) == 1:
            change = changes[0]
            if change.status == "modified":
                reasoning = f"Updated {change.path} to improve functionality and maintain code quality."
            elif change.status == "added":
                reasoning = (
                    f"Added {change.path} to enhance the application with new features."
                )
            elif change.status == "deleted":
                reasoning = f"Removed {change.path} to clean up unused code and improve maintainability."
            else:
                reasoning = f"Modified {change.path} to address specific requirements and improve overall system performance."
        else:
            # Analyze file types to provide better context
            file_types = {}
            for change in changes:
                ext = Path(change.path).suffix.lower()
                if ext in [".py", ".js", ".ts", ".jsx", ".tsx"]:
                    file_types["code"] = file_types.get("code", 0) + 1
                elif ext in [".md", ".txt", ".rst"]:
                    file_types["docs"] = file_types.get("docs", 0) + 1
                elif ext in [".json", ".yaml", ".yml", ".toml"]:
                    file_types["config"] = file_types.get("config", 0) + 1
                elif ext in [".css", ".scss", ".sass"]:
                    file_types["styles"] = file_types.get("styles", 0) + 1
                else:
                    file_types["other"] = file_types.get("other", 0) + 1

            # Generate context-aware reasoning
            if "code" in file_types and file_types["code"] > 0:
                reasoning = f"Updated {len(changes)} files to enhance application functionality and improve code quality. Changes include code modifications, configuration updates, and documentation improvements to ensure better maintainability and user experience."
            elif "styles" in file_types and file_types["styles"] > 0:
                reasoning = f"Updated {len(changes)} files to improve styling and user interface components. These changes enhance the visual presentation and user experience across the application."
            elif "docs" in file_types and file_types["docs"] > 0:
                reasoning = f"Updated {len(changes)} files to improve documentation and project clarity. These changes help developers understand the codebase better and maintain consistent project standards."
            else:
                reasoning = f"Updated {len(changes)} files to improve overall project structure and functionality. These changes contribute to better code organization, enhanced features, and improved maintainability."

        return CommitMessageResult(
            commit_type=commit_type,
            scope=scope,
            description=description,
            reasoning=reasoning,
            related_files=file_paths,
        )

    def _analyze_changes_for_description(
        self, changes: List[FileChange]
    ) -> tuple[str, str, str]:
        """Analyze file changes to generate specific commit type, scope, and description."""
        file_paths = [change.path for change in changes]

        # Default values
        commit_type = "feat"
        scope = "general"
        description = "update code"

        # Analyze file content for more specific descriptions
        content_analysis = self._analyze_file_content(changes)

        # Use content analysis to generate more specific descriptions
        if content_analysis["patterns"]:
            if "testing" in content_analysis["patterns"]:
                commit_type = "test"
                scope = "testing"
                if content_analysis["functions"]:
                    func_names = list(content_analysis["functions"])[:2]
                    description = f"add tests for {', '.join(func_names)}"
                else:
                    description = "add or update tests"
            elif "configuration" in content_analysis["patterns"]:
                commit_type = "chore"
                scope = "config"
                description = "update configuration settings"
            elif "error_handling" in content_analysis["patterns"]:
                commit_type = "fix"
                scope = "error-handling"
                description = "improve error handling"
            elif "api" in content_analysis["patterns"]:
                commit_type = "feat"
                scope = "api"
                description = "enhance API functionality"
            elif "database" in content_analysis["patterns"]:
                commit_type = "feat"
                scope = "database"
                description = "update data models"
            elif "authentication" in content_analysis["patterns"]:
                commit_type = "feat"
                scope = "auth"
                description = "improve authentication"
            elif "ui" in content_analysis["patterns"]:
                commit_type = "feat"
                scope = "ui"
                description = "enhance user interface"

        # Analyze file paths for patterns
        path_lower = " ".join(file_paths).lower()

        # Test files
        if any("test" in path.lower() for path in file_paths):
            commit_type = "test"
            scope = "testing"
            description = "add or update tests"

        # Documentation
        elif any(
            "doc" in path.lower() or "readme" in path.lower() or path.endswith(".md")
            for path in file_paths
        ):
            commit_type = "docs"
            scope = "documentation"
            if any("readme" in path.lower() for path in file_paths):
                description = "update readme"
            elif any("changelog" in path.lower() for path in file_paths):
                description = "update changelog"
            else:
                description = "update documentation"

        # Configuration files
        elif any(
            "config" in path.lower()
            or path.endswith((".toml", ".json", ".yaml", ".yml"))
            for path in file_paths
        ):
            commit_type = "chore"
            scope = "config"
            if any("pyproject" in path.lower() for path in file_paths):
                description = "update project config"
            elif any("pytest" in path.lower() for path in file_paths):
                description = "update test config"
            else:
                description = "update configuration"

        # AI/ML related files
        elif any(
            "factory" in path.lower()
            or "strategy" in path.lower()
            or "prompt" in path.lower()
            for path in file_paths
        ):
            commit_type = "feat"
            scope = "ai-integration"
            description = "improve AI model integration"

        # Web/frontend files
        elif any(
            path.startswith("web/")
            or path.endswith((".astro", ".html", ".css", ".scss"))
            for path in file_paths
        ):
            commit_type = "feat"
            scope = "web"
            if any(path.endswith(".astro") for path in file_paths):
                description = "update web pages"
            elif any(path.endswith((".css", ".scss")) for path in file_paths):
                description = "update styles"
            else:
                description = "update web interface"

        # Backend/API files
        elif any(
            path.startswith("backend/") or "api" in path.lower() for path in file_paths
        ):
            commit_type = "feat"
            scope = "api"
            if any("service" in path.lower() for path in file_paths):
                description = "update services"
            elif any("api" in path.lower() for path in file_paths):
                description = "update API endpoints"
            else:
                description = "update backend logic"

        # Database related
        elif any(
            "db" in path.lower()
            or "database" in path.lower()
            or "model" in path.lower()
            for path in file_paths
        ):
            commit_type = "feat"
            scope = "database"
            description = "update data models"

        # CLI/commands
        elif any(
            "cli" in path.lower() or "command" in path.lower() for path in file_paths
        ):
            commit_type = "feat"
            scope = "cli"
            description = "update command interface"

        # Core functionality
        elif any(
            "core" in path.lower() or "base" in path.lower() for path in file_paths
        ):
            commit_type = "feat"
            scope = "core"
            description = "update core functionality"

        # Specific feature analysis based on file content
        else:
            # Try to extract more specific information from file paths
            for path in file_paths:
                path_parts = Path(path).parts

                # Look for feature-specific directories
                if len(path_parts) > 1:
                    if "income" in path_parts[1].lower():
                        commit_type = "feat"
                        scope = "income"
                        description = "update income features"
                        break
                    elif "import" in path_parts[1].lower():
                        commit_type = "feat"
                        scope = "import"
                        description = "update import functionality"
                        break
                    elif "transaction" in path_parts[1].lower():
                        commit_type = "feat"
                        scope = "transactions"
                        description = "update transaction handling"
                        break
                    elif "csv" in path_parts[1].lower():
                        commit_type = "feat"
                        scope = "csv"
                        description = "update CSV processing"
                        break

        return commit_type, scope, description

    def _analyze_file_content(self, changes: List[FileChange]) -> dict:
        """Analyze file content to extract more specific commit information."""
        analysis = {
            "keywords": set(),
            "functions": set(),
            "classes": set(),
            "imports": set(),
            "patterns": set(),
        }

        for change in changes:
            content = change.content_diff.lower()

            # Look for function definitions
            import re

            functions = re.findall(r"def\s+(\w+)", content)
            analysis["functions"].update(functions)

            # Look for class definitions
            classes = re.findall(r"class\s+(\w+)", content)
            analysis["classes"].update(classes)

            # Look for imports
            imports = re.findall(r"from\s+(\w+)|import\s+(\w+)", content)
            for imp in imports:
                analysis["imports"].update([i for i in imp if i])

            # Look for specific patterns
            if "test" in content or "assert" in content:
                analysis["patterns"].add("testing")
            if "config" in content or "setting" in content:
                analysis["patterns"].add("configuration")
            if "error" in content or "exception" in content:
                analysis["patterns"].add("error_handling")
            if "api" in content or "endpoint" in content:
                analysis["patterns"].add("api")
            if "database" in content or "model" in content:
                analysis["patterns"].add("database")
            if "auth" in content or "login" in content:
                analysis["patterns"].add("authentication")
            if "ui" in content or "component" in content:
                analysis["patterns"].add("ui")

        return analysis

    def _generate_meaningful_reasoning(self, changes: List[FileChange]) -> str:
        """Generate meaningful reasoning for commit messages."""
        if len(changes) == 1:
            change = changes[0]
            if change.status == "modified":
                return f"Updated {change.path} to improve functionality and maintain code quality."
            elif change.status == "added":
                return (
                    f"Added {change.path} to enhance the application with new features."
                )
            elif change.status == "deleted":
                return f"Removed {change.path} to clean up unused code and improve maintainability."
            else:
                return f"Modified {change.path} to address specific requirements and improve overall system performance."
        else:
            # Analyze file types to provide better context
            file_types = {}
            for change in changes:
                ext = Path(change.path).suffix.lower()
                if ext in [".py", ".js", ".ts", ".jsx", ".tsx"]:
                    file_types["code"] = file_types.get("code", 0) + 1
                elif ext in [".md", ".txt", ".rst"]:
                    file_types["docs"] = file_types.get("docs", 0) + 1
                elif ext in [".json", ".yaml", ".yml", ".toml"]:
                    file_types["config"] = file_types.get("config", 0) + 1
                elif ext in [".css", ".scss", ".sass"]:
                    file_types["styles"] = file_types.get("styles", 0) + 1
                else:
                    file_types["other"] = file_types.get("other", 0) + 1

            # Generate context-aware reasoning
            if "code" in file_types and file_types["code"] > 0:
                return f"Updated {len(changes)} files to enhance application functionality and improve code quality. Changes include code modifications, configuration updates, and documentation improvements to ensure better maintainability and user experience."
            elif "styles" in file_types and file_types["styles"] > 0:
                return f"Updated {len(changes)} files to improve styling and user interface components. These changes enhance the visual presentation and user experience across the application."
            elif "docs" in file_types and file_types["docs"] > 0:
                return f"Updated {len(changes)} files to improve documentation and project clarity. These changes help developers understand the codebase better and maintain consistent project standards."
            else:
                return f"Updated {len(changes)} files to improve overall project structure and functionality. These changes contribute to better code organization, enhanced features, and improved maintainability."


class ConventionalCommitStrategy(CommitMessageStrategy):
    """Strategy for generating conventional commit messages."""

    def __init__(self, model: str = "anthropic:claude-3-5-sonnet-latest"):
        self.agent = Agent(
            model=model,
            output_type=CommitMessageResult,
            system_prompt=COMMIT_MESSAGE_PROMPT,
        )

    async def generate_message(
        self, changes: List[FileChange], context: str
    ) -> CommitMessageResult:
        changes_desc = []
        for change in changes:
            # Truncate very large diffs to avoid prompt size issues
            diff = (
                change.content_diff[:1000] + "..."
                if len(change.content_diff) > 1000
                else change.content_diff
            )
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
   - Be specific and descriptive (avoid generic terms like "update code", "fix stuff", etc.)
   - Focus on the main purpose or feature being changed
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
        if hasattr(result, "output"):
            result = result.output
        elif hasattr(result, "data"):
            result = result.data
        elif isinstance(result, dict):
            result = CommitMessageResult(**result)

        return result


class SimpleCommitStrategy(CommitMessageStrategy):
    """Strategy for generating simple, non-conventional commit messages."""

    def __init__(self, model: str = "anthropic:claude-3-5-sonnet-latest"):
        self.agent = Agent(
            model=model,
            output_type=CommitMessageResult,
            system_prompt="""You are a Git commit message generator that creates simple, clear commit messages.
            Focus on clarity and brevity while still explaining the purpose of the changes.""",
        )

    async def generate_message(
        self, changes: List[FileChange], context: str
    ) -> CommitMessageResult:
        changes_desc = []
        for change in changes:
            diff = (
                change.content_diff[:1000] + "..."
                if len(change.content_diff) > 1000
                else change.content_diff
            )
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
5. Be specific and descriptive (avoid generic terms like "update code", "fix stuff", etc.)
6. Focus on the main purpose or feature being changed
7. Add a brief body explaining the context if needed

Please generate a clear commit message that follows these requirements."""

        result = await self.agent.run(prompt)
        if not result:
            return None

        # Handle different result structures
        if hasattr(result, "output"):
            result = result.output
        elif hasattr(result, "data"):
            result = result.data
        elif isinstance(result, dict):
            result = CommitMessageResult(**result)

        return result
