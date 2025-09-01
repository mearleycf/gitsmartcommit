# Changelog

## [Unreleased]

### Added

-

### Changed

-

### Fixed

-

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2025-09-01

### Added

-

### Changed

-

### Fixed

-

### Breaking Changes

-

### Added

- Version management system with automatic version checking
- `--version` flag to display current version
- `--check-updates` flag to check for newer versions
- `--verify-install` flag to verify installation integrity
- Comprehensive changelog tracking

### Changed

- Improved commit message descriptions to be more specific and descriptive
- Enhanced fallback logic to generate meaningful commit titles instead of generic "update code"
- Better file pattern analysis for determining commit types and scopes

### Fixed

- Generic commit message titles like "feat(general): update code" now generate specific descriptions
- Fallback scenarios now provide meaningful commit messages based on file analysis

## [0.1.0] - 2025-01-22

### Added

- Initial release of git-smart-commit
- AI-powered commit message generation
- Intelligent file grouping and batching
- Support for multiple AI models (Claude, Gemini, Qwen, Ollama)
- Conventional commit format support
- Git integration with staging, committing, and pushing
- Configuration management via TOML files
- Comprehensive test suite
- Documentation and examples

### Features

- Automatic change analysis and grouping
- Multiple commit strategies (Conventional, Simple, Ollama)
- Relationship analysis between changed files
- Fallback grouping for edge cases
- Validation of commit messages
- Observer pattern for extensibility
- Logging and debugging support
