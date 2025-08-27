"""Factory classes for creating agents and other components."""
from abc import ABC, abstractmethod
from pydantic_ai import Agent
import google.generativeai as genai
import httpx
import json
from typing import Optional, Dict, Any

from .models import RelationshipResult, CommitMessageResult
from .commit_message import CommitMessageGenerator, CommitMessageStrategy, ConventionalCommitStrategy, OllamaCommitStrategy
from .prompts import RELATIONSHIP_PROMPT, COMMIT_MESSAGE_PROMPT

class OllamaModel:
    """Custom model class for Ollama integration."""
    
    def __init__(self, model_name: str, base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response using Ollama API."""
        url = f"{self.base_url}/api/generate"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=60.0)
            response.raise_for_status()
            result = response.json()
            return result.get("message", {}).get("content", "")

class OllamaAgent:
    """Custom agent class for Ollama integration."""
    
    def __init__(self, model_name: str, output_type=None, system_prompt: str = None, base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.output_type = output_type
        self.system_prompt = system_prompt
        self.base_url = base_url
        
    async def run(self, prompt: str):
        """Run the agent with the given prompt."""
        url = f"{self.base_url}/api/generate"
        
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        
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
                
                # For now, return a simple mock result
                # In a full implementation, you'd parse the content into the expected output_type
                class MockResult:
                    def __init__(self, content):
                        self.content = content
                        self.data = self
                        self.output = self
                
                return MockResult(content)
        except Exception as e:
            raise Exception(f"Ollama API error: {str(e)}")

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
            # For Ollama models, use our custom Ollama integration
            # Remove the ollama: prefix if present
            model_name = self.model.replace('ollama:', '') if self.model.startswith('ollama:') else self.model
            
            # Use our custom OllamaAgent instead of pydantic-ai Agent
            return OllamaAgent(
                model_name=model_name,
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
            # For Ollama models, use our custom Ollama commit strategy
            model_name = self.model.replace('ollama:', '') if self.model.startswith('ollama:') else self.model
            return OllamaCommitStrategy(model_name=model_name)
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