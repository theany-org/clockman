"""
Main entry point for Clockman when run as a module.

Allows running with: python -m clockman
"""

from clockman.cli.main import app

if __name__ == "__main__":
    app()