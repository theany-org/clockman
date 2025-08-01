# Contributing to Clockman

Thank you for your interest in contributing to Clockman We welcome contributions from developers of all skill levels. This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Issue Guidelines](#issue-guidelines)
- [Feature Requests](#feature-requests)

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. We are committed to providing a welcoming and inclusive environment for all contributors.

## Getting Started

### Types of Contributions

We welcome several types of contributions:

- **Bug fixes** - Help us fix issues and improve stability
- **New features** - Add functionality that benefits all users
- **Documentation** - Improve README, code comments, or add examples
- **Testing** - Increase test coverage or improve test quality
- **Performance** - Optimize code for better performance
- **Code quality** - Refactor code for better maintainability

### Before You Start

1. Check existing [issues](https://github.com/theany-org/clockman/issues) to avoid duplicate work
2. For major changes, open an issue first to discuss your proposal
3. Fork the repository and create a feature branch

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- A text editor or IDE

### Setup Instructions

1. **Fork and clone the repository**

   ```bash
   git clone https://github.com/theany-org/clockman.git
   cd clockman
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**

   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify the setup**

   ```bash
   # Run tests
   pytest

   # Check code style
   black --check clockman/
   isort --check-only clockman/

   # Type checking
   mypy clockman/
   ```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-export-functionality`
- `bugfix/fix-timezone-handling`
- `docs/update-installation-guide`

### Development Workflow

1. **Create a new branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**

   - Write clean, readable code
   - Follow existing patterns and conventions
   - Add docstrings for new functions and classes
   - Update type hints as needed

3. **Test your changes**

   ```bash
   pytest
   ```

4. **Run code quality checks**

   ```bash
   black clockman/
   isort clockman/
   flake8 clockman/
   mypy clockman/
   ```

## Testing

We maintain high test coverage (target: 90%+). Please include tests for your changes.

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=clockman --cov-report=html

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests only
pytest -m "not slow"     # Skip slow tests
```

### Writing Tests

- **Unit tests**: Test individual functions and classes
- **Integration tests**: Test component interactions
- **End-to-end tests**: Test complete workflows

Example test structure:

```python
def test_start_tracking_session():
    """Test starting a new tracking session."""
    # Arrange
    clockman = TimeTracker()

    # Act
    session = clockman.start("Test task", tags=["test"])

    # Assert
    assert session.description == "Test task"
    assert "test" in session.tags
```

## Code Style

We use several tools to maintain consistent code style:

### Formatting

- **Black** for code formatting (88 character line length)
- **isort** for import sorting

### Linting

- **flake8** for style and error checking
- **mypy** for type checking

### Standards

- Use type hints for all functions and methods
- Write descriptive docstrings (Google style)
- Keep functions focused and single-purpose
- Use meaningful variable and function names

Example:

```python
def calculate_session_duration(start_time: datetime, end_time: datetime) -> timedelta:
    """Calculate the duration of a tracking session.

    Args:
        start_time: When the session started
        end_time: When the session ended

    Returns:
        The duration as a timedelta object

    Raises:
        ValueError: If end_time is before start_time
    """
    if end_time < start_time:
        raise ValueError("End time cannot be before start time")

    return end_time - start_time
```

## Submitting Changes

### Pull Request Process

1. **Ensure your code passes all checks**

   ```bash
   pytest
   black --check clockman/
   isort --check-only clockman/
   flake8 clockman/
   mypy clockman/
   ```

2. **Update documentation** if needed

   - Update README.md for new features
   - Add or update docstrings
   - Update command help text

3. **Create a pull request**
   - Use a clear, descriptive title
   - Provide a detailed description of changes
   - Reference any related issues
   - Include screenshots for UI changes

### Pull Request Template

```markdown
## Description

Brief description of changes

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Code refactoring
- [ ] Performance improvement

## Testing

- [ ] All tests pass
- [ ] New tests added (if applicable)
- [ ] Manual testing completed

## Checklist

- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
```

## Issue Guidelines

### Reporting Bugs

When reporting bugs, please include:

1. **Environment information**

   - Python version
   - Operating system
   - Clockman version

2. **Steps to reproduce**

   - Clear, numbered steps
   - Expected vs actual behavior
   - Any error messages

3. **Additional context**
   - Screenshots if applicable
   - Configuration details
   - Workarounds you've tried

### Bug Report Template

```markdown
**Environment:**

- Python version: 3.11.5
- OS: Ubuntu 20.04
- Clockman version: 1.0.0

**Description:**
Brief description of the bug

**Steps to Reproduce:**

1. Run `clockman start "test"`
2. Wait 5 minutes
3. Run `clockman status`
4. Observe incorrect time display

**Expected Behavior:**
Should display correct elapsed time

**Actual Behavior:**
Shows 0 minutes elapsed

**Additional Context:**
Add any other context about the problem here
```

## Feature Requests

We welcome feature requests! Please:

1. Check if the feature already exists or is planned
2. Describe the use case and benefits
3. Consider implementation complexity
4. Be open to discussion and alternatives

### Feature Request Template

```markdown
**Feature Description:**
Clear description of the proposed feature

**Use Case:**
Why is this feature needed? What problem does it solve?

**Proposed Solution:**
How do you envision this working?

**Alternatives Considered:**
Any alternative solutions you've considered

**Additional Context:**
Any other context or screenshots
```

## Development Tips

### Project Structure

```bash
clockman/
├── cli/           # CLI commands and interface
├── core/          # Core business logic
├── db/            # Database operations and models
├── utils/         # Utility functions
└── tests/         # Test suite
```

### Key Components

- **CLI Layer**: Uses Typer for command-line interface
- **Core Logic**: Time tracking business logic
- **Database**: SQLite with custom models
- **Utils**: Helper functions and utilities

### Common Tasks

**Adding a new CLI command:**

1. Add command function in `cli/commands.py`
2. Register with Typer app in `cli/main.py`
3. Add tests in `tests/cli/`
4. Update help documentation

**Adding a new database model:**

1. Define model in `db/models.py`
2. Create migration if needed
3. Add repository methods in `db/repository.py`
4. Add tests in `tests/db/`

## Getting Help

- **Documentation**: Check README.md and code comments
- **Issues**: Search existing issues or create a new one
- **Discussions**: Use GitHub Discussions for questions

## Recognition

Contributors will be recognized in our README and release notes. Thank you for helping make Clockman better!

---

### Happy contributing 🚀
