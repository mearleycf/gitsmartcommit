"""Factory classes for creating agents and other components."""
from abc import ABC, abstractmethod
from pydantic_ai import Agent
import google.generativeai as genai
import httpx
import json
from typing import Optional, Dict, Any

from .models import RelationshipResult, CommitMessageResult, CommitUnit, CommitType
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
                
                # Create a proper RelationshipResult
                # Extract file paths from the prompt for grouping
                import re
                # Look for file paths in the prompt (they appear as "Changes in path/to/file:")
                file_paths = re.findall(r'Changes in ([^:]+):', prompt)
                
                if not file_paths:
                    # Fallback: create a simple group
                    file_paths = ["all_files"]
                
                class MockResult:
                    def __init__(self, content, file_paths):
                        self.content = content
                        self.data = RelationshipResult(
                            groups=[file_paths],  # Group all files together
                            reasoning=content,
                            commit_units=[]
                        )
                        self.output = self.data
                
                return MockResult(content, file_paths)
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
        # Explicit Ollama prefix always means Ollama
        if 'ollama' in self.model.lower() or self.model.startswith('ollama:'):
            return True
            
        # Check if there's an explicit provider prefix that's not Ollama
        if any(provider in self.model.lower() for provider in ['huggingface:', 'anthropic:', 'openai:', 'google:', 'gemini-']):
            return False
            
        # For Qwen models without explicit provider, check if we have a relevant API key
        # Only HF_TOKEN is relevant for Qwen models, other API keys should be ignored
        if self.api_key:
            # This is a bit of a hack, but we need to check if the API key looks like an HF token
            # HF tokens typically start with 'hf_' or are very long alphanumeric strings
            # For now, we'll assume if an API key is provided, it might be for HuggingFace
            # unless it's clearly not (like a Gemini key which starts with 'AIza')
            if self.api_key.startswith('AIza') or self.api_key.startswith('sk-'):
                # This looks like a Gemini or OpenAI key, not relevant for Qwen
                return True  # Use Ollama
            else:
                # This might be an HF token, use HuggingFace
                return False
        
        # No API key and no explicit provider prefix, use Ollama
        return True
        
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