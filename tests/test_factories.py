"""Tests for factory classes."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pydantic_ai import Agent

from gitsmartcommit.factories import AgentFactory, ClaudeAgentFactory, GeminiAgentFactory, QwenAgentFactory, MockAgentFactory
from gitsmartcommit.models import RelationshipResult, CommitUnit, CommitType
from gitsmartcommit.commit_message import CommitMessageStrategy

def test_claude_agent_factory():
    """Test the Claude agent factory creates appropriate instances."""
    factory = ClaudeAgentFactory(model='claude-3-5-sonnet-latest')
    
    # Test relationship agent creation
    relationship_agent = factory.create_relationship_agent()
    assert isinstance(relationship_agent, Agent)
    assert relationship_agent.model.model_name == 'claude-3-5-sonnet-latest'
    
    # Test commit strategy creation
    commit_strategy = factory.create_commit_strategy()
    assert isinstance(commit_strategy, CommitMessageStrategy)

def test_gemini_agent_factory():
    """Test the Gemini agent factory creates appropriate instances."""
    with patch('google.generativeai.configure') as mock_configure:
        factory = GeminiAgentFactory(model='gemini-pro', api_key='test-key')
        mock_configure.assert_called_once_with(api_key='test-key')
        
        # Test relationship agent creation
        relationship_agent = factory.create_relationship_agent()
        assert isinstance(relationship_agent, Agent)
        assert relationship_agent.model.model_name == 'gemini-pro'
        
        # Test commit strategy creation
        commit_strategy = factory.create_commit_strategy()
        assert isinstance(commit_strategy, CommitMessageStrategy)

def test_gemini_agent_factory_no_api_key():
    """Test the Gemini agent factory without API key."""
    with patch('google.generativeai.configure') as mock_configure:
        factory = GeminiAgentFactory(model='gemini-pro')
        mock_configure.assert_not_called()
        
        # Test relationship agent creation
        relationship_agent = factory.create_relationship_agent()
        assert isinstance(relationship_agent, Agent)
        assert relationship_agent.model.model_name == 'gemini-pro'

def test_qwen_agent_factory():
    """Test the Qwen agent factory creates appropriate instances."""
    with patch('os.environ.get', return_value='test-key'), \
         patch('gitsmartcommit.factories.Agent') as mock_agent_class:
        
        mock_agent = Mock()
        mock_agent.model.model_name = 'Qwen/qwen2.5-coder-7b'
        mock_agent_class.return_value = mock_agent
        
        factory = QwenAgentFactory(model='qwen2.5-coder:7b', api_key='test-key')
        
        # Test relationship agent creation
        relationship_agent = factory.create_relationship_agent()
        assert isinstance(relationship_agent, Mock)
        assert relationship_agent.model.model_name == 'Qwen/qwen2.5-coder-7b'
        
        # Test commit strategy creation
        commit_strategy = factory.create_commit_strategy()
        assert isinstance(commit_strategy, CommitMessageStrategy)

def test_qwen_agent_factory_no_api_key():
    """Test the Qwen agent factory without API key."""
    with patch('os.environ.get', return_value=None):
        factory = QwenAgentFactory(model='qwen2.5-coder:7b')
        
        # Should fall back to Ollama agent when no API key
        relationship_agent = factory.create_relationship_agent()
        # The agent should be an OllamaAgent instance
        assert hasattr(relationship_agent, '_model_name')
        
        # Test commit strategy creation
        commit_strategy = factory.create_commit_strategy()
        assert isinstance(commit_strategy, CommitMessageStrategy)

def test_qwen_agent_factory_ollama():
    """Test the Qwen agent factory with Ollama model."""
    factory = QwenAgentFactory(model='ollama:qwen2.5-coder:7b')
    
    # Test that it's detected as an Ollama model
    assert factory._is_ollama_model() == True
    
    # Test relationship agent creation (should use OllamaAgent)
    relationship_agent = factory.create_relationship_agent()
    # Should be an OllamaAgent instance
    assert hasattr(relationship_agent, '_model_name')
    
    # Test commit strategy creation
    commit_strategy = factory.create_commit_strategy()
    assert isinstance(commit_strategy, CommitMessageStrategy)

def test_mock_agent_factory():
    """Test the mock agent factory with provided mocks."""
    mock_agent = Mock(spec=Agent)
    mock_strategy = Mock(spec=CommitMessageStrategy)
    
    factory = MockAgentFactory(
        mock_relationship_agent=mock_agent,
        mock_commit_strategy=mock_strategy
    )
    
    # Test relationship agent creation
    relationship_agent = factory.create_relationship_agent()
    assert relationship_agent == mock_agent
    
    # Test commit strategy creation
    commit_strategy = factory.create_commit_strategy()
    assert commit_strategy == mock_strategy

def test_mock_agent_factory_no_mocks():
    """Test the mock agent factory raises errors when no mocks provided."""
    factory = MockAgentFactory()
    
    with pytest.raises(ValueError, match="No mock relationship agent provided"):
        factory.create_relationship_agent()
    
    with pytest.raises(ValueError, match="No mock commit strategy provided"):
        factory.create_commit_strategy()

@pytest.mark.asyncio
async def test_factory_integration():
    """Test that factory-created agents work together correctly."""
    # Create mock components
    mock_agent = AsyncMock(spec=Agent)
    mock_strategy = AsyncMock(spec=CommitMessageStrategy)
    
    # Configure mock behavior
    mock_response = Mock()
    mock_response.data = RelationshipResult(
        groups=[["test.py"]],
        reasoning="Test grouping",
        commit_units=[CommitUnit(
            type=CommitType.FEAT,
            scope="test",
            description="test change",
            files=["test.py"],
            message="test: commit message",
            body=""
        )]
    )
    mock_agent.run.return_value = mock_response
    mock_strategy.generate_message.return_value = "test: commit message"
    
    # Create factory with mocks
    factory = MockAgentFactory(
        mock_relationship_agent=mock_agent,
        mock_commit_strategy=mock_strategy
    )
    
    # Verify components work together
    relationship_agent = factory.create_relationship_agent()
    commit_strategy = factory.create_commit_strategy()
    
    result = await relationship_agent.run(
        """Please analyze these files and group related changes based on logical units of work. 
A single logical unit means changes that work together to achieve one goal. 
For example: implementation files with their tests, or configuration files that support a feature.

Files to analyze:
test.py: test content"""
    )
    assert len(result.data.commit_units) == 1
    assert result.data.commit_units[0].description == "test change"
    assert result.data.commit_units[0].files == ["test.py"]
    
    message = await commit_strategy.generate_message("test description", ["test.py"])
    assert message == "test: commit message" 