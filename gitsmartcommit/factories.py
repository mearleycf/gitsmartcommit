"""Factory classes for creating agents and other components."""
from abc import ABC, abstractmethod
from pydantic_ai import Agent

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
            result_type=RelationshipResult,
            system_prompt=RELATIONSHIP_PROMPT
        )
    
    def create_commit_strategy(self) -> CommitMessageStrategy:
        """Create a conventional commit strategy using Claude."""
        return ConventionalCommitStrategy(model=f"anthropic:{self.model}" if not self.model.startswith("anthropic:") else self.model)

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