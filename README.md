# GitSmartCommit

A smart Git commit assistant that helps you create better commits by analyzing your changes and suggesting logical commit units with appropriate commit messages.

## Features

- Analyzes repository changes and groups them into logical units
- Generates conventional commit messages
- Supports multiple commit message formats
- Validates commit messages against best practices
- Provides undo functionality for git operations
- Supports logging and notifications for git operations

## Installation

Currently, GitSmartCommit needs to be installed from source:

```bash
# Clone the repository
git clone https://github.com/yourusername/gitsmartcommit.git
cd gitsmartcommit

# Create a virtual environment (optional but recommended)
python -m venv venv

# Activate the virtual environment:
# For bash/zsh:
source venv/bin/activate
# For fish:
source venv/bin/activate.fish
# For Windows Command Prompt:
venv\Scripts\activate.bat
# For Windows PowerShell:
venv\Scripts\Activate.ps1

# Install the package in editable mode with development dependencies
pip install -e ".[dev]"
```

## Usage

After installation, you can use the `gitsmartcommit` command in any git repository:

```bash
# Basic usage (analyzes current directory)
gitsmartcommit

# Get help and see all available options
gitsmartcommit --help
```

### Options

```bash
# Specify repository path (defaults to current directory)
gitsmartcommit -p /path/to/repo
gitsmartcommit --path /path/to/repo

# Preview commits without making changes
gitsmartcommit -d
gitsmartcommit --dry-run

# Automatically push changes after committing
gitsmartcommit -a
gitsmartcommit --auto-push

# Choose commit message style (conventional or simple)
gitsmartcommit -c simple (or -c conventional)
gitsmartcommit --commit-style simple (or --commit-style conventional)

# Log operations to a file
gitsmartcommit -l git_operations.log
gitsmartcommit --log-file git_operations.log
```

The tool will:

1. Analyze your repository changes
2. Group related changes into logical commits
3. Generate meaningful commit messages
4. Create the commits (unless --dry-run is used)
5. Optionally push changes to remote (if --auto-push is used)

## Architecture

GitSmartCommit uses several design patterns to maintain a clean and extensible codebase:

- Strategy Pattern for commit message generation
- Observer Pattern for git operation notifications
- Factory Pattern for creating AI agents
- Chain of Responsibility for commit message validation
- Command Pattern for git operations

For more details about the design patterns used, see [Design Patterns Documentation](docs/design_patterns.md).

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit your changes (`git commit -m 'feat: add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

When adding new features, please refer to the [Design Patterns Documentation](docs/design_patterns.md) to maintain consistency with the existing architecture.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.