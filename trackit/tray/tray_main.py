"""
Standalone entry point for the TrackIt system tray application.

This can be used to launch the tray application directly without the CLI.
"""

import logging
import sys
from pathlib import Path

# Add the trackit package to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from trackit.tray.tray_manager import TrayManager


def setup_logging() -> None:
    """Set up logging for the tray application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(Path.home() / ".trackit" / "tray.log"),
        ],
    )


def main() -> None:
    """Main entry point for the tray application."""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting TrackIt system tray application")
        tray_manager = TrayManager()
        tray_manager.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as e:
        logger.error(f"Error running tray application: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
