# GitSmartCommit

An AI-enhanced Git commit tool that intelligently analyzes changes and creates meaningful commits.

## Features

- Automatically groups related changes across files into logical units
- Generates meaningful commit messages explaining WHY changes were made
- Uses conventional commit format
- Handles multiple commits and pushes automatically
- AI-powered analysis of code changes

## Installation

Using uv:

```bash
uv venv
source .venv/bin/activate  # or equivalent for your shell
uv pip install -e .
```

## Usage

```bash
# From any git repository
git smart-commit
```

The tool will:
1. Analyze all changes in your repository
2. Group related changes together
3. Create meaningful commits with proper conventional commit messages
4. Push changes to remote

## Development

Setup development environment:

```bash
# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT