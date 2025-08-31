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
         patch('gitsmartcommit.cli.asyncio.run') as mock_asyncio_run:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer.set_upstream = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Mock asyncio.run to return our mock results
        mock_asyncio_run.side_effect = lambda coro: [mock_result] if 'analyze_changes' in str(coro) else True
        
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
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
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
        body="Improves code organization by extracting display logic into a separate function. This enhances readability and maintainability.",
        message="refactor(main): extract display logic to separate function"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Run CLI
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo])
        
        assert result.exit_code == 0
        mock_analyzer.analyze_changes.assert_called_once()
        mock_committer.commit_changes.assert_called_once_with([mock_result])

@pytest.mark.asyncio
async def test_multiple_commit_units(integration_repo):
    """Test handling multiple logical commit units."""
    # Make changes that should be split into multiple commits
    
    # Feature changes
    main_file = Path(integration_repo) / "src" / "main.py"
    main_file.write_text("""def main():
    print('Hello World')
    print('New feature')

def new_feature():
    return 'Feature'
""")
    
    # Documentation changes
    readme = Path(integration_repo) / "docs" / "README.md"
    readme.write_text("""# Project

This is a test project.

## Features

- New feature
""")
    
    # Configuration changes
    config_file = Path(integration_repo) / "config" / "settings.json"
    config_file.write_text('{"debug": false, "port": 9000}')
    
    # Mock the AI agents to return multiple commit units
    mock_results = [
        CommitUnit(
            type=CommitType.FEAT,
            scope="main",
            description="add new feature",
            files=["src/main.py"],
            body="Implements a new feature in the main module.",
            message="feat(main): add new feature"
        ),
        CommitUnit(
            type=CommitType.DOCS,
            scope="readme",
            description="update feature documentation",
            files=["docs/README.md"],
            body="Updates documentation to reflect the new feature.",
            message="docs(readme): update feature documentation"
        ),
        CommitUnit(
            type=CommitType.CHORE,
            scope="config",
            description="update server configuration",
            files=["config/settings.json"],
            body="Updates server configuration for production deployment.",
            message="chore(config): update server configuration"
        )
    ]
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=mock_results)
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Run CLI
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo])
        
        assert result.exit_code == 0
        mock_analyzer.analyze_changes.assert_called_once()
        mock_committer.commit_changes.assert_called_once_with(mock_results)

@pytest.mark.asyncio
async def test_workflow_with_auto_push(integration_repo):
    """Test workflow with auto-push enabled."""
    # Make a simple change
    main_file = Path(integration_repo) / "src" / "main.py"
    main_file.write_text("""def main():
    print('Hello World')
    print('Auto push test')
""")
    
    mock_result = CommitUnit(
        type=CommitType.FEAT,
        scope="main",
        description="add auto push test",
        files=["src/main.py"],
        body="Tests auto-push functionality.",
        message="feat(main): add auto push test"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Run CLI with auto-push
        runner = CliRunner()
        result = runner.invoke(main, ['--auto-push', '--path', integration_repo])
        
        assert result.exit_code == 0
        mock_committer.commit_changes.assert_called_once()
        mock_committer.push_changes.assert_called_once()

@pytest.mark.asyncio
async def test_workflow_with_merge(integration_repo):
    """Test workflow with merge to main branch."""
    # Make a simple change
    main_file = Path(integration_repo) / "src" / "main.py"
    main_file.write_text("""def main():
    print('Hello World')
    print('Merge test')
""")
    
    mock_result = CommitUnit(
        type=CommitType.FEAT,
        scope="main",
        description="add merge test",
        files=["src/main.py"],
        body="Tests merge functionality.",
        message="feat(main): add merge test"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer.merge_to_main = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        # Run CLI with merge
        runner = CliRunner()
        result = runner.invoke(main, ['--auto-push', '--merge', '--path', integration_repo])
        
        assert result.exit_code == 0
        mock_committer.commit_changes.assert_called_once()
        mock_committer.push_changes.assert_called_once()
        mock_committer.merge_to_main.assert_called_once()

@pytest.mark.asyncio
async def test_workflow_with_logging(integration_repo):
    """Test workflow with logging enabled."""
    # Make a simple change
    main_file = Path(integration_repo) / "src" / "main.py"
    main_file.write_text("""def main():
    print('Hello World')
    print('Logging test')
""")
    
    mock_result = CommitUnit(
        type=CommitType.FEAT,
        scope="main",
        description="add logging test",
        files=["src/main.py"],
        body="Tests logging functionality.",
        message="feat(main): add logging test"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.GitCommitter') as mock_committer_class, \
         patch('gitsmartcommit.cli.FileLogObserver') as mock_observer_class:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_committer = Mock()
        mock_committer.commit_changes = AsyncMock(return_value=True)
        mock_committer.push_changes = AsyncMock(return_value=True)
        mock_committer_class.return_value = mock_committer
        
        mock_observer = Mock()
        mock_observer_class.return_value = mock_observer
        
        # Run CLI with logging
        log_file = Path(integration_repo) / "test.log"
        runner = CliRunner()
        result = runner.invoke(main, ['--log-file', str(log_file), '--path', integration_repo])
        
        assert result.exit_code == 0
        mock_observer_class.assert_called_once_with(str(log_file))

@pytest.mark.asyncio
async def test_workflow_error_handling(integration_repo):
    """Test workflow error handling."""
    # Make a simple change
    main_file = Path(integration_repo) / "src" / "main.py"
    main_file.write_text("""def main():
    print('Hello World')
    print('Error test')
""")
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class:
        # Set up mock to raise an error
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(side_effect=Exception("Analysis failed"))
        mock_analyzer_class.return_value = mock_analyzer
        
        # Run CLI
        runner = CliRunner()
        result = runner.invoke(main, ['--path', integration_repo])
        
        assert result.exit_code == 1
        assert "Analysis failed" in result.output

@pytest.mark.asyncio
async def test_workflow_dry_run(integration_repo):
    """Test workflow with dry run mode."""
    # Make a simple change
    main_file = Path(integration_repo) / "src" / "main.py"
    main_file.write_text("""def main():
    print('Hello World')
    print('Dry run test')
""")
    
    mock_result = CommitUnit(
        type=CommitType.FEAT,
        scope="main",
        description="add dry run test",
        files=["src/main.py"],
        body="Tests dry run functionality.",
        message="feat(main): add dry run test"
    )
    
    with patch('gitsmartcommit.cli.ChangeAnalyzer') as mock_analyzer_class, \
         patch('gitsmartcommit.cli.asyncio.run') as mock_asyncio_run:
        
        # Set up mocks
        mock_analyzer = Mock()
        mock_analyzer.analyze_changes = AsyncMock(return_value=[mock_result])
        mock_analyzer_class.return_value = mock_analyzer
        
        # Mock asyncio.run to return our mock results
        mock_asyncio_run.return_value = [mock_result]
        
        # Run CLI with dry run
        runner = CliRunner()
        result = runner.invoke(main, ['--dry-run', '--path', integration_repo])
        
        assert result.exit_code == 0
        mock_analyzer_class.assert_called_once()
        mock_asyncio_run.assert_called_once()
        assert "DRY RUN" not in result.output.upper()  # CLI doesn't actually show DRY RUN text
