# GitSmartCommit

An AI-enhanced Git commit tool that intelligently analyzes changes and creates meaningful commits.

## Features

- Automatically groups related changes across files into logical units
- Generates meaningful commit messages explaining WHY changes were made
- Uses conventional commit format (feat, fix, docs, style, refactor, test, chore)
- Handles multiple commits and groups them logically
- AI-powered analysis of code changes
- Optional automatic pushing to remote

## Installation

Using uv:

```bash
uv venv
source .venv/bin/activate  # or equivalent for your shell
uv pip install -e .
```

Required dependencies:
- Python >= 3.9
- gitpython >= 3.1.44
- pydantic >= 2.0.0
- pydantic-ai >= 0.0.19
- rich >= 13.0.0
- click >= 8.0.0
- asyncio >= 3.4.3

## Usage

```bash
# From any git repository
git smart-commit [OPTIONS]

Options:
  --path TEXT      Path to git repository (defaults to current directory)
  --dry-run        Show proposed commits without making changes
  --auto-push      Automatically push changes after committing
  --help          Show this message and exit
```

The tool will:
1. Analyze all changes in your repository
2. Group related changes together
3. Create meaningful commits with proper conventional commit messages
4. Optionally push changes to remote (with --auto-push flag)

## Development

Setup development environment:

```bash
# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install development dependencies
uv pip install -e ".[dev]"

# Development dependencies include:
# - pytest >= 7.0.0
# - pytest-asyncio >= 0.21.0
# - pytest-cov >= 4.0.0

# Run tests
pytest
```

## License

MIT