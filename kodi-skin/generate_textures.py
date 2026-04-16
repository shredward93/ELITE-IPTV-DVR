"""
Generate missing texture files for the ELITE IPTV DVR Kodi skin.
Creates minimal PNG images using pure Python (no external dependencies).
Run once: python generate_textures.py
"""
import struct
import zlib
import os

MEDIA_DIR = os.path.join(os.path.dirname(__file__), "skin.elite.dvr", "media")
ICONS_DIR = os.path.join(MEDIA_DIR, "icons")


def create_rgba_png(width, height, pixels_fn):
    """Create a PNG file from an RGBA pixel generator function."""
    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = zlib.crc32(c) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + c + struct.pack(">I", crc)

    raw = b""
    for y in range(height):
        raw += b"\x00"  # filter: none
        for x in range(width):
            r, g, b, a = pixels_fn(x, y, width, height)
            raw += struct.pack("BBBB", r, g, b, a)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def solid_white(x, y, w, h):
    return (255, 255, 255, 255)


def circle_pixel(x, y, w, h):
    cx, cy = w / 2, h / 2
    r = min(cx, cy)
    dx, dy = x - cx + 0.5, y - cy + 0.5
    dist = (dx * dx + dy * dy) ** 0.5
    if dist <= r - 1:
        return (255, 255, 255, 255)
    elif dist <= r:
        alpha = int(255 * max(0, r - dist))
        return (255, 255, 255, alpha)
    return (0, 0, 0, 0)


def rounded_rect_pixel(x, y, w, h, radius=8):
    """White rounded rectangle with anti-aliased corners."""
    def corner_dist(cx, cy):
        dx, dy = abs(x - cx), abs(y - cy)
        if dx <= 0 and dy <= 0:
            return -1  # inside
        return (dx * dx + dy * dy) ** 0.5

    r = min(radius, w // 2, h // 2)
    inside = True
    alpha = 255

    # Check each corner
    corners = [
        (r, r),                  # top-left
        (w - 1 - r, r),         # top-right
        (r, h - 1 - r),         # bottom-left
        (w - 1 - r, h - 1 - r)  # bottom-right
    ]

    for cx, cy in corners:
        in_corner_x = (x <= r and cx == r) or (x >= w - 1 - r and cx == w - 1 - r)
        in_corner_y = (y <= r and cy == r) or (y >= h - 1 - r and cy == h - 1 - r)
        if in_corner_x and in_corner_y:
            dx = abs(x - cx)
            dy = abs(y - cy)
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > r:
                return (0, 0, 0, 0)
            elif dist > r - 1.5:
                alpha = int(255 * max(0, (r - dist) / 1.5))
                return (255, 255, 255, alpha)

    return (255, 255, 255, 255)


def pill_pixel(x, y, w, h):
    """Fully rounded pill shape (radius = height/2)."""
    return rounded_rect_pixel(x, y, w, h, radius=h // 2)


def card_pixel(x, y, w, h):
    return rounded_rect_pixel(x, y, w, h, radius=12)


def panel_pixel(x, y, w, h):
    return rounded_rect_pixel(x, y, w, h, radius=18)


def button_pixel(x, y, w, h):
    return rounded_rect_pixel(x, y, w, h, radius=22)


def placeholder_icon(x, y, w, h):
    """Simple centered diamond shape for placeholder icons."""
    cx, cy = w // 2, h // 2
    dist = abs(x - cx) + abs(y - cy)
    max_dist = min(w, h) // 3
    if dist <= max_dist:
        return (255, 255, 255, 200)
    elif dist <= max_dist + 2:
        alpha = int(200 * max(0, (max_dist + 2 - dist) / 2))
        return (255, 255, 255, alpha)
    return (0, 0, 0, 0)


def save_png(filepath, width, height, pixel_fn):
    data = create_rgba_png(width, height, pixel_fn)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(data)
    print(f"  Created: {os.path.relpath(filepath, MEDIA_DIR)}")


def main():
    print("Generating ELITE IPTV DVR skin textures...")
    print(f"Output: {MEDIA_DIR}\n")

    # Core textures
    save_png(os.path.join(MEDIA_DIR, "white.png"), 4, 4, solid_white)
    save_png(os.path.join(MEDIA_DIR, "circle.png"), 64, 64, circle_pixel)
    save_png(os.path.join(MEDIA_DIR, "card_rounded.png"), 64, 64, card_pixel)
    save_png(os.path.join(MEDIA_DIR, "pill_rounded.png"), 64, 44, pill_pixel)
    save_png(os.path.join(MEDIA_DIR, "panel_rounded.png"), 64, 64, panel_pixel)
    save_png(os.path.join(MEDIA_DIR, "button_rounded.png"), 64, 44, button_pixel)

    # Small logo placeholder (will be replaced with real asset)
    save_png(os.path.join(MEDIA_DIR, "elite_logo_small.png"), 30, 30, placeholder_icon)

    # Placeholder icons for Home menu
    icon_names = ["guide", "livetv", "recordings", "timers", "search", "settings"]
    for name in icon_names:
        save_png(os.path.join(ICONS_DIR, f"{name}.png"), 48, 48, placeholder_icon)

    print(f"\nDone! Generated all required textures.")


if __name__ == "__main__":
    main()
