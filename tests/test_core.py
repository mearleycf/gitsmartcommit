import pytest
import asyncio
from pathlib import Path
import tempfile
import os
from git import Repo
from unittest.mock import Mock, patch, AsyncMock
from gitsmartcommit.core import (
    ChangeAnalyzer, GitCommitter, CommitUnit, CommitType, FileChange
)
from gitsmartcommit.models import RelationshipResult, CommitMessageResult
from gitsmartcommit.commit_message import CommitMessageGenerator
from pydantic_ai import RunContext, Agent, Tool
from gitsmartcommit.commit_message.strategy import CommitMessageStrategy

@pytest.fixture
def temp_git_repo():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Initialize git repo
        repo = Repo.init(tmp_dir)
        
        # Create a test file
        test_file = Path(tmp_dir) / "test.txt"
        test_file.write_text("Initial content")
        
        # Initial commit
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        
        yield tmp_dir

@pytest.mark.asyncio
async def test_change_analyzer_no_changes(temp_git_repo):
    # Make sure the repo is clean
    repo = Repo(temp_git_repo)
    repo.index.commit("Clean state commit")
    
    # Verify that ChangeAnalyzer raises an error for a clean repo
    with pytest.raises(ValueError, match="No changes detected in repository"):
        analyzer = ChangeAnalyzer(temp_git_repo)
        await analyzer.analyze_changes()

@pytest.mark.asyncio
async def test_change_analyzer_with_changes(temp_git_repo):
    # Make some changes
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Modified content")
    
    analyzer = ChangeAnalyzer(temp_git_repo)
    assert analyzer._validate_repo() is True

@pytest.mark.asyncio
async def test_change_analyzer_collect_changes(temp_git_repo):
    # Create multiple types of changes
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Modified content")
    
    new_file = Path(temp_git_repo) / "new.txt"
    new_file.write_text("New file content")
    
    analyzer = ChangeAnalyzer(temp_git_repo)
    changes = analyzer._collect_changes()
    
    assert len(changes) == 2
    assert any(change.path == "test.txt" for change in changes)
    assert any(change.path == "new.txt" for change in changes)

@pytest.mark.asyncio
async def test_git_committer(temp_git_repo):
    # Create a test commit unit
    commit_unit = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="test commit",
        files=["test.txt"],
        body="Test commit body"
    )
    
    # Make a change
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Modified content")
    
    # Commit the change
    committer = GitCommitter(temp_git_repo)
    success = await committer.commit_changes([commit_unit])
    
    assert success is True
    
    # Verify commit
    repo = Repo(temp_git_repo)
    latest_commit = repo.head.commit
    assert latest_commit.message.startswith("feat(test): test commit")

@pytest.mark.asyncio
async def test_analyze_relationships(temp_git_repo):
    # Create mock return values
    mock_grouping = RelationshipResult(
        groups=[["test.txt", "utils.py"], ["README.md"]],
        reasoning="Test grouping"
    )

    mock_commit = CommitMessageResult(
        commit_type=CommitType.FEAT,
        scope="test",
        description="test changes",
        reasoning="Test reasoning",
        related_files=["test.txt", "utils.py"]
    )

    # Mock both agent run methods
    with patch.object(Agent, 'run', new_callable=AsyncMock) as mock_relationship_run, \
         patch.object(CommitMessageGenerator, 'generate_commit_message', new_callable=AsyncMock) as mock_commit_run:
        
        # Set up relationship mock
        mock_relationship_response = Mock()
        mock_relationship_response.data = mock_grouping
        mock_relationship_run.return_value = mock_relationship_response

        # Set up commit message mock
        mock_commit_run.return_value = mock_commit

        # Create test files and changes
        test_file = Path(temp_git_repo) / "test.txt"
        test_file.write_text("Test content")
        utils_file = Path(temp_git_repo) / "utils.py"
        utils_file.write_text("Utils content")

        analyzer = ChangeAnalyzer(temp_git_repo)
        commit_units = await analyzer.analyze_changes()

        assert len(commit_units) > 0
        assert commit_units[0].type == CommitType.FEAT
        assert commit_units[0].scope == "test"
        assert commit_units[0].description == "test changes"

@pytest.mark.asyncio
async def test_generate_commit_message(temp_git_repo):
    # Create mock return values
    mock_grouping = RelationshipResult(
        groups=[["test.txt"]],
        reasoning="Test grouping"
    )

    mock_commit = CommitMessageResult(
        commit_type=CommitType.FEAT,
        scope="test",
        description="test changes",
        reasoning="Test reasoning",
        related_files=["test.txt"]
    )

    # Mock the strategy
    mock_strategy = Mock(spec=CommitMessageStrategy)
    mock_strategy.generate_message = AsyncMock(return_value=mock_commit)

    # Mock relationship agent
    with patch.object(Agent, 'run', new_callable=AsyncMock) as mock_relationship_run:
        # Set up relationship mock
        mock_relationship_response = Mock()
        mock_relationship_response.data = mock_grouping
        mock_relationship_run.return_value = mock_relationship_response

        # Create a test change
        test_file = Path(temp_git_repo) / "test.txt"
        test_file.write_text("Test content")

        analyzer = ChangeAnalyzer(temp_git_repo, commit_strategy=mock_strategy)
        changes = analyzer._collect_changes()
        assert len(changes) > 0

        commit_units = await analyzer.analyze_changes()
        assert len(commit_units) > 0
        assert commit_units[0].type == CommitType.FEAT
        assert commit_units[0].scope == "test"
        assert commit_units[0].description == "test changes"
        assert commit_units[0].body == "Test reasoning"

        # Verify the strategy was called correctly
        mock_strategy.generate_message.assert_called_once()