"""Integration tests for end-to-end workflows."""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from git import Repo
from click.testing import CliRunner

from gitsmartcommit.cli import main
from gitsmartcommit.core import ChangeAnalyzer, GitCommitter
from gitsmartcommit.models import CommitType, CommitUnit, FileChange
from gitsmartcommit.factories import MockAgentFactory

@pytest.fixture
def integration_repo():
    """Create a realistic repository for integration testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create a realistic project structure
        project_structure = {
            "src/": {
                "main.py": "def main():\n    print('Hello World')",
                "utils.py": "def helper():\n    return True",
                "__init__.py": ""
            },
            "tests/": {
                "test_main.py": "def test_main():\n    assert True",
                "test_utils.py": "def test_helper():\n    assert True",
                "__init__.py": ""
            },
            "docs/": {
                "README.md": "# Project\n\nThis is a test project.",
                "API.md": "# API Documentation"
            },
            "config/": {
                "settings.json": '{"debug": true, "port": 8000}',
                "logging.yaml": "level: INFO\nhandlers: [console]"
            }
        }
        
        def create_structure(base_path, structure):
            for name, content in structure.items():
                path = base_path / name
                if isinstance(content, dict):
                    path.mkdir(exist_ok=True)
                    create_structure(path, content)
                else:
                    path.write_text(content)
        
        create_structure(Path(tmp_dir), project_structure)
        
        # Add all files to git
        repo.index.add(["src/", "tests/", "docs/", "config/"])
        repo.index.commit("Initial project setup")
        
        yield tmp_dir

@pytest.mark.asyncio
async def test_full_workflow_feature_development(integration_repo):
    """Test complete workflow for feature development."""
    # Simulate feature development
    src_main = Path(integration_repo) / "src" / "main.py"
    src_main.write_text("""def main():
    print('Hello World')
    print('New feature added')

def new_feature():
    return 'Feature implemented'
""")
    
    # Add corresponding test
    test_main = Path(integration_repo) / "tests" / "test_main.py"
    test_main.write_text("""def test_main():
    assert True

def test_new_feature():
    from src.main import new_feature
    assert new_feature() == 'Feature implemented'
""")
    
    # Update documentation
    readme = Path(integration_repo) / "docs" / "README.md"
    readme.write_text("""# Project

This is a test project.

## Features

- New feature added
""")
    
    # Mock the AI agents
    mock_result = CommitUnit(
        type=CommitType.FEAT,
        scope="main",
        description="add new feature with tests and docs",
        files=["src/main.py", "tests/test_main.py", "docs/README.md"],
        body="Implements a new feature with comprehensive test coverage and documentation updates.",
        message="feat(main): add new feature with tests and docs"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class, \
         patch('gitsmartcommit.cli.run_async') as mock_run_async:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer.set_upstream = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Mock run_async to properly handle coroutines
        def mock_run_async_side_effect(coro):
            if 'analyze_changes' in str(coro):
                return [mock_result]  # Must return a list for analyze_changes
            elif 'commit_changes' in str(coro):
                return True
            elif 'push_changes' in str(coro):
                return True
            elif 'set_upstream' in str(coro):
                return True
            else:
                return True
        
        mock_run_async.side_effect = mock_run_async_side_effect
        
        # Run CLI
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo])
        
        assert result.exit_code == 0
        mock_analyzer_class.assert_called_once()
        mock_committer_class.assert_called_once()

@pytest.mark.asyncio
async def test_full_workflow_bug_fix(integration_repo):
    """Test complete workflow for bug fix."""
    # Simulate bug fix
    utils_file = Path(integration_repo) / "src" / "utils.py"
    utils_file.write_text("""def helper():
    # Fix: return proper boolean value
    return True

def buggy_function():
    # Fix: handle edge case
    try:
        return 1 / 0
    except ZeroDivisionError:
        return None
""")
    
    # Add test for the fix
    test_utils = Path(integration_repo) / "tests" / "test_utils.py"
    test_utils.write_text("""def test_helper():
    assert True

def test_buggy_function():
    from src.utils import buggy_function
    assert buggy_function() is None
""")
    
    # Mock the AI agents
    mock_result = CommitUnit(
        type=CommitType.FIX,
        scope="utils",
        description="fix division by zero in buggy_function",
        files=["src/utils.py", "tests/test_utils.py"],
        body="Fixes a critical bug where division by zero would crash the application. Added proper error handling and test coverage.",
        message="fix(utils): fix division by zero in buggy_function"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class, \
         patch('gitsmartcommit.cli.run_async') as mock_run_async:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Mock run_async to properly handle coroutines
        def mock_run_async_side_effect(coro):
            if 'analyze_changes' in str(coro):
                return [mock_result]  # Must return a list for analyze_changes
            elif 'commit_changes' in str(coro):
                return True
            elif 'push_changes' in str(coro):
                return True
            else:
                return True
        
        mock_run_async.side_effect = mock_run_async_side_effect
        
        # Run CLI
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo])
        
        assert result.exit_code == 0
        mock_analyzer.analyze_changes.assert_called_once()
        mock_committer.commit_changes.assert_called_once_with([mock_result])

@pytest.mark.asyncio
async def test_full_workflow_refactoring(integration_repo):
    """Test complete workflow for refactoring."""
    # Simulate refactoring
    main_file = Path(integration_repo) / "src" / "main.py"
    main_file.write_text("""def main():
    print('Hello World')

# Refactored: extracted to separate function
def display_message():
    print('Hello World')

def main():
    display_message()
""")
    
    # Mock the AI agents
    mock_result = CommitUnit(
        type=CommitType.REFACTOR,
        scope="main",
        description="extract display logic to separate function",
        files=["src/main.py"],
        body="Refactors the main function to extract display logic into a separate function for better code organization.",
        message="refactor(main): extract display logic to separate function"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class, \
         patch('gitsmartcommit.cli.run_async') as mock_run_async:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Mock run_async to properly handle coroutines
        def mock_run_async_side_effect(coro):
            if 'analyze_changes' in str(coro):
                return [mock_result]  # Must return a list for analyze_changes
            elif 'commit_changes' in str(coro):
                return True
            elif 'push_changes' in str(coro):
                return True
            else:
                return True
        
        mock_run_async.side_effect = mock_run_async_side_effect
        
        # Run CLI
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo])
        
        assert result.exit_code == 0
        mock_analyzer.analyze_changes.assert_called_once()
        mock_committer.commit_changes.assert_called_once_with([mock_result])

@pytest.mark.asyncio
async def test_multiple_commit_units(integration_repo):
    """Test workflow with multiple commit units."""
    # Create multiple changes
    files = ["src/main.py", "src/utils.py", "tests/test_main.py", "docs/README.md"]
    for file_path in files:
        full_path = Path(integration_repo) / file_path
        full_path.write_text(f"Updated content for {file_path}")
    
    # Mock multiple commit units
    mock_results = [
        CommitUnit(
            type=CommitType.FEAT,
            scope="main",
            description="add new feature",
            files=["src/main.py"],
            body="Adds a new feature to the main module.",
            message="feat(main): add new feature"
        ),
        CommitUnit(
            type=CommitType.FIX,
            scope="utils",
            description="fix bug in utils",
            files=["src/utils.py"],
            body="Fixes a bug in the utils module.",
            message="fix(utils): fix bug in utils"
        ),
        CommitUnit(
            type=CommitType.TEST,
            scope="main",
            description="add tests for main",
            files=["tests/test_main.py"],
            body="Adds comprehensive tests for the main module.",
            message="test(main): add tests for main"
        ),
        CommitUnit(
            type=CommitType.DOCS,
            scope="docs",
            description="update documentation",
            files=["docs/README.md"],
            body="Updates project documentation.",
            message="docs(docs): update documentation"
        )
    ]
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class, \
         patch('gitsmartcommit.cli.run_async') as mock_run_async:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=mock_results)
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Mock run_async to properly handle coroutines
        def mock_run_async_side_effect(coro):
            if 'analyze_changes' in str(coro):
                return mock_results  # Must return a list for analyze_changes
            elif 'commit_changes' in str(coro):
                return True
            elif 'push_changes' in str(coro):
                return True
            else:
                return True
        
        mock_run_async.side_effect = mock_run_async_side_effect
        
        # Run CLI
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo])
        
        assert result.exit_code == 0
        mock_analyzer.analyze_changes.assert_called_once()
        mock_committer.commit_changes.assert_called_once_with(mock_results)

@pytest.mark.asyncio
async def test_workflow_with_auto_push(integration_repo):
    """Test workflow with auto-push enabled."""
    # Create a change
    main_file = Path(integration_repo) / "src" / "main.py"
    main_file.write_text("def main():\n    print('Updated content')")
    
    # Mock the AI agents
    mock_result = CommitUnit(
        type=CommitType.FEAT,
        scope="main",
        description="update main function",
        files=["src/main.py"],
        body="Updates the main function with new functionality.",
        message="feat(main): update main function"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class, \
         patch('gitsmartcommit.cli.run_async') as mock_run_async:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer.set_upstream = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Mock run_async to properly handle coroutines
        def mock_run_async_side_effect(coro):
            if 'analyze_changes' in str(coro):
                return [mock_result]  # Must return a list for analyze_changes
            elif 'commit_changes' in str(coro):
                return True
            elif 'push_changes' in str(coro):
                return True
            elif 'set_upstream' in str(coro):
                return True
            else:
                return True
        
        mock_run_async.side_effect = mock_run_async_side_effect
        
        # Run CLI with auto-push
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo, '--auto-push'])
        
        assert result.exit_code == 0
        mock_committer.push_changes.assert_called_once()

@pytest.mark.asyncio
async def test_workflow_with_merge(integration_repo):
    """Test workflow with merge to main branch."""
    # Create a change
    main_file = Path(integration_repo) / "src" / "main.py"
    main_file.write_text("def main():\n    print('Updated content')")
    
    # Mock the AI agents
    mock_result = CommitUnit(
        type=CommitType.FEAT,
        scope="main",
        description="update main function",
        files=["src/main.py"],
        body="Updates the main function with new functionality.",
        message="feat(main): update main function"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class, \
         patch('gitsmartcommit.cli.run_async') as mock_run_async:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer.set_upstream = AsyncMock(return_value=True)
        mock_committer.merge_to_main = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Mock run_async to properly handle coroutines
        def mock_run_async_side_effect(coro):
            if 'analyze_changes' in str(coro):
                return [mock_result]  # Must return a list for analyze_changes
            elif 'commit_changes' in str(coro):
                return True
            elif 'push_changes' in str(coro):
                return True
            elif 'set_upstream' in str(coro):
                return True
            elif 'merge_to_main' in str(coro):
                return True
            else:
                return True
        
        mock_run_async.side_effect = mock_run_async_side_effect
        
        # Run CLI with merge
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo, '--auto-push', '--merge'])
        
        assert result.exit_code == 0
        mock_committer.merge_to_main.assert_called_once()

@pytest.mark.asyncio
async def test_workflow_with_logging(integration_repo):
    """Test workflow with logging enabled."""
    # Create a change
    main_file = Path(integration_repo) / "src" / "main.py"
    main_file.write_text("def main():\n    print('Updated content')")
    
    # Mock the AI agents
    mock_result = CommitUnit(
        type=CommitType.FEAT,
        scope="main",
        description="update main function",
        files=["src/main.py"],
        body="Updates the main function with new functionality.",
        message="feat(main): update main function"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class, \
         patch('gitsmartcommit.cli.run_async') as mock_run_async, \
         patch('gitsmartcommit.cli.FileLogObserver') as mock_file_log_observer:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer.set_upstream = AsyncMock(return_value=True)
        mock_committer.add_observer = Mock()
        mock_committer_class.return_value = mock_committer
        
        mock_file_log_observer.return_value = Mock()
        
        # Mock run_async to properly handle coroutines
        def mock_run_async_side_effect(coro):
            if 'analyze_changes' in str(coro):
                return [mock_result]  # Must return a list for analyze_changes
            elif 'commit_changes' in str(coro):
                return True
            elif 'push_changes' in str(coro):
                return True
            elif 'set_upstream' in str(coro):
                return True
            else:
                return True
        
        mock_run_async.side_effect = mock_run_async_side_effect
        
        # Run CLI with logging
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo, '--log-file', 'test.log'])
        
        assert result.exit_code == 0
        mock_committer.add_observer.assert_called()

@pytest.mark.asyncio
async def test_workflow_error_handling(integration_repo):
    """Test workflow error handling."""
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.run_async') as mock_run_async:
        
        # Set up mocks to raise an exception
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(side_effect=Exception("Test error"))
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_run_async.side_effect = Exception("Test error")
        
        # Run CLI
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo])
        
        # Should handle the error gracefully
        assert result.exit_code != 0

@pytest.mark.asyncio
async def test_workflow_dry_run(integration_repo):
    """Test workflow with dry run mode."""
    # Create a change
    main_file = Path(integration_repo) / "src" / "main.py"
    main_file.write_text("def main():\n    print('Updated content')")
    
    # Mock the AI agents
    mock_result = CommitUnit(
        type=CommitType.FEAT,
        scope="main",
        description="update main function",
        files=["src/main.py"],
        body="Updates the main function with new functionality.",
        message="feat(main): update main function"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class, \
         patch('gitsmartcommit.cli.run_async') as mock_run_async:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Mock run_async to properly handle coroutines
        def mock_run_async_side_effect(coro):
            if 'analyze_changes' in str(coro):
                return [mock_result]  # Must return a list for analyze_changes
            else:
                return True
        
        mock_run_async.side_effect = mock_run_async_side_effect
        
        # Run CLI with dry run
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo, '--dry-run'])
        
        assert result.exit_code == 0
        # In dry run mode, GitCommitter should not be called
        mock_committer_class.assert_not_called()
        # But the commit message should be displayed
        assert "feat(main): update main function" in result.output
