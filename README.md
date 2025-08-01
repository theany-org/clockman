# Clockman

> Terminal-based time tracking for developers who value privacy and simplicity

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Clockman is a privacy-focused, offline-first time tracking CLI designed for developers who want to track their work without sacrificing performance or privacy.

## Features

- **Privacy First** - All data stays local in SQLite database
- **Lightning Fast** - Zero-latency offline operation
- **Smart Tagging** - Organize tasks with custom tags
- **Beautiful Output** - Rich terminal interface with colors and formatting
- **Detailed Logging** - Comprehensive time tracking and reporting
- **Type Safe** - Built with modern Python and full type hints
- **Developer Friendly** - Clean CLI interface designed for technical workflows

## Quick Start

### Installation

```bash
pip install clockman
```

### Basic Usage

```bash
# Start tracking time
clockman start "Fix authentication bug" --tag backend --tag bug

# Check current status
clockman status

# Stop current session
clockman stop

# View your work log
clockman log
```

## Commands

### `clockman start <description>`

Start a new time tracking session.

```bash
# Basic usage
clockman start "Working on API endpoints"

# With tags for better organization
clockman start "Frontend refactoring" --tag frontend --tag refactor

# Multiple tags
clockman start "Database migration" --tag db --tag migration --tag urgent
```

### `clockman stop`

Stop the current tracking session.

```bash
clockman stop
```

### `clockman status`

Display current tracking status.

```bash
clockman status
# Output: Currently tracking: "Fix authentication bug" (2h 34m) [backend, bug]
```

### `clockman log`

View your complete work history.

```bash
clockman log
# Shows formatted table with all sessions, durations, and tags
```

### `clockman version`

Display version information.

```bash
clockman version
```

## Usage Examples

### Daily Development Workflow

```bash
# Morning standup prep
clockman start "Review PRs and plan day" --tag planning

# Main development work
clockman start "Implement user authentication" --tag feature --tag auth

# Bug fixing session
clockman start "Fix CSS layout issues" --tag bugfix --tag frontend

# Code review
clockman start "Review team PRs" --tag review

# End of day
clockman log  # Review what you accomplished
```

### Project Organization with Tags

```bash
# Frontend work
clockman start "Component refactoring" --tag frontend --tag react

# Backend API development
clockman start "REST API endpoints" --tag backend --tag api

# DevOps and deployment
clockman start "CI/CD pipeline setup" --tag devops --tag deployment

# Testing
clockman start "Unit test coverage" --tag testing --tag quality
```

## Configuration

Clockman stores all data locally in your system's application data directory:

- **Linux**: `~/.local/share/clockman/`
- **macOS**: `~/Library/Application Support/clockman/`
- **Windows**: `%APPDATA%\clockman\`

The SQLite database (`tracking.db`) contains all your time tracking data.

## Architecture

Clockman is built with a clean, modular architecture:

```bash
clockman/
    cli/           # Command-line interface
    core/          # Core business logic
    db/            # Database operations
    utils/         # Utility functions
    tests/         # Test suite
```

**Key Technologies:**

- **Typer** - Modern CLI framework
- **Rich** - Beautiful terminal formatting
- **Pydantic** - Data validation and serialization
- **SQLite** - Local data storage
- **Pytest** - Testing framework

## Contributing

We welcome contributions Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for details on:

- Code style and standards
- Testing requirements
- Pull request process
- Issue reporting

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with ❤️ by the Theany Team for developers who value privacy and productivity.

---

**Questions or issues?** [Open an issue](https://github.com/theany-org/clockman/issues) on GitHub.
