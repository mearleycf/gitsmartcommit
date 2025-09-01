"""Test commit message description improvements."""

import pytest
from pathlib import Path
from gitsmartcommit.commit_message.strategy import OllamaCommitStrategy
from gitsmartcommit.models import FileChange


class TestCommitDescriptionImprovements:
    """Test that commit messages are more specific and descriptive."""
    
    def test_web_files_generate_specific_descriptions(self):
        """Test that web files generate specific descriptions."""
        strategy = OllamaCommitStrategy()
        
        changes = [
            FileChange(
                path="web/src/pages/income.astro",
                status="modified",
                content_diff="Some changes to income page",
                is_staged=True
            ),
            FileChange(
                path="web/src/pages/index.astro", 
                status="modified",
                content_diff="Some changes to index page",
                is_staged=True
            )
        ]
        
        # Test the fallback message generation
        result = strategy._generate_fallback_message(changes, "Test context")
        
        assert result.commit_type == "feat"
        assert result.scope == "web"
        assert result.description == "update web pages"
        assert "update code" not in result.description.lower()
    
    def test_backend_files_generate_specific_descriptions(self):
        """Test that backend files generate specific descriptions."""
        strategy = OllamaCommitStrategy()
        
        changes = [
            FileChange(
                path="backend/api/api.py",
                status="modified", 
                content_diff="Some API changes",
                is_staged=True
            ),
            FileChange(
                path="backend/services/csv_import_service.py",
                status="modified",
                content_diff="Some service changes",
                is_staged=True
            )
        ]
        
        result = strategy._generate_fallback_message(changes, "Test context")
        
        assert result.commit_type == "feat"
        assert result.scope == "api"
        assert result.description == "update services"
        assert "update code" not in result.description.lower()
    
    def test_documentation_files_generate_specific_descriptions(self):
        """Test that documentation files generate specific descriptions."""
        strategy = OllamaCommitStrategy()
        
        changes = [
            FileChange(
                path="README.md",
                status="modified",
                content_diff="Some README changes",
                is_staged=True
            )
        ]
        
        result = strategy._generate_fallback_message(changes, "Test context")
        
        assert result.commit_type == "docs"
        assert result.scope == "documentation"
        assert result.description == "update readme"
        assert "update code" not in result.description.lower()
    
    def test_config_files_generate_specific_descriptions(self):
        """Test that configuration files generate specific descriptions."""
        strategy = OllamaCommitStrategy()
        
        changes = [
            FileChange(
                path="pyproject.toml",
                status="modified",
                content_diff="Some config changes",
                is_staged=True
            )
        ]
        
        result = strategy._generate_fallback_message(changes, "Test context")
        
        assert result.commit_type == "chore"
        assert result.scope == "config"
        assert result.description == "update project config"
        assert "update code" not in result.description.lower()
    
    def test_income_feature_files_generate_specific_descriptions(self):
        """Test that income-related files generate specific descriptions."""
        strategy = OllamaCommitStrategy()
        
        changes = [
            FileChange(
                path="src/income/processor.py",
                status="modified",
                content_diff="Some income processing changes",
                is_staged=True
            )
        ]
        
        result = strategy._generate_fallback_message(changes, "Test context")
        
        assert result.commit_type == "feat"
        assert result.scope == "income"
        assert result.description == "update income features"
        assert "update code" not in result.description.lower()
    
    def test_import_feature_files_generate_specific_descriptions(self):
        """Test that import-related files generate specific descriptions."""
        strategy = OllamaCommitStrategy()
        
        changes = [
            FileChange(
                path="src/import/handler.py",
                status="modified",
                content_diff="Some import handling changes",
                is_staged=True
            )
        ]
        
        result = strategy._generate_fallback_message(changes, "Test context")
        
        assert result.commit_type == "feat"
        assert result.scope == "import"
        assert result.description == "update import functionality"
        assert "update code" not in result.description.lower()
    
    def test_csv_files_generate_specific_descriptions(self):
        """Test that CSV-related files generate specific descriptions."""
        strategy = OllamaCommitStrategy()
        
        changes = [
            FileChange(
                path="src/csv/parser.py",
                status="modified",
                content_diff="Some CSV parsing changes",
                is_staged=True
            )
        ]
        
        result = strategy._generate_fallback_message(changes, "Test context")
        
        assert result.commit_type == "feat"
        assert result.scope == "csv"
        assert result.description == "update CSV processing"
        assert "update code" not in result.description.lower()
    
    def test_generic_files_still_have_reasonable_fallback(self):
        """Test that truly generic files still have a reasonable fallback."""
        strategy = OllamaCommitStrategy()
        
        changes = [
            FileChange(
                path="some_random_file.txt",
                status="modified",
                content_diff="Some random changes",
                is_staged=True
            )
        ]
        
        result = strategy._generate_fallback_message(changes, "Test context")
        
        # For truly generic files, "update code" is acceptable as a fallback
        # But we should have a meaningful reasoning
        assert result.description == "update code"  # This is the expected fallback
        assert len(result.reasoning) > 0
        assert "some_random_file.txt" in result.reasoning
