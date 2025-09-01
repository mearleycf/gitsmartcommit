"""Tests for commit batching and logical grouping functionality."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from git import Repo
from gitsmartcommit.core import ChangeAnalyzer
from gitsmartcommit.models import FileChange, RelationshipResult, CommitUnit, CommitType, CommitMessageResult

@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        yield tmp_dir

@pytest.fixture
def mock_changes():
    """Create mock file changes that represent the scenario from the user's example."""
    return [
        FileChange(
            path="README.md",
            status="modified",
            content_diff="Updated main README",
            is_staged=True
        ),
        FileChange(
            path="ai_instructions.md",
            status="modified",
            content_diff="Updated AI instructions",
            is_staged=True
        ),
        FileChange(
            path="web/README.md",
            status="modified",
            content_diff="Updated web README",
            is_staged=True
        ),
        FileChange(
            path=".kiro/specs/budget-management/design.md",
            status="modified",
            content_diff="Updated budget design",
            is_staged=True
        ),
        FileChange(
            path=".kiro/specs/budget-management/requirements.md",
            status="modified",
            content_diff="Updated budget requirements",
            is_staged=True
        ),
        FileChange(
            path=".kiro/specs/business-expense-tracking/design.md",
            status="modified",
            content_diff="Updated expense tracking design",
            is_staged=True
        ),
        FileChange(
            path=".kiro/specs/business-expense-tracking/requirements.md",
            status="modified",
            content_diff="Updated expense tracking requirements",
            is_staged=True
        ),
    ]

def test_fallback_grouping_basic(temp_git_repo, mock_changes):
    """Test that fallback grouping correctly separates files into logical units."""
    analyzer = ChangeAnalyzer(temp_git_repo)
    
    # Test the fallback grouping method directly
    result = analyzer._fallback_grouping(mock_changes)
    
    # Should create multiple groups
    assert len(result.groups) > 1
    
    # Check that main docs are grouped together
    main_docs_group = None
    for group in result.groups:
        if "README.md" in group and "ai_instructions.md" in group:
            main_docs_group = group
            break
    
    assert main_docs_group is not None
    assert "web/README.md" not in main_docs_group  # Web docs should be separate
    
    # Check that feature specs are grouped by feature
    budget_group = None
    expense_group = None
    for group in result.groups:
        if ".kiro/specs/budget-management/design.md" in group:
            budget_group = group
        if ".kiro/specs/business-expense-tracking/design.md" in group:
            expense_group = group
    
    assert budget_group is not None
    assert expense_group is not None
    assert budget_group != expense_group  # Different features should be separate groups

def test_granular_fallback_grouping(temp_git_repo):
    """Test granular fallback grouping for complex directory structures."""
    analyzer = ChangeAnalyzer(temp_git_repo)
    
    changes = [
        FileChange(path="src/auth/login.py", status="modified", content_diff="", is_staged=True),
        FileChange(path="src/auth/logout.py", status="modified", content_diff="", is_staged=True),
        FileChange(path="src/user/profile.py", status="modified", content_diff="", is_staged=True),
        FileChange(path="tests/auth/test_login.py", status="modified", content_diff="", is_staged=True),
        FileChange(path="tests/user/test_profile.py", status="modified", content_diff="", is_staged=True),
    ]
    
    result = analyzer._granular_fallback_grouping(changes)
    
    # Should group by directory structure
    assert len(result) >= 3  # src/auth, src/user, tests/auth, tests/user
    
    # Check that auth files are grouped together
    auth_group = None
    for group in result:
        if "src/auth/login.py" in group:
            auth_group = group
            break
    
    assert auth_group is not None
    assert "src/auth/logout.py" in auth_group
    assert "src/user/profile.py" not in auth_group  # Different module

def test_fallback_grouping_patterns(temp_git_repo):
    """Test various file patterns are correctly grouped."""
    analyzer = ChangeAnalyzer(temp_git_repo)
    
    changes = [
        # Main docs
        FileChange(path="README.md", status="modified", content_diff="", is_staged=True),
        FileChange(path="CHANGELOG.md", status="modified", content_diff="", is_staged=True),
        
        # Web docs
        FileChange(path="web/README.md", status="modified", content_diff="", is_staged=True),
        FileChange(path="web/API.md", status="modified", content_diff="", is_staged=True),
        
        # Feature specs
        FileChange(path=".kiro/specs/auth/design.md", status="modified", content_diff="", is_staged=True),
        FileChange(path=".kiro/specs/auth/requirements.md", status="modified", content_diff="", is_staged=True),
        FileChange(path=".kiro/specs/payments/design.md", status="modified", content_diff="", is_staged=True),
        FileChange(path=".kiro/specs/payments/requirements.md", status="modified", content_diff="", is_staged=True),
        
        # Other files
        FileChange(path="src/utils.py", status="modified", content_diff="", is_staged=True),
    ]
    
    result = analyzer._fallback_grouping(changes)
    
    # Should have 5 groups: main_docs, web_docs, auth_specs, payments_specs, other
    assert len(result.groups) == 5
    
    # Check main docs group
    main_docs = None
    for group in result.groups:
        if "README.md" in group and "CHANGELOG.md" in group:
            main_docs = group
            break
    assert main_docs is not None
    assert len(main_docs) == 2
    
    # Check web docs group
    web_docs = None
    for group in result.groups:
        if "web/README.md" in group and "web/API.md" in group:
            web_docs = group
            break
    assert web_docs is not None
    assert len(web_docs) == 2
    
    # Check feature spec groups are separate
    auth_specs = None
    payments_specs = None
    for group in result.groups:
        if ".kiro/specs/auth/design.md" in group:
            auth_specs = group
        if ".kiro/specs/payments/design.md" in group:
            payments_specs = group
    
    assert auth_specs is not None
    assert payments_specs is not None
    assert auth_specs != payments_specs
    assert len(auth_specs) == 2
    assert len(payments_specs) == 2

def test_fallback_grouping_edge_cases(temp_git_repo):
    """Test fallback grouping with edge cases."""
    analyzer = ChangeAnalyzer(temp_git_repo)
    
    # Test with no changes
    result = analyzer._fallback_grouping([])
    assert len(result.groups) == 0
    
    # Test with single file
    changes = [FileChange(path="README.md", status="modified", content_diff="", is_staged=True)]
    result = analyzer._fallback_grouping(changes)
    assert len(result.groups) == 1
    assert len(result.groups[0]) == 1
    
    # Test with files that don't match any patterns
    changes = [
        FileChange(path="unknown/file.txt", status="modified", content_diff="", is_staged=True),
        FileChange(path="another/unknown.py", status="modified", content_diff="", is_staged=True),
    ]
    result = analyzer._fallback_grouping(changes)
    assert len(result.groups) == 1  # Should group unknown files together
    assert len(result.groups[0]) == 2
