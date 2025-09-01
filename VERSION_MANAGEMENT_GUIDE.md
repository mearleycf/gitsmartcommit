# Version Management Guide for git-smart-commit

## Overview

We've implemented a comprehensive version management system for git-smart-commit that allows you to:

- Track versions properly with semantic versioning
- Check for updates and verify installations
- Automatically bump versions and update changelogs
- Manage installations across multiple repositories

## Current Version

**git-smart-commit is now at version 0.1.1**

## New CLI Commands

### 1. Version Information

```bash
git-smart-commit --version
```

Displays comprehensive version information including:

- Current version
- Installed version
- Installation path
- Installation verification status

### 2. Check for Updates

```bash
git-smart-commit --check-updates
```

Checks if there are newer versions available and provides update instructions.

### 3. Verify Installation

```bash
git-smart-commit --verify-install
```

Verifies that all components are properly installed and working correctly.

## Version Management Scripts

### 1. Version Bumping Script

Located at: `scripts/bump_version.py`

**Usage:**

```bash
# Bump patch version (0.1.0 → 0.1.1)
python scripts/bump_version.py patch

# Bump minor version (0.1.0 → 0.2.0)
python scripts/bump_version.py minor

# Bump major version (0.1.0 → 1.0.0)
python scripts/bump_version.py major
```

**What it does:**

- Updates version in `pyproject.toml`
- Updates version in `gitsmartcommit/__init__.py`
- Updates `CHANGELOG.md` with new version entry
- Provides next steps for committing and tagging

### 2. Update Checker Script

Located at: `scripts/update_gitsmartcommit.py`

**Usage:**

```bash
python scripts/update_gitsmartcommit.py
```

**What it does:**

- Checks current installation status
- Detects if you have an editable or pip installation
- Offers to update to the latest version
- Verifies installation integrity

## How to Use in Other Repositories

### Option 1: Editable Installation (Recommended for Development)

```bash
# In your other repository (e.g., balanceit2)
cd ~/code/balanceit2

# Check current version
git-smart-commit --version

# Check for updates
git-smart-commit --check-updates

# Verify installation
git-smart-commit --verify-install
```

### Option 2: Automatic Updates

```bash
# Run the update script from any repository
python /Users/mikeearley/code/gitsmartcommit/scripts/update_gitsmartcommit.py
```

This script will:

- Detect your installation type
- Check for newer versions
- Offer to update automatically
- Verify the update was successful

## Version Bumping Workflow

When you make significant changes to git-smart-commit:

### 1. Bump Version

```bash
cd ~/code/gitsmartcommit

# For bug fixes and minor improvements
python scripts/bump_version.py patch

# For new features
python scripts/bump_version.py minor

# For breaking changes
python scripts/bump_version.py major
```

### 2. Update Changelog

The script automatically creates a new version entry in `CHANGELOG.md`. Edit it to include:

- What was added
- What was changed
- What was fixed
- Any breaking changes

### 3. Commit and Tag

```bash
git add .
git commit -m "chore: bump version to 0.1.1"
git tag v0.1.1
git push && git push --tags
```

### 4. Reinstall

```bash
pip install -e .
```

## Semantic Versioning

We follow [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for added functionality in a backward compatible manner
- **PATCH** version for backward compatible bug fixes

## File Locations

- **Version definition**: `pyproject.toml` and `gitsmartcommit/__init__.py`
- **Changelog**: `CHANGELOG.md`
- **Version management**: `gitsmartcommit/version.py`
- **Update scripts**: `scripts/` directory

## Benefits

1. **Clear Version Tracking**: Know exactly which version you're running
2. **Easy Updates**: Simple commands to check and update versions
3. **Installation Verification**: Ensure everything is working correctly
4. **Automatic Changelog**: Keep track of what changed in each version
5. **Cross-Repository Management**: Manage versions across multiple projects

## Troubleshooting

### Version Mismatch

If you see a version mismatch:

```bash
git-smart-commit --version
# Shows: Current version: 0.1.1 (installed: 0.1.0)
```

**Solution:**

```bash
pip install -e .
```

**If the above doesn't work, try clearing Python cache:**
```bash
# From the gitsmartcommit directory
find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
pip install -e .
```

This issue can occur when Python cached bytecode files contain outdated version information.

### Installation Verification Failed

```bash
git-smart-commit --verify-install
```

**Common solutions:**

1. Reinstall: `pip install -e .`
2. Check Python environment
3. Verify file permissions

### Update Script Not Working

Make sure you're running it from the correct location:

```bash
# From any repository
python /Users/mikeearley/code/gitsmartcommit/scripts/update_gitsmartcommit.py
```

## Best Practices

1. **Always bump version** before committing significant changes
2. **Update changelog** with meaningful descriptions
3. **Test new versions** before pushing tags
4. **Use semantic versioning** appropriately
5. **Verify installations** after updates

## Future Enhancements

- PyPI integration for automatic version checking
- GitHub releases integration
- Automated changelog generation from commit messages
- Version compatibility checking
- Rollback functionality

---

This version management system ensures that git-smart-commit is properly versioned and easy to maintain across multiple repositories! 🎉
