#!/usr/bin/env python3
"""Version bumping script for git-smart-commit."""

import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Tuple

def parse_version(version: str) -> Tuple[int, int, int]:
    """Parse version string into major, minor, patch components."""
    match = re.match(r'(\d+)\.(\d+)\.(\d+)', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    return tuple(int(x) for x in match.groups())

def format_version(major: int, minor: int, patch: int) -> str:
    """Format version components into version string."""
    return f"{major}.{minor}.{patch}"

def bump_version(current_version: str, bump_type: str) -> str:
    """Bump version according to semantic versioning."""
    major, minor, patch = parse_version(current_version)
    
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")
    
    return format_version(major, minor, patch)

def update_pyproject_toml(project_root: Path, new_version: str) -> None:
    """Update version in pyproject.toml."""
    pyproject_path = project_root / "pyproject.toml"
    
    with open(pyproject_path, 'r') as f:
        content = f.read()
    
    # Update version in pyproject.toml
    content = re.sub(
        r'version = "([^"]+)"',
        f'version = "{new_version}"',
        content
    )
    
    with open(pyproject_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated pyproject.toml to version {new_version}")

def update_init_py(project_root: Path, new_version: str) -> None:
    """Update version in __init__.py."""
    init_path = project_root / "gitsmartcommit" / "__init__.py"
    
    with open(init_path, 'r') as f:
        content = f.read()
    
    # Update version in __init__.py
    content = re.sub(
        r'__version__ = "([^"]+)"',
        f'__version__ = "{new_version}"',
        content
    )
    
    with open(init_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated __init__.py to version {new_version}")

def update_changelog(project_root: Path, new_version: str, bump_type: str) -> None:
    """Update CHANGELOG.md with new version."""
    changelog_path = project_root / "CHANGELOG.md"
    
    with open(changelog_path, 'r') as f:
        content = f.read()
    
    # Get current date
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Create new version entry
    new_entry = f"""## [{new_version}] - {today}

### Added
- 

### Changed
- 

### Fixed
- 

### Breaking Changes
- 

"""
    
    # Replace [Unreleased] with the new version
    content = content.replace("## [Unreleased]", new_entry.rstrip())
    
    # Add new [Unreleased] section at the top
    unreleased_section = """## [Unreleased]

### Added
- 

### Changed
- 

### Fixed
- 

"""
    
    # Insert after the header
    lines = content.split('\n')
    insert_index = 0
    for i, line in enumerate(lines):
        if line.startswith('# Changelog'):
            insert_index = i + 2  # Insert after the header and blank line
            break
    
    lines.insert(insert_index, unreleased_section)
    content = '\n'.join(lines)
    
    with open(changelog_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated CHANGELOG.md with version {new_version}")

def get_current_version(project_root: Path) -> str:
    """Get current version from pyproject.toml."""
    pyproject_path = project_root / "pyproject.toml"
    
    with open(pyproject_path, 'r') as f:
        content = f.read()
    
    match = re.search(r'version = "([^"]+)"', content)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    
    return match.group(1)

def main():
    """Main function for version bumping."""
    if len(sys.argv) != 2:
        print("Usage: python bump_version.py <major|minor|patch>")
        sys.exit(1)
    
    bump_type = sys.argv[1].lower()
    if bump_type not in ["major", "minor", "patch"]:
        print("Error: bump type must be 'major', 'minor', or 'patch'")
        sys.exit(1)
    
    # Get project root (assuming script is in scripts/ directory)
    project_root = Path(__file__).parent.parent
    
    try:
        # Get current version
        current_version = get_current_version(project_root)
        print(f"Current version: {current_version}")
        
        # Calculate new version
        new_version = bump_version(current_version, bump_type)
        print(f"New version: {new_version}")
        
        # Update files
        update_pyproject_toml(project_root, new_version)
        update_init_py(project_root, new_version)
        update_changelog(project_root, new_version, bump_type)
        
        print(f"\n🎉 Successfully bumped version from {current_version} to {new_version}")
        print("\nNext steps:")
        print("1. Review and update the CHANGELOG.md with actual changes")
        print("2. Commit the version bump:")
        print(f"   git add .")
        print(f"   git commit -m 'chore: bump version to {new_version}'")
        print("3. Tag the release:")
        print(f"   git tag v{new_version}")
        print("4. Push changes:")
        print(f"   git push && git push --tags")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
