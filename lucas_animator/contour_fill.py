"""Topology-aware flood fill for FRAMEFORGE's raster animation editor.

The source image is read-only. The region mask is temporary; optional gap closing
is never written back to the line-art layer.
"""
from collections import deque
from PIL import Image, ImageChops, ImageFilter


def _ink_masks(source, threshold=32):
    """Return a binary contour barrier and a soft mask retaining AA ink opacity."""
    rgba = source.convert("RGBA")
    alpha = rgba.getchannel("A")
    gray = rgba.convert("RGB").convert("L")
    a = alpha.tobytes()
    g = gray.tobytes()
    # Dark, sufficiently opaque pixels form barriers. This works for both
    # transparent canvases and white-paper backgrounds.
    strength = bytes((aa * (255 - lum)) // 255 for aa, lum in zip(a, g))
    soft = Image.frombytes("L", source.size, strength)
    barrier = soft.point(lambda p: 255 if p >= threshold else 0)
    return barrier, soft


def _close_temporary_gaps(barrier, gap):
    gap = max(0, min(12, int(gap)))
    if not gap:
        return barrier
    # Closing is exclusively for region detection. The source artwork is untouched.
    size = gap * 2 + 1
    return barrier.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))


def flood_region(source, seed, gap=0, threshold=32):
    """Return (selected-region mask, soft ink mask), or (None, None)."""
    width, height = source.size
    x, y = int(seed[0]), int(seed[1])
    if not (0 <= x < width and 0 <= y < height):
        return None, None

    original_barrier, soft_ink = _ink_masks(source, threshold)
    barrier = _close_temporary_gaps(original_barrier, gap)
    barrier_bytes = barrier.tobytes()
    start = y * width + x

    # A click on a contour pixel is redirected to the closest non-contour pixel.
    if barrier_bytes[start]:
        candidate = None
        for radius in range(1, 5):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < width and 0 <= yy < height:
                        pos = yy * width + xx
                        if not barrier_bytes[pos]:
                            candidate = pos
                            break
                if candidate is not None:
                    break
            if candidate is not None:
                break
        if candidate is None:
            return None, None
        start = candidate

    # Scanline-independent 4-connected flood. Open internal strokes do not
    # divide an area unless they actually form a closed boundary.
    visited = bytearray(width * height)
    queue = deque([start])
    visited[start] = 1
    while queue:
        pos = queue.popleft()
        px = pos % width
        py = pos // width
        if px and not visited[pos - 1] and not barrier_bytes[pos - 1]:
            visited[pos - 1] = 1
            queue.append(pos - 1)
        if px + 1 < width and not visited[pos + 1] and not barrier_bytes[pos + 1]:
            visited[pos + 1] = 1
            queue.append(pos + 1)
        if py and not visited[pos - width] and not barrier_bytes[pos - width]:
            visited[pos - width] = 1
            queue.append(pos - width)
        if py + 1 < height and not visited[pos + width] and not barrier_bytes[pos + width]:
            visited[pos + width] = 1
            queue.append(pos + width)

    mask = Image.frombytes("L", source.size,
                           bytes(255 if value else 0 for value in visited))
    if mask.getbbox() is None:
        return None, None
    return mask, soft_ink


def _underpaint_mask(region, soft_ink):
    """Extend fill only beneath the antialiased inner edge of the contour."""
    expanded = region.filter(ImageFilter.MaxFilter(3))
    # Only pixels belonging to the soft contour can be added. This prevents
    # dilation from escaping the outline and creating an exterior color fringe.
    return ImageChops.lighter(region, ImageChops.multiply(expanded, soft_ink))


def apply_fill(target, source, seed, color, gap=0, threshold=32, separate=False):
    """Return a new layer image after one atomic fill operation.

    separate=True writes paint to the active layer using source as read-only line art.
    Otherwise the fill and preserved line art are composited on the active layer.
    """
    region, soft_ink = flood_region(source, seed, gap=gap, threshold=threshold)
    if region is None:
        return None

    paint_mask = _underpaint_mask(region, soft_ink)
    fill = Image.new("RGBA", target.size, tuple(color))

    if separate:
        # The active paint layer receives only fill. Source line-art is never edited.
        output = target.convert("RGBA").copy()
        output.paste(fill, (0, 0), paint_mask)
        return output

    # Same-layer mode: apply fill, then alpha-composite the original antialiased
    # ink back over it. Non-ink artwork outside the chosen region is retained.
    original = target.convert("RGBA")
    output = original.copy()
    output.paste(fill, (0, 0), paint_mask)
    ink_layer = original.copy()
    ink_layer.putalpha(soft_ink)
    output.alpha_composite(ink_layer)
    return output
