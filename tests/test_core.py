import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from git import Repo
from pydantic_ai import Agent, RunContext, Tool

from gitsmartcommit.commit_message import (
    CommitMessageGenerator,
    CommitMessageStrategy,
    ConventionalCommitStrategy,
    SimpleCommitStrategy,
)
from gitsmartcommit.core import (
    ChangeAnalyzer,
    CommitType,
    CommitUnit,
    FileChange,
    GitCommitter,
)
from gitsmartcommit.models import CommitMessageResult, RelationshipResult
from gitsmartcommit.observers import FileLogObserver, GitOperationObserver


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
        body="Test commit body",
        message="feat(test): test commit",
    )

    # Make a change
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Modified content")

    # Stage the change manually (since we're not using the analyzer)
    repo = Repo(temp_git_repo)
    repo.index.add(["test.txt"])

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
        groups=[["test.txt", "utils.py"], ["README.md"]], reasoning="Test grouping"
    )

    mock_commit = CommitMessageResult(
        commit_type=CommitType.FEAT,
        scope="test",
        description="test changes",
        reasoning="Test reasoning",
        related_files=["test.txt", "utils.py"],
    )

    # Create proper mock response structure
    mock_relationship_response = Mock()
    mock_relationship_response.data = mock_grouping

    # Mock the factory to return our mock agent
    with patch("gitsmartcommit.core.ClaudeAgentFactory") as mock_factory_class:
        mock_factory = Mock()
        mock_agent = Mock()
        mock_agent.run = AsyncMock(return_value=mock_relationship_response)
        mock_factory.create_relationship_agent.return_value = mock_agent

        # Mock the commit strategy as well
        mock_strategy = Mock()
        mock_strategy.generate_message = AsyncMock(return_value=mock_commit)
        mock_factory.create_commit_strategy.return_value = mock_strategy
        mock_factory_class.return_value = mock_factory

        # Create test files and changes (only one file to trigger single file path)
        test_file = Path(temp_git_repo) / "test.txt"
        test_file.write_text("Test content")

        analyzer = ChangeAnalyzer(temp_git_repo, factory=mock_factory)
        commit_units = await analyzer.analyze_changes()

        assert len(commit_units) > 0
        assert commit_units[0].type == CommitType.FEAT
        assert commit_units[0].scope == "test"
        assert commit_units[0].description == "test changes"


@pytest.mark.asyncio
async def test_generate_commit_message(temp_git_repo):
    # Create mock return values
    mock_grouping = RelationshipResult(groups=[["test.txt"]], reasoning="Test grouping")

    mock_commit = CommitMessageResult(
        commit_type=CommitType.FEAT,
        scope="test",
        description="test changes",
        reasoning="Test reasoning",
        related_files=["test.txt"],
    )

    # Mock the strategy
    mock_strategy = Mock(spec=CommitMessageStrategy)
    mock_strategy.generate_message = AsyncMock(return_value=mock_commit)

    # Mock relationship agent
    with patch.object(Agent, "run", new_callable=AsyncMock) as mock_relationship_run:
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


@pytest.mark.asyncio
async def test_git_committer_observers(temp_git_repo):
    # Create a mock observer
    mock_observer = Mock(spec=GitOperationObserver)
    mock_observer.on_commit_created = AsyncMock()
    mock_observer.on_push_completed = AsyncMock()

    # Create a test commit unit
    commit_unit = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="test commit",
        files=["test.txt"],
        body="Test commit body",
        message="feat(test): test commit",
    )

    # Make a change
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Modified content")

    # Stage the change manually (since we're not using the analyzer)
    repo = Repo(temp_git_repo)
    repo.index.add(["test.txt"])

    # Create committer and add observer
    committer = GitCommitter(temp_git_repo)
    committer.add_observer(mock_observer)

    # Test commit
    success = await committer.commit_changes([commit_unit])
    assert success is True
    mock_observer.on_commit_created.assert_called_once_with(commit_unit)

    # Test push (should fail since there's no remote)
    success = await committer.push_changes()
    assert success is False
    mock_observer.on_push_completed.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_file_log_observer(temp_git_repo, tmp_path):
    # Create a log file
    log_file = tmp_path / "git.log"
    observer = FileLogObserver(str(log_file))

    # Create a test commit unit
    commit_unit = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="test commit",
        files=["test.txt"],
        body="Test commit body",
        message="feat(test): test commit",
    )

    # Test logging commit
    await observer.on_commit_created(commit_unit)
    assert log_file.exists()
    content = log_file.read_text()
    assert "Created commit: feat(test): test commit" in content

    # Test logging push
    await observer.on_push_completed(True)
    content = log_file.read_text()
    assert "Successfully push changes to remote" in content

    # Test logging merge
    await observer.on_merge_completed(True, "feature", "main")
    content = log_file.read_text()
    assert "Successfully merge feature into main" in content


@pytest.mark.asyncio
async def test_simple_commit_strategy(temp_git_repo):
    # Create test changes
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Modified content")

    # Create a FileChange object
    change = FileChange(
        path="test.txt",
        status="modified",
        content_diff="Modified content",
        is_staged=False,
    )

    # Create the strategy with mock agent
    from gitsmartcommit.commit_message import SimpleCommitStrategy
    from gitsmartcommit.factories import MockAgentFactory
    from gitsmartcommit.models import CommitMessageResult, CommitType

    mock_result = CommitMessageResult(
        commit_type=CommitType.FEAT,
        scope="test",
        description="add test functionality",
        reasoning="This change adds test functionality to improve code coverage",
        related_files=["test.txt"],
    )

    # Mock the agent properly
    with patch("gitsmartcommit.commit_message.strategy.Agent") as mock_agent_class:
        mock_agent = Mock()
        mock_response = Mock()
        mock_response.output = mock_result  # Use output instead of data
        mock_agent.run = AsyncMock(return_value=mock_response)
        mock_agent_class.return_value = mock_agent

        strategy = SimpleCommitStrategy()

        # Generate a message
        result = await strategy.generate_message([change], "Current branch: main")

        # Verify the result
        assert result is not None
        assert isinstance(result, CommitMessageResult)
        assert result.commit_type in CommitType
        assert len(result.description) <= 50  # Subject line length requirement
        assert not result.description.endswith(".")  # No period at end
        assert result.reasoning  # Should have a body explaining why


@pytest.mark.asyncio
async def test_conventional_commit_strategy(temp_git_repo):
    # Create test changes
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Modified content")

    # Create a FileChange object
    change = FileChange(
        path="test.txt",
        status="modified",
        content_diff="Modified content",
        is_staged=False,
    )

    # Create the strategy with mock agent
    from gitsmartcommit.commit_message import ConventionalCommitStrategy
    from gitsmartcommit.factories import MockAgentFactory
    from gitsmartcommit.models import CommitMessageResult, CommitType

    mock_result = CommitMessageResult(
        commit_type=CommitType.FEAT,
        scope="test",
        description="add test functionality",
        reasoning="This change adds test functionality to improve code coverage",
        related_files=["test.txt"],
    )

    # Mock the agent properly
    with patch("gitsmartcommit.commit_message.strategy.Agent") as mock_agent_class:
        mock_agent = Mock()
        mock_response = Mock()
        mock_response.output = mock_result
        mock_agent.run = AsyncMock(return_value=mock_response)
        mock_agent_class.return_value = mock_agent

        strategy = ConventionalCommitStrategy()

        # Generate a message
        result = await strategy.generate_message([change], "Current branch: main")

        # Verify the result
        assert result is not None
        assert isinstance(result, CommitMessageResult)
        assert result.commit_type in CommitType
        assert result.scope is not None
        assert len(result.description) <= 50
        assert (
            ":" in f"{result.commit_type.value}({result.scope}): {result.description}"
        )
        assert not result.description.endswith(".")
        assert result.reasoning


@pytest.mark.asyncio
async def test_git_push_no_tracking(temp_git_repo):
    # Create a test commit unit
    commit_unit = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="test commit",
        files=["test.txt"],
        body="Test commit body",
        message="feat(test): test commit",
    )

    # Make a change
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Modified content")

    # Create committer and observer
    committer = GitCommitter(temp_git_repo)
    mock_observer = Mock(spec=GitOperationObserver)
    mock_observer.on_push_completed = AsyncMock()
    committer.add_observer(mock_observer)

    # Create a new branch
    repo = Repo(temp_git_repo)
    new_branch = repo.create_head("feature-branch")
    repo.head.reference = new_branch

    # Commit and try to push
    await committer.commit_changes([commit_unit])
    success = await committer.push_changes()

    # Should fail since there's no upstream
    assert success is False
    mock_observer.on_push_completed.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_git_push_no_remote(temp_git_repo):
    # Create a test commit unit
    commit_unit = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="test commit",
        files=["test.txt"],
        body="Test commit body",
        message="feat(test): test commit",
    )

    # Make a change
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Modified content")

    # Create committer and observer
    committer = GitCommitter(temp_git_repo)
    mock_observer = Mock(spec=GitOperationObserver)
    mock_observer.on_push_completed = AsyncMock()
    committer.add_observer(mock_observer)

    # Remove any remotes
    repo = Repo(temp_git_repo)
    for remote in repo.remotes:
        repo.delete_remote(remote)

    # Commit and try to push
    await committer.commit_changes([commit_unit])
    success = await committer.push_changes()

    # Should fail since there's no remote
    assert success is False
    mock_observer.on_push_completed.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_auto_staging_functionality(temp_git_repo):
    """Test that ChangeAnalyzer automatically stages changes when auto_stage=True."""
    # Create some unstaged changes
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Modified content")

    new_file = Path(temp_git_repo) / "new.txt"
    new_file.write_text("New file content")

    repo = Repo(temp_git_repo)

    # Verify files are not staged initially
    assert not repo.index.diff(repo.head.commit)
    assert "test.txt" in repo.untracked_files or "new.txt" in repo.untracked_files

    # Create analyzer with auto_stage=True (default)
    analyzer = ChangeAnalyzer(temp_git_repo, auto_stage=True)

    # Mock both the commit generator and relationship agent to avoid AI calls
    with patch.object(
        analyzer.commit_generator, "generate_commit_message", new_callable=AsyncMock
    ) as mock_generate, patch.object(
        analyzer.relationship_agent, "run", new_callable=AsyncMock
    ) as mock_relationship:

        mock_generate.return_value = CommitMessageResult(
            commit_type=CommitType.FEAT,
            scope="test",
            description="test changes",
            related_files=["test.txt", "new.txt"],
            reasoning="Test commit",
        )

        # Mock the relationship agent to return a single group
        mock_relationship.return_value = RelationshipResult(
            groups=[["test.txt", "new.txt"]], reasoning="Test files are related"
        )

        # Analyze changes - this should auto-stage
        commit_units = await analyzer.analyze_changes()

        # Verify that files are now staged
        staged_diff = repo.index.diff(repo.head.commit)
        staged_files = [diff.a_path for diff in staged_diff]
        assert "test.txt" in staged_files or "new.txt" in staged_files

        # Verify commit units were generated
        assert len(commit_units) == 1
        assert commit_units[0].description == "test changes"


@pytest.mark.asyncio
async def test_no_auto_staging_functionality(temp_git_repo):
    """Test that ChangeAnalyzer doesn't auto-stage when auto_stage=False."""
    # Create some unstaged changes
    test_file = Path(temp_git_repo) / "test.txt"
    test_file.write_text("Modified content")

    new_file = Path(temp_git_repo) / "new.txt"
    new_file.write_text("New file content")

    repo = Repo(temp_git_repo)

    # Verify files are not staged initially
    initial_staged = repo.index.diff(repo.head.commit)
    initial_untracked = repo.untracked_files.copy()

    # Create analyzer with auto_stage=False
    analyzer = ChangeAnalyzer(temp_git_repo, auto_stage=False)

    # Mock both the commit generator and relationship agent to avoid AI calls
    with patch.object(
        analyzer.commit_generator, "generate_commit_message", new_callable=AsyncMock
    ) as mock_generate, patch.object(
        analyzer.relationship_agent, "run", new_callable=AsyncMock
    ) as mock_relationship:

        mock_generate.return_value = CommitMessageResult(
            commit_type=CommitType.FEAT,
            scope="test",
            description="test changes",
            related_files=["test.txt", "new.txt"],
            reasoning="Test commit",
        )

        # Mock the relationship agent to return a single group
        mock_relationship.return_value = RelationshipResult(
            groups=[["test.txt", "new.txt"]], reasoning="Test files are related"
        )

        # Analyze changes - this should NOT auto-stage
        commit_units = await analyzer.analyze_changes()

        # Verify that files are still not staged (same as initial state)
        final_staged = repo.index.diff(repo.head.commit)
        final_untracked = repo.untracked_files

        assert len(final_staged) == len(initial_staged)
        assert final_untracked == initial_untracked

        # Verify commit units were still generated (from unstaged/untracked files)
        assert len(commit_units) == 1
        assert commit_units[0].description == "test changes"
