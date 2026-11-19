import unittest
from PIL import Image, ImageDraw
from lucas_animator.contour_fill import apply_fill, flood_region


class ContourFillTests(unittest.TestCase):
    def test_closed_regions_and_open_detail(self):
        line = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        d = ImageDraw.Draw(line)
        d.rectangle((8, 8, 70, 70), outline=(0, 0, 0, 255), width=3)
        d.ellipse((30, 30, 50, 45), outline=(0, 0, 0, 255), width=2)
        d.line((20, 18, 26, 25), fill=(0, 0, 0, 255), width=2)
        out = apply_fill(line, line, (15, 40), (240, 180, 120, 255))
        self.assertEqual(out.getpixel((15, 40))[:3], (240, 180, 120))
        self.assertEqual(out.getpixel((40, 38))[3], 0)
        self.assertEqual(out.getpixel((21, 19))[:3], (0, 0, 0))
        self.assertEqual(out.getpixel((0, 0))[3], 0)
        # An open interior stroke does not wall off the surrounding face.
        self.assertEqual(out.getpixel((15, 25))[:3], (240, 180, 120))

    def test_separate_layer_does_not_mutate_line_art_or_target(self):
        line = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
        ImageDraw.Draw(line).rectangle((10, 10, 50, 50), outline="black", width=2)
        before = line.tobytes()
        target = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
        target_before = target.tobytes()
        out = apply_fill(target, line, (25, 25), (255, 0, 0, 255), separate=True)
        self.assertEqual(line.tobytes(), before)
        self.assertEqual(target.tobytes(), target_before)
        self.assertEqual(out.getpixel((25, 25))[:3], (255, 0, 0))
        self.assertEqual(out.getpixel((0, 0))[3], 0)

    def test_small_gap_only_changes_region_calculation(self):
        line = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(line)
        d.line([(8, 8), (28, 8)], fill="black", width=2)
        d.line([(32, 8), (54, 8), (54, 54), (8, 54), (8, 8)], fill="black", width=2)
        before = line.tobytes()
        out = apply_fill(Image.new("RGBA", line.size), line, (25, 25),
                         (0, 255, 0, 255), gap=2, separate=True)
        self.assertEqual(line.tobytes(), before)
        self.assertEqual(out.getpixel((25, 25))[:3], (0, 255, 0))
        self.assertEqual(out.getpixel((0, 0))[3], 0)

    def test_antialiased_edge_is_underpainted_without_outside_fringe(self):
        line = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(line)
        d.ellipse((8, 8, 55, 55), outline=(0, 0, 0, 255), width=2)
        line = line.resize((128, 128), Image.Resampling.LANCZOS).resize(
            (64, 64), Image.Resampling.LANCZOS)
        before = line.tobytes()
        target = Image.new("RGBA", line.size, (0, 0, 0, 0))
        out = apply_fill(target, line, (32, 32), (0, 120, 255, 255), separate=True)
        self.assertEqual(line.tobytes(), before)
        self.assertEqual(out.getpixel((32, 32))[:3], (0, 120, 255))
        self.assertEqual(out.getpixel((2, 2))[3], 0)


if __name__ == "__main__":
    unittest.main()
