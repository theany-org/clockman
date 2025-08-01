# TrackIt

> Terminal-based time tracking for developers who value privacy and simplicity

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

TrackIt is a privacy-focused, offline-first time tracking CLI designed for developers who want to track their work without sacrificing performance or privacy.

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
tracker start "Fix authentication bug" --tag backend --tag bug

# Check current status
tracker status

# Stop current session
tracker stop

# View your work log
tracker log
```

## Commands

### `tracker start <description>`

Start a new time tracking session.

```bash
# Basic usage
tracker start "Working on API endpoints"

# With tags for better organization
tracker start "Frontend refactoring" --tag frontend --tag refactor

# Multiple tags
tracker start "Database migration" --tag db --tag migration --tag urgent
```

### `tracker stop`

Stop the current tracking session.

```bash
tracker stop
```

### `tracker status`

Display current tracking status.

```bash
tracker status
# Output: Currently tracking: "Fix authentication bug" (2h 34m) [backend, bug]
```

### `tracker log`

View your complete work history.

```bash
tracker log
# Shows formatted table with all sessions, durations, and tags
```

### `tracker version`

Display version information.

```bash
tracker version
```

## Usage Examples

### Daily Development Workflow

```bash
# Morning standup prep
tracker start "Review PRs and plan day" --tag planning

# Main development work
tracker start "Implement user authentication" --tag feature --tag auth

# Bug fixing session
tracker start "Fix CSS layout issues" --tag bugfix --tag frontend

# Code review
tracker start "Review team PRs" --tag review

# End of day
tracker log  # Review what you accomplished
```

### Project Organization with Tags

```bash
# Frontend work
tracker start "Component refactoring" --tag frontend --tag react

# Backend API development
tracker start "REST API endpoints" --tag backend --tag api

# DevOps and deployment
tracker start "CI/CD pipeline setup" --tag devops --tag deployment

# Testing
tracker start "Unit test coverage" --tag testing --tag quality
```

## Configuration

TrackIt stores all data locally in your system's application data directory:

- **Linux**: `~/.local/share/trackit/`
- **macOS**: `~/Library/Application Support/trackit/`
- **Windows**: `%APPDATA%\trackit\`

The SQLite database (`tracking.db`) contains all your time tracking data.

## Architecture

TrackIt is built with a clean, modular architecture:

```bash
trackit/
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

**Questions or issues?** [Open an issue](https://github.com/theany-org/trackit/issues) on GitHub.
