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
        analysis_time = time.time() - start_time
        
        print(f"Analysis time for 100 changes: {analysis_time:.2f}s")
        
        # Should complete within reasonable time (less than 5 seconds)
        assert analysis_time < 5.0
        assert len(changes) == 100

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
    
    # Get final memory usage
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory
    
    print(f"Memory usage: {initial_memory:.1f}MB -> {final_memory:.1f}MB (+{memory_increase:.1f}MB)")
    
    # Should not use excessive memory (less than 200MB increase)
    assert memory_increase < 200
    assert len(changes) == 100

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
        return analyzer._collect_changes()
    
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
        assert len(result) == 10

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
    
    commit_time = time.time() - start_time
    print(f"Time for 100 commits: {commit_time:.2f}s")
    
    # Should complete within reasonable time
    assert commit_time < 10.0
    
    # Test commit analysis performance
    start_time = time.time()
    analyzer = ChangeAnalyzer(performance_repo)
    changes = analyzer._collect_changes()
    analysis_time = time.time() - start_time
    
    print(f"Analysis time with git history: {analysis_time:.2f}s")
    
    # Should complete within reasonable time
    assert analysis_time < 2.0

@pytest.mark.asyncio
async def test_stress_test_many_small_changes(performance_repo):
    """Stress test with many small changes."""
    # Create many small files and modify them rapidly
    repo = Repo(performance_repo)
    
    # Create initial files
    for i in range(1000):
        file_path = Path(performance_repo) / f"file_{i}.txt"
        file_path.write_text(f"Initial content {i}")
    
    repo.index.add(["."])
    repo.index.commit("Initial commit")
    
    # Rapidly modify files
    start_time = time.time()
    
    for iteration in range(10):
        for i in range(0, 1000, 10):
            file_path = Path(performance_repo) / f"file_{i}.txt"
            file_path.write_text(f"Modified content {i} iteration {iteration}")
        
        # Analyze changes
        analyzer = ChangeAnalyzer(performance_repo)
        changes = analyzer._collect_changes()
        
        # Commit changes
        repo.index.add(["."])
        repo.index.commit(f"Iteration {iteration}")
    
    total_time = time.time() - start_time
    print(f"Stress test time: {total_time:.2f}s")
    
    # Should complete within reasonable time
    assert total_time < 30.0

@pytest.mark.asyncio
async def test_performance_with_binary_files(performance_repo):
    """Test performance with many binary files."""
    # Create many binary files
    for i in range(100):
        file_path = Path(performance_repo) / f"binary_{i}.bin"
        # Create fake binary data
        binary_data = bytes([i % 256] * 1024)  # 1KB of data
        file_path.write_bytes(binary_data)
    
    repo = Repo(performance_repo)
    repo.index.add(["."])
    repo.index.commit("Add binary files")
    
    # Modify some binary files
    for i in range(0, 100, 10):
        file_path = Path(performance_repo) / f"binary_{i}.bin"
        binary_data = bytes([(i + 1) % 256] * 1024)
        file_path.write_bytes(binary_data)
    
    # Test analysis performance
    start_time = time.time()
    analyzer = ChangeAnalyzer(performance_repo)
    changes = analyzer._collect_changes()
    analysis_time = time.time() - start_time
    
    print(f"Analysis time with binary files: {analysis_time:.2f}s")
    
    # Should complete within reasonable time
    assert analysis_time < 2.0
    assert len(changes) == 10

@pytest.mark.asyncio
async def test_performance_with_deep_directory_structure(performance_repo):
    """Test performance with deep directory structure."""
    # Create deep directory structure
    depth = 20
    current_path = Path(performance_repo)
    
    for d in range(depth):
        current_path = current_path / f"level_{d}"
        current_path.mkdir(exist_ok=True)
        
        # Create a file at each level
        file_path = current_path / f"file_level_{d}.txt"
        file_path.write_text(f"Content at level {d}")
    
    repo = Repo(performance_repo)
    repo.index.add(["."])
    repo.index.commit("Add deep structure")
    
    # Modify files at different levels
    for d in range(0, depth, 2):
        file_path = Path(performance_repo)
        for level in range(d + 1):
            file_path = file_path / f"level_{level}"
        file_path = file_path / f"file_level_{d}.txt"
        file_path.write_text(f"Modified content at level {d}")
    
    # Test analysis performance
    start_time = time.time()
    analyzer = ChangeAnalyzer(performance_repo)
    changes = analyzer._collect_changes()
    analysis_time = time.time() - start_time
    
    print(f"Analysis time with deep structure: {analysis_time:.2f}s")
    
    # Should complete within reasonable time
    assert analysis_time < 3.0
    assert len(changes) == depth // 2

@pytest.mark.asyncio
async def test_performance_with_large_commit_messages(performance_repo):
    """Test performance with large commit messages."""
    # Create a test file
    test_file = Path(performance_repo) / "test.txt"
    test_file.write_text("Test content")
    
    # Create commit unit with large message
    large_body = "This is a very long commit message body. " * 1000  # ~50KB
    commit_unit = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="add large commit message test",
        files=["test.txt"],
        body=large_body,
        message="feat(test): add large commit message test"
    )
    
    # Test commit performance
    start_time = time.time()
    committer = GitCommitter(performance_repo)
    success = await committer.commit_changes([commit_unit])
    commit_time = time.time() - start_time
    
    print(f"Commit time with large message: {commit_time:.2f}s")
    
    # Should complete within reasonable time
    assert commit_time < 1.0
    assert success is True

@pytest.mark.asyncio
async def test_performance_with_many_observers(performance_repo):
    """Test performance with many observers."""
    from gitsmartcommit.observers import GitOperationObserver
    
    # Create many mock observers
    observers = []
    for i in range(100):
        observer = Mock(spec=GitOperationObserver)
        observer.on_commit_created = AsyncMock()
        observer.on_push_completed = AsyncMock()
        observers.append(observer)
    
    # Create a test file
    test_file = Path(performance_repo) / "test.txt"
    test_file.write_text("Test content")
    
    # Create commit unit
    commit_unit = CommitUnit(
        type=CommitType.FEAT,
        scope="test",
        description="add observer performance test",
        files=["test.txt"],
        body="Test observer performance",
        message="feat(test): add observer performance test"
    )
    
    # Test performance with many observers
    start_time = time.time()
    committer = GitCommitter(performance_repo)
    
    # Add all observers
    for observer in observers:
        committer.add_observer(observer)
    
    # Commit changes
    success = await committer.commit_changes([commit_unit])
    total_time = time.time() - start_time
    
    print(f"Commit time with 100 observers: {total_time:.2f}s")
    
    # Should complete within reasonable time
    assert total_time < 2.0
    assert success is True
    
    # Verify all observers were notified
    for observer in observers:
        observer.on_commit_created.assert_called_once()

@pytest.mark.asyncio
async def test_performance_with_complex_git_history(performance_repo):
    """Test performance with complex git history."""
    repo = Repo(performance_repo)
    
    # Create complex git history with branches and merges
    for i in range(50):
        # Create a file
        file_path = Path(performance_repo) / f"file_{i}.txt"
        file_path.write_text(f"Content {i}")
        
        # Commit
        repo.index.add([f"file_{i}.txt"])
        commit = repo.index.commit(f"Add file {i}")
        
        # Create a branch every 10 commits
        if i % 10 == 0:
            branch_name = f"branch_{i}"
            repo.create_head(branch_name, commit)
            
            # Switch to branch and make changes
            repo.head.reference = repo.heads[branch_name]
            file_path.write_text(f"Branch content {i}")
            repo.index.add([f"file_{i}.txt"])
            repo.index.commit(f"Branch commit {i}")
            
            # Switch back to main and merge
            repo.head.reference = repo.heads.master
            repo.git.merge(branch_name)
    
    # Modify some files
    for i in range(0, 50, 5):
        file_path = Path(performance_repo) / f"file_{i}.txt"
        file_path.write_text(f"Final content {i}")
    
    # Test analysis performance
    start_time = time.time()
    analyzer = ChangeAnalyzer(performance_repo)
    changes = analyzer._collect_changes()
    analysis_time = time.time() - start_time
    
    print(f"Analysis time with complex history: {analysis_time:.2f}s")
    
    # Should complete within reasonable time
    assert analysis_time < 5.0
    assert len(changes) == 10
