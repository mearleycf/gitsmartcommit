# GitSmartCommit

An AI-enhanced Git commit tool that intelligently analyzes changes and creates meaningful commits.

## Features

- Automatically groups related changes across files into logical units
- Generates meaningful commit messages explaining WHY changes were made
- Supports multiple commit message styles (conventional and simple)
- Handles multiple commits and groups them logically
- AI-powered analysis of code changes
- Optional automatic pushing to remote
- Detailed operation logging (console and file-based)
- Smart handling of both single-file and multi-file changes

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
  -p, --path TEXT      Path to git repository (defaults to current directory)
  -d, --dry-run        Show proposed commits without making changes
  -a, --auto-push      Automatically push changes after committing
  -c, --commit-style   Style of commit messages to generate (conventional or simple)
  -l, --log-file FILE  Optional file to log git operations
  --help              Show this message and exit
```

The tool will:
1. Analyze all changes in your repository (with helpful debug output)
2. Group related changes together
3. Create meaningful commits with your chosen commit message style:
   - conventional: Uses conventional commit format (feat, fix, docs, etc.)
   - simple: Uses a simpler, more readable format
4. Log all operations to the console and optionally to a file
5. Optionally push changes to remote (with --auto-push flag)

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