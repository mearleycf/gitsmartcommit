"""Factory classes for creating agents and other components."""
from abc import ABC, abstractmethod
from pydantic_ai import Agent
import google.generativeai as genai

from .models import RelationshipResult, CommitMessageResult
from .commit_message import CommitMessageGenerator, CommitMessageStrategy, ConventionalCommitStrategy
from .prompts import RELATIONSHIP_PROMPT, COMMIT_MESSAGE_PROMPT

class AgentFactory(ABC):
    """Abstract factory for creating agents."""
    
    @abstractmethod
    def create_relationship_agent(self) -> Agent:
        """Create an agent for analyzing relationships between changes."""
        pass
    
    @abstractmethod
    def create_commit_strategy(self) -> CommitMessageStrategy:
        """Create a strategy for generating commit messages."""
        pass

class ClaudeAgentFactory(AgentFactory):
    """Factory for creating Claude-based agents."""
    
    def __init__(self, model: str = 'claude-3-5-sonnet-latest'):
        self.model = model
    
    def create_relationship_agent(self) -> Agent:
        """Create a Claude agent for analyzing relationships."""
        return Agent(
            model=f"anthropic:{self.model}" if not self.model.startswith("anthropic:") else self.model,
            output_type=RelationshipResult,
            system_prompt=RELATIONSHIP_PROMPT
        )
    
    def create_commit_strategy(self) -> CommitMessageStrategy:
        """Create a conventional commit strategy using Claude."""
        return ConventionalCommitStrategy(model=f"anthropic:{self.model}" if not self.model.startswith("anthropic:") else self.model)

class GeminiAgentFactory(AgentFactory):
    """Factory for creating Google Gemini-based agents."""
    
    def __init__(self, model: str = 'gemini-pro', api_key: str = None):
        self.model = model
        if api_key:
            genai.configure(api_key=api_key)
        
    def create_relationship_agent(self) -> Agent:
        """Create a Gemini agent for analyzing relationships."""
        return Agent(
            model=f"google-gla:{self.model}" if not self.model.startswith("google-gla:") else self.model,
            output_type=RelationshipResult,
            system_prompt=RELATIONSHIP_PROMPT
        )
    
    def create_commit_strategy(self) -> CommitMessageStrategy:
        """Create a conventional commit strategy using Gemini."""
        return ConventionalCommitStrategy(model=f"google-gla:{self.model}" if not self.model.startswith("google-gla:") else self.model)

class QwenAgentFactory(AgentFactory):
    """Factory for creating Qwen-based agents."""
    
    def __init__(self, model: str = 'qwen2.5-coder:7b', api_key: str = None):
        self.model = model
        self.api_key = api_key
        
    def _is_ollama_model(self) -> bool:
        """Check if this is an Ollama model."""
        return (
            'ollama' in self.model.lower() or 
            self.model.startswith('ollama:') or
            (not self.api_key and not any(provider in self.model.lower() for provider in ['huggingface:', 'anthropic:', 'openai:', 'google:', 'gemini-']))
        )
        
    def create_relationship_agent(self) -> Agent:
        """Create a Qwen agent for analyzing relationships."""
        if self._is_ollama_model():
            # For Ollama models, try using the model name directly
            # This might work if pydantic-ai can handle local models
            model_name = self.model.replace('ollama:', '') if self.model.startswith('ollama:') else self.model
            try:
                return Agent(
                    model=model_name,
                    output_type=RelationshipResult,
                    system_prompt=RELATIONSHIP_PROMPT
                )
            except Exception:
                # If direct model name doesn't work, fall back to HuggingFace
                # This allows users to still use Ollama models by providing an HF token
                # Remove the ollama: prefix before creating the HuggingFace model name
                clean_model_name = self.model.replace('ollama:', '') if self.model.startswith('ollama:') else self.model
                # Replace colons with hyphens for HuggingFace compatibility
                clean_model_name = clean_model_name.replace(':', '-')
                model_name = f"Qwen/{clean_model_name}" if not clean_model_name.startswith("Qwen/") else clean_model_name
                return Agent(
                    model=f"huggingface:{model_name}",
                    output_type=RelationshipResult,
                    system_prompt=RELATIONSHIP_PROMPT
                )
        else:
            # Use HuggingFace as the provider for Qwen models (requires API token)
            # Replace colons with hyphens for HuggingFace compatibility
            clean_model_name = self.model.replace(':', '-')
            model_name = f"Qwen/{clean_model_name}" if not clean_model_name.startswith("Qwen/") else clean_model_name
            return Agent(
                model=f"huggingface:{model_name}",
                output_type=RelationshipResult,
                system_prompt=RELATIONSHIP_PROMPT
            )
    
    def create_commit_strategy(self) -> CommitMessageStrategy:
        """Create a conventional commit strategy using Qwen."""
        if self._is_ollama_model():
            # For Ollama models, try using the model name directly
            model_name = self.model.replace('ollama:', '') if self.model.startswith('ollama:') else self.model
            try:
                return ConventionalCommitStrategy(model=model_name)
            except Exception:
                # If direct model name doesn't work, fall back to HuggingFace
                # Remove the ollama: prefix before creating the HuggingFace model name
                clean_model_name = self.model.replace('ollama:', '') if self.model.startswith('ollama:') else self.model
                # Replace colons with hyphens for HuggingFace compatibility
                clean_model_name = clean_model_name.replace(':', '-')
                model_name = f"Qwen/{clean_model_name}" if not clean_model_name.startswith("Qwen/") else clean_model_name
                return ConventionalCommitStrategy(model=f"huggingface:{model_name}")
        else:
            # Use HuggingFace as the provider for Qwen models (requires API token)
            # Replace colons with hyphens for HuggingFace compatibility
            clean_model_name = self.model.replace(':', '-')
            model_name = f"Qwen/{clean_model_name}" if not clean_model_name.startswith("Qwen/") else clean_model_name
            return ConventionalCommitStrategy(model=f"huggingface:{model_name}")

class MockAgentFactory(AgentFactory):
    """Factory for creating mock agents (used in testing)."""
    
    def __init__(self, mock_relationship_agent: Agent = None, mock_commit_strategy: CommitMessageStrategy = None):
        self.mock_relationship_agent = mock_relationship_agent
        self.mock_commit_strategy = mock_commit_strategy
    
    def create_relationship_agent(self) -> Agent:
        """Create a mock relationship agent."""
        if not self.mock_relationship_agent:
            raise ValueError("No mock relationship agent provided")
        return self.mock_relationship_agent
    
    def create_commit_strategy(self) -> CommitMessageStrategy:
        """Create a mock commit strategy."""
        if not self.mock_commit_strategy:
            raise ValueError("No mock commit strategy provided")
        return self.mock_commit_strategy 