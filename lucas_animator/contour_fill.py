"""Contour-aware raster fill for FRAMEFORGE. Pillow-only implementation."""
from PIL import Image, ImageDraw, ImageFilter, ImageChops


def _barrier(source, threshold=90):
    """Detect visible ink on transparent or light-paper drawings."""
    rgba=source.convert("RGBA")
    alpha=rgba.getchannel("A")
    rgb=rgba.convert("RGB")
    gray=rgb.convert("L")
    # Transparent canvases: alpha is the contour; opaque paper: dark pixels are ink.
    lo,hi=alpha.getextrema()
    if lo < 255:
        return alpha.point(lambda a: 255 if a >= threshold else 0)
    return gray.point(lambda v: 255 if v < 225 else 0)


def flood_region(source, seed, gap=0, threshold=90):
    """Return selected region mask and original ink mask, without changing source."""
    w,h=source.size
    x,y=map(int,seed)
    if not (0<=x<w and 0<=y<h):
        return None,None
    ink=_barrier(source,threshold)
    gap=max(0,min(12,int(gap)))
    # Morphological closing is only used to determine the enclosed region.
    # It never paints or changes the line artwork.
    if gap:
        k=2*gap+1
        ink=ink.filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.MinFilter(k))
    barrier=ink.point(lambda p:255 if p else 0)
    if barrier.getpixel((x,y)):
        # Allow a click on the edge to reach the nearest open pixel.
        found=None
        for radius in range(1,9):
            for dx,dy in ((0,-radius),(radius,0),(0,radius),(-radius,0)):
                xx,yy=x+dx,y+dy
                if 0<=xx<w and 0<=yy<h and not barrier.getpixel((xx,yy)):
                    found=(xx,yy);break
            if found:break
        if found is None:return None,None
        x,y=found
    available=barrier.point(lambda p:0 if p else 255)
    ImageDraw.floodfill(available,(x,y),128,thresh=0)
    region=available.point(lambda p:255 if p==128 else 0)
    if not region.getbbox():return None,None
    return region,_barrier(source,threshold)


def apply_fill(target, source, seed, color, gap=0, threshold=90, separate=False):
    """Fill behind original ink, with local 1px underpaint and no external fringe.

    Returns a new RGBA image; callers decide when to record an undo snapshot.
    """
    region,ink=flood_region(source,seed,gap,threshold)
    if region is None:return None
    # Underpaint the antialiased inside edge by one pixel; preserve closed neighbors.
    enlarged=region.filter(ImageFilter.MaxFilter(3))
    # Only expand onto ink pixels, never into another open region.
    under=ImageChops.multiply(enlarged,ink)
    region=ImageChops.lighter(region,under)
    fill=Image.new("RGBA",target.size,color)
    if separate:
        out=target.copy()
        out.paste(fill,(0,0),region)
        return out
    # Same-layer fill: retain the contour and its fractional-alpha antialiasing.
    # For opaque paper, only restore detected ink, not the white background.
    out=target.copy()
    out.paste(fill,(0,0),region)
    original=target.convert("RGBA")
    stroke=original.copy()
    # Preserve semitransparent edge pixels around the detected ink.
    edge=ink.filter(ImageFilter.MaxFilter(3))
    stroke.putalpha(ImageChops.multiply(original.getchannel("A"),edge))
    out.paste(original,(0,0),edge)
    return out
