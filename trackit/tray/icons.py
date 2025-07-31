"""
Icon generation utilities for the system tray.

This module creates simple icons programmatically using PIL.
"""

from io import BytesIO
from typing import Tuple

from PIL import Image, ImageDraw


def create_tray_icon(
    size: Tuple[int, int] = (64, 64),
    is_active: bool = False,
    background_color: str = "white",
) -> Image.Image:
    """
    Create a system tray icon for TrackIt.

    Args:
        size: Icon size as (width, height) tuple
        is_active: Whether to show the active state (green) or inactive state (gray)
        background_color: Background color for the icon

    Returns:
        PIL Image object
    """
    # Create a new image with transparent background
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    # Calculate sizes based on icon dimensions
    center_x, center_y = size[0] // 2, size[1] // 2
    radius = min(size) // 3

    # Choose colors based on active state
    if is_active:
        circle_color = "#22c55e"  # Green for active
        text_color = "white"
    else:
        circle_color = "#6b7280"  # Gray for inactive
        text_color = "white"

    # Draw the main circle
    draw.ellipse(
        [
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
        ],
        fill=circle_color,
        outline="#374151",
        width=2,
    )

    # Draw a clock-like symbol
    clock_radius = radius // 2

    # Clock hands
    if is_active:
        # Draw "running" clock hands
        hand_length = clock_radius - 4
        # Hour hand (pointing to 2)
        draw.line(
            [
                center_x,
                center_y,
                center_x + hand_length // 2,
                center_y - hand_length // 2,
            ],
            fill=text_color,
            width=3,
        )
        # Minute hand (pointing to 12)
        draw.line(
            [center_x, center_y, center_x, center_y - hand_length],
            fill=text_color,
            width=2,
        )
    else:
        # Draw stopped clock hands (both pointing to 12)
        hand_length = clock_radius - 4
        draw.line(
            [center_x, center_y, center_x, center_y - hand_length],
            fill=text_color,
            width=3,
        )
        draw.line(
            [center_x, center_y, center_x, center_y - hand_length // 2],
            fill=text_color,
            width=2,
        )

    # Draw center dot
    dot_radius = 2
    draw.ellipse(
        [
            center_x - dot_radius,
            center_y - dot_radius,
            center_x + dot_radius,
            center_y + dot_radius,
        ],
        fill=text_color,
    )

    return image


def create_notification_icon(size: Tuple[int, int] = (64, 64)) -> Image.Image:
    """
    Create a notification icon for TrackIt.

    Args:
        size: Icon size as (width, height) tuple

    Returns:
        PIL Image object
    """
    return create_tray_icon(size, is_active=True)


def icon_to_bytes(icon: Image.Image) -> bytes:
    """
    Convert PIL Image to bytes for use with pystray.

    Args:
        icon: PIL Image object

    Returns:
        Icon data as bytes
    """
    buffer = BytesIO()
    icon.save(buffer, format="PNG")
    return buffer.getvalue()
