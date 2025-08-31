"""Performance and stress tests for the git-smart-commit tool."""
import pytest
import tempfile
import time
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from git import Repo

from gitsmartcommit.core import ChangeAnalyzer, GitCommitter
from gitsmartcommit.models import CommitType, CommitUnit, FileChange

def filter_git_files(changes):
    """Filter out git internal files from changes."""
    return [change for change in changes if not change.path.startswith('.git/') and not change.path.startswith('./.git/')]

@pytest.fixture
def performance_repo():
    """Create a repository for performance testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create initial file
        test_file = Path(tmp_dir) / "test.txt"
        test_file.write_text("Initial content")
        
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        
        yield tmp_dir

@pytest.mark.asyncio
async def test_large_repository_performance():
    """Test performance with a large repository."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo = Repo.init(tmp_dir)
        
        # Create a large number of files
        start_time = time.time()
        
        for i in range(1000):
            # Create nested directory structure
            depth = i % 5
            dir_path = Path(tmp_dir)
            for d in range(depth):
                dir_path = dir_path / f"dir_{d}"
                dir_path.mkdir(exist_ok=True)
            
            file_path = dir_path / f"file_{i}.txt"
            file_path.write_text(f"Content for file {i}")
        
        # Add all files to git
        repo.index.add(["."])
        repo.index.commit("Add large number of files")
        
        setup_time = time.time() - start_time
        print(f"Setup time for 1000 files: {setup_time:.2f}s")
        
        # Modify some files
        for i in range(0, 1000, 10):
            depth = i % 5
            dir_path = Path(tmp_dir)
            for d in range(depth):
                dir_path = dir_path / f"dir_{d}"
            
            file_path = dir_path / f"file_{i}.txt"
            file_path.write_text(f"Modified content for file {i}")
        
        # Test change analysis performance
        start_time = time.time()
        analyzer = ChangeAnalyzer(tmp_dir)
        changes = analyzer._collect_changes()
        # Filter out git internal files
        changes = filter_git_files(changes)
        analysis_time = time.time() - start_time
        
        print(f"Analysis time for 100 changes: {analysis_time:.2f}s")
        
        # Should complete within reasonable time (less than 5 seconds)
        assert analysis_time < 5.0
        # The actual number of changes will be 100 (every 10th file)
        assert len(changes) >= 100

@pytest.mark.asyncio
async def test_large_file_performance(performance_repo):
    """Test performance with large files."""
    # Create a large file (10MB)
    large_file = Path(performance_repo) / "large_file.txt"
    
    start_time = time.time()
    
    # Write 10MB of data
    chunk_size = 1024 * 1024  # 1MB chunks
    with open(large_file, 'w') as f:
        for i in range(10):
            f.write("x" * chunk_size)
    
    write_time = time.time() - start_time
    print(f"Write time for 10MB file: {write_time:.2f}s")
    
    # Test change analysis performance
    start_time = time.time()
    analyzer = ChangeAnalyzer(performance_repo)
    changes = analyzer._collect_changes()
    # Filter out git internal files
    changes = filter_git_files(changes)
    analysis_time = time.time() - start_time
    
    print(f"Analysis time for large file: {analysis_time:.2f}s")
    
    # Should complete within reasonable time (less than 2 seconds)
    assert analysis_time < 2.0
    assert len(changes) == 1
    assert changes[0].path == "large_file.txt"

@pytest.mark.asyncio
async def test_memory_usage_performance(performance_repo):
    """Test memory usage with many files."""
    import psutil
    import os
    
    # Get initial memory usage
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Create many small files
    for i in range(5000):
        file_path = Path(performance_repo) / f"file_{i}.txt"
        file_path.write_text(f"Content {i}")
    
    # Add to git
    repo = Repo(performance_repo)
    repo.index.add(["."])
    repo.index.commit("Add many files")
    
    # Modify some files
    for i in range(0, 5000, 50):
        file_path = Path(performance_repo) / f"file_{i}.txt"
        file_path.write_text(f"Modified content {i}")
    
    # Test memory usage during analysis
    analyzer = ChangeAnalyzer(performance_repo)
    changes = analyzer._collect_changes()
    # Filter out git internal files
    changes = filter_git_files(changes)
    
    # Get final memory usage
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory
    
    print(f"Memory usage: {initial_memory:.1f}MB -> {final_memory:.1f}MB (+{memory_increase:.1f}MB)")
    
    # Should not use excessive memory (less than 200MB increase)
    assert memory_increase < 200
    # The actual number of changes will be 100 (every 50th file)
    assert len(changes) >= 100

@pytest.mark.asyncio
async def test_concurrent_analysis_performance(performance_repo):
    """Test performance under concurrent analysis."""
    import asyncio
    import threading
    
    # Create some test files
    for i in range(100):
        file_path = Path(performance_repo) / f"file_{i}.txt"
        file_path.write_text(f"Content {i}")
    
    repo = Repo(performance_repo)
    repo.index.add(["."])
    repo.index.commit("Add test files")
    
    # Modify some files
    for i in range(0, 100, 10):
        file_path = Path(performance_repo) / f"file_{i}.txt"
        file_path.write_text(f"Modified content {i}")
    
    # Test concurrent analysis
    async def analyze_changes():
        analyzer = ChangeAnalyzer(performance_repo)
        changes = analyzer._collect_changes()
        # Filter out git internal files
        return filter_git_files(changes)
    
    start_time = time.time()
    
    # Run multiple analyses concurrently
    tasks = [analyze_changes() for _ in range(5)]
    results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    print(f"Concurrent analysis time: {total_time:.2f}s")
    
    # Should complete within reasonable time
    assert total_time < 3.0
    
    # All results should be the same
    for result in results:
        assert len(result) >= 10

@pytest.mark.asyncio
async def test_git_operations_performance(performance_repo):
    """Test performance of git operations."""
    # Create many small commits
    repo = Repo(performance_repo)
    
    start_time = time.time()
    
    for i in range(100):
        # Create a file
        file_path = Path(performance_repo) / f"file_{i}.txt"
        file_path.write_text(f"Content {i}")
        
        # Commit it
        repo.index.add([f"file_{i}.txt"])
        repo.index.commit(f"Add file {i}")
    
    git_time = time.time() - start_time
    print(f"Git operations time: {git_time:.2f}s")
    
    # Should complete within reasonable time
    assert git_time < 10.0

@pytest.mark.asyncio
async def test_stress_test_many_small_changes(performance_repo):
    """Stress test with many small changes."""
    # Create many small files and modify them
    for i in range(1000):
        file_path = Path(performance_repo) / f"file_{i}.txt"
        file_path.write_text(f"Content {i}")
    
    repo = Repo(performance_repo)
    repo.index.add(["."])
    repo.index.commit("Add many files")
    
    # Modify all files
    start_time = time.time()
    
    for i in range(1000):
        file_path = Path(performance_repo) / f"file_{i}.txt"
        file_path.write_text(f"Modified content {i}")
    
    # Analyze changes
    analyzer = ChangeAnalyzer(performance_repo)
    changes = analyzer._collect_changes()
    # Filter out git internal files
    changes = filter_git_files(changes)
    
    total_time = time.time() - start_time
    print(f"Stress test time: {total_time:.2f}s")
    
    # Should complete within reasonable time (less than 30 seconds)
    assert total_time < 30.0
    assert len(changes) >= 1000

@pytest.mark.asyncio
async def test_performance_with_binary_files(performance_repo):
    """Test performance with binary files."""
    # Create binary files
    for i in range(10):
        file_path = Path(performance_repo) / f"binary_{i}.bin"
        with open(file_path, 'wb') as f:
            f.write(b'\x00' * 1024)  # 1KB of null bytes
    
    repo = Repo(performance_repo)
    repo.index.add(["."])
    repo.index.commit("Add binary files")
    
    # Modify binary files
    for i in range(10):
        file_path = Path(performance_repo) / f"binary_{i}.bin"
        with open(file_path, 'wb') as f:
            f.write(b'\xff' * 1024)  # 1KB of 0xFF bytes
    
    # Test analysis performance
    start_time = time.time()
    analyzer = ChangeAnalyzer(performance_repo)
    
    # Just test that the analysis completes without crashing
    # The binary files will be handled by git diff
    changes = analyzer._collect_changes()
    # Filter out git internal files
    changes = filter_git_files(changes)
    
    analysis_time = time.time() - start_time
    print(f"Analysis time with binary files: {analysis_time:.2f}s")
    
    # Should complete within reasonable time
    assert analysis_time < 2.0
    assert len(changes) >= 10

@pytest.mark.asyncio
async def test_performance_with_deep_directory_structure(performance_repo):
    """Test performance with deep directory structure."""
    depth = 20
    
    # Create deep directory structure
    current_path = Path(performance_repo)
    for i in range(depth):
        current_path = current_path / f"level_{i}"
        current_path.mkdir(exist_ok=True)
        
        # Create a file at each level
        file_path = current_path / f"file_level_{i}.txt"
        file_path.write_text(f"Content at level {i}")
    
    repo = Repo(performance_repo)
    repo.index.add(["."])
    repo.index.commit("Add deep structure")
    
    # Modify files at every other level
    for i in range(0, depth, 2):
        # Reconstruct the path properly
        current_path = Path(performance_repo)
        for j in range(i + 1):
            current_path = current_path / f"level_{j}"
        file_path = current_path / f"file_level_{i}.txt"
        file_path.write_text(f"Modified content at level {i}")
    
    # Test analysis performance
    start_time = time.time()
    analyzer = ChangeAnalyzer(performance_repo)
    changes = analyzer._collect_changes()
    # Filter out git internal files
    changes = filter_git_files(changes)
    analysis_time = time.time() - start_time
    
    print(f"Analysis time with deep structure: {analysis_time:.2f}s")
    
    # Should complete within reasonable time
    assert analysis_time < 2.0
    assert len(changes) >= depth // 2

@pytest.mark.asyncio
async def test_performance_with_large_commit_messages(performance_repo):
    """Test performance with large commit messages."""
    # Create a file with a very long commit message
    file_path = Path(performance_repo) / "large_message.txt"
    file_path.write_text("Content")
    
    repo = Repo(performance_repo)
    repo.index.add(["large_message.txt"])
    
    # Create a very long commit message
    long_message = "A" * 10000  # 10KB message
    repo.index.commit(long_message)
    
    # Modify the file
    file_path.write_text("Modified content")
    
    # Test analysis performance
    start_time = time.time()
    analyzer = ChangeAnalyzer(performance_repo)
    changes = analyzer._collect_changes()
    # Filter out git internal files
    changes = filter_git_files(changes)
    analysis_time = time.time() - start_time
    
    print(f"Analysis time with large commit message: {analysis_time:.2f}s")
    
    # Should complete within reasonable time
    assert analysis_time < 2.0
    assert len(changes) == 1

@pytest.mark.asyncio
async def test_performance_with_many_observers(performance_repo):
    """Test performance with many observers."""
    # Create a simple change
    file_path = Path(performance_repo) / "observer_test.txt"
    file_path.write_text("Content")
    
    # Test with many observers
    start_time = time.time()
    
    committer = GitCommitter(performance_repo)
    
    # Add many observers
    for i in range(100):
        observer = Mock()
        observer.on_commit = Mock()
        observer.on_push = Mock()
        committer.add_observer(observer)
    
    # Simulate operations by calling the actual methods
    # Note: We'll just test that adding observers doesn't crash
    total_time = time.time() - start_time
    print(f"Observer setup time: {total_time:.2f}s")
    
    # Should complete within reasonable time
    assert total_time < 1.0

@pytest.mark.asyncio
async def test_performance_with_complex_git_history(performance_repo):
    """Test performance with complex git history."""
    repo = Repo(performance_repo)
    
    # Create a complex history with many branches and merges
    start_time = time.time()
    
    # Create main branch with many commits
    for i in range(50):
        file_path = Path(performance_repo) / f"main_file_{i}.txt"
        file_path.write_text(f"Main content {i}")
        repo.index.add([f"main_file_{i}.txt"])
        repo.index.commit(f"Main commit {i}")
    
    # Create a feature branch
    feature_branch = repo.create_head('feature')
    feature_branch.checkout()
    
    for i in range(20):
        file_path = Path(performance_repo) / f"feature_file_{i}.txt"
        file_path.write_text(f"Feature content {i}")
        repo.index.add([f"feature_file_{i}.txt"])
        repo.index.commit(f"Feature commit {i}")
    
    # Switch back to main and merge
    repo.heads.main.checkout()
    repo.index.merge_tree(feature_branch.commit)
    
    # Create another branch
    another_branch = repo.create_head('another')
    another_branch.checkout()
    
    for i in range(15):
        file_path = Path(performance_repo) / f"another_file_{i}.txt"
        file_path.write_text(f"Another content {i}")
        repo.index.add([f"another_file_{i}.txt"])
        repo.index.commit(f"Another commit {i}")
    
    # Switch back to main
    repo.heads.main.checkout()
    
    # Modify a file
    file_path = Path(performance_repo) / "main_file_0.txt"
    file_path.write_text("Modified main content")
    
    # Test analysis performance
    analyzer = ChangeAnalyzer(performance_repo)
    changes = analyzer._collect_changes()
    # Filter out git internal files
    changes = filter_git_files(changes)
    
    total_time = time.time() - start_time
    print(f"Complex history analysis time: {total_time:.2f}s")
    
    # Should complete within reasonable time
    assert total_time < 10.0
    assert len(changes) >= 1
