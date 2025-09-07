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

GitSmartCommit can be installed globally so you can use it from any repository without reinstalling.

### Quick Global Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/gitsmartcommit.git
cd gitsmartcommit

# Install globally (recommended)
python3 scripts/install_global.py
```

This will install `git-smart-commit` and the short alias `git-smart` in your PATH.

### Manual Installation

If you prefer to install manually:

```bash
# Clone the repository
git clone https://github.com/yourusername/gitsmartcommit.git
cd gitsmartcommit

# Install globally (recommended for regular use)
python3 -m pip install -e . --user

# Or install in a virtual environment for development
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[test]"
```

### Updating

To update your global installation with the latest changes:

```bash
cd gitsmartcommit
python3 scripts/update_global.py
```

Or use the quick update scripts:

```bash
# For bash/zsh
./update.sh

# For fish shell
./update.fish
```

Or manually:

```bash
python3 -m pip install -e . --user --force-reinstall
```

## Usage

After installation, you can use the `git-smart-commit` command (or the short alias `git-smart`) in any git repository:

```bash
# Basic usage (analyzes current directory)
git-smart-commit
# or
git-smart

# Get help and see all available options
git-smart-commit --help
# or
git-smart --help
```

### Options

- `-p, --path PATH`: Path to git repository (defaults to current directory)
- `-d, --dry-run`: Show proposed commits without making changes
- `-a, --auto-push`: Automatically push changes after committing
- `-m, --merge`: After pushing changes, merge into main branch and push
- `--main-branch TEXT`: Name of the main branch to merge into (defaults to 'main')
- `-c, --commit-style [conventional|simple]`: Style of commit messages to generate
- `-l, --log-file FILE`: Optional file to log git operations

## Examples

```bash
# Basic usage - analyze and commit changes
git-smart-commit

# Dry run to see proposed commits
git-smart-commit -d

# Auto-push changes after committing
git-smart-commit -a

# Auto-push and merge into main branch
git-smart-commit -a -m

# Auto-push and merge into a different main branch
git-smart-commit -a -m --main-branch develop

# Use simple commit style instead of conventional commits
git-smart-commit -c simple

# Log operations to a file
git-smart-commit -l git-operations.log
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

## Configuration

GitSmartCommit can be configured using a `.gitsmartcommit.toml` file in your repository root. This allows you to set default behaviors that can still be overridden by command line options.

Example configuration file:

```toml
# Name of the main branch to merge into (default: "main")
main_branch = "develop"

# Style of commit messages (default: "conventional")
# Options: "conventional" or "simple"
commit_style = "conventional"

# Name of the remote repository (default: "origin")
remote_name = "origin"

# Whether to automatically push changes after committing (default: false)
auto_push = true

# Whether to always generate log files (default: false)
always_log = true

# Custom log file path (ignored if always_log is true)
log_file = "git-operations.log"

# Directory to store timestamped log files (relative to repository root)
log_directory = "logs"

# AI model to use (default: "claude-3-5-sonnet-latest")
# Options: "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "gemini-pro", "qwen2.5-coder:7b"
model = "claude-3-5-sonnet-latest"
```

When `always_log` is enabled, log files are automatically generated with names in the format `gsc_log-YYYY-MM-DD_HH-mm-ss.log`. If `log_directory` is specified, these timestamped log files will be created in that directory instead of the repository root.

Command line options take precedence over configuration file settings. For example, if `auto_push = false` in the config file but you use the `-a` flag, changes will be pushed.

### API Keys

For security reasons, API keys should NOT be stored in the configuration file. Instead, provide them through environment variables:

```bash
# For Gemini
export GEMINI_API_KEY="your-key"
# Or
export GOOGLE_API_KEY="your-key"

# For Claude
export ANTHROPIC_API_KEY="your-key"

# For Qwen (via HuggingFace)
export HF_TOKEN="your-huggingface-token"

# For Qwen (via Ollama - no token needed)
# Just make sure Ollama is running and the model is installed
```

You can also provide the API key via the `--api-key` flag, but this is not recommended as it may be visible in your shell history:

```bash
git smart-commit --model gemini-pro --api-key "your-key"  # Not recommended
```

## AI Models

GitSmartCommit supports multiple AI models for generating commit messages and analyzing changes:

1. Qwen (default)
   - Models: qwen2.5-coder:7b (default), and other Qwen models
   - Options:
     - **HuggingFace**: Requires HF_TOKEN environment variable (HuggingFace API token)
     - **Ollama**: No API token required (runs locally via Ollama API)

2. Anthropic Claude
   - Models: claude-3-5-sonnet-latest, claude-3-5-haiku-latest
   - Requires: ANTHROPIC_API_KEY environment variable

3. Google Gemini
   - Model: gemini-pro (automatically uses latest production version)
   - Requires: GEMINI_API_KEY or GOOGLE_API_KEY environment variable

4. Qwen
   - Models: qwen2.5-coder:7b (and other Qwen models)
   - Options:
     - **HuggingFace**: Requires HF_TOKEN environment variable (HuggingFace API token)
     - **Ollama**: No API token required (runs locally via Ollama API)

You can select a model using the `--model` flag or configuration file:

```bash
# Use Qwen (default - Ollama)
git smart-commit

# Use Qwen (HuggingFace)
git smart-commit --model qwen2.5-coder:7b

# Use Qwen (Ollama - explicit)
git smart-commit --model ollama:qwen2.5-coder:7b

# Use Claude
git smart-commit --model claude-3-5-sonnet-latest

# Use Gemini
git smart-commit --model gemini-pro
```

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
