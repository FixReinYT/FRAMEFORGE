"""Non-destructive-to-source premium raster effects used by FRAMEFORGE PRO."""
from PIL import Image, ImageChops, ImageFilter, ImageOps


def apply_pro_effect(image, effect, intensity=50):
    intensity = max(1, min(100, int(intensity)))
    source = image.convert("RGBA")
    alpha = source.getchannel("A")
    amount = intensity / 100.0

    if effect == "glow":
        blurred = source.filter(ImageFilter.GaussianBlur(radius=max(2.0, intensity / 8.0)))
        blurred.putalpha(blurred.getchannel("A").point(lambda value: int(value * amount)))
        result = source.copy()
        result.alpha_composite(blurred)
        return result

    if effect == "duotone":
        gray = ImageOps.grayscale(source)
        result = ImageOps.colorize(gray, black="#15243b", white="#ffcf9c").convert("RGBA")
        result.putalpha(alpha)
        return result

    if effect == "film_grain":
        rgb = source.convert("RGB")
        noise = Image.effect_noise(source.size, max(8, intensity * 1.2))
        grain = ImageChops.add(rgb, Image.merge("RGB", (noise, noise, noise)),
                               scale=2.0, offset=-128)
        result = Image.blend(rgb, grain, 0.12 + amount * 0.28).convert("RGBA")
        result.putalpha(alpha)
        return result

    raise ValueError("Неизвестный фильтр FRAMEFORGE PRO.")
