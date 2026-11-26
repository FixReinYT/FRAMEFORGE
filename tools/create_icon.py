from PIL import Image, ImageDraw
from pathlib import Path

S = 512
im = Image.new("RGBA", (S, S), (13, 22, 35, 255))
d = ImageDraw.Draw(im)
d.rounded_rectangle((16, 16, 496, 496), radius=112, fill=(20, 39, 57), outline=(54, 201, 182), width=14)
d.rounded_rectangle((40, 40, 472, 472), radius=92, outline=(49, 94, 112), width=5)
# FLiK: an asymmetrical folded-frame sprite, not a robot or an animal.
d.ellipse((112, 415, 402, 464), fill=(7, 16, 27, 180))
body = [(132, 177), (190, 89), (365, 98), (435, 183), (411, 355),
        (320, 431), (185, 410), (92, 295), (94, 230)]
d.polygon(body, fill=(54, 201, 182), outline=(166, 255, 240))
d.line(body + [body[0]], fill=(166, 255, 240), width=12, joint="curve")
d.polygon([(365, 98), (435, 150), (435, 183), (374, 170)], fill=(255, 141, 112), outline=(255, 224, 181))
d.line((190, 108, 145, 42), fill=(166, 255, 240), width=13)
d.ellipse((118, 18, 164, 64), fill=(255, 181, 111), outline=(255, 240, 201), width=6)
d.ellipse((157, 194, 252, 300), fill=(18, 35, 49), outline=(235, 255, 248), width=7)
d.ellipse((284, 198, 366, 285), fill=(18, 35, 49), outline=(235, 255, 248), width=7)
d.ellipse((190, 225, 226, 267), fill=(248, 255, 255))
d.ellipse((310, 225, 341, 259), fill=(248, 255, 255))
d.ellipse((200, 232, 216, 250), fill=(17, 39, 54))
d.ellipse((318, 231, 333, 247), fill=(17, 39, 54))
d.ellipse((123, 303, 158, 333), fill=(255, 152, 124))
d.ellipse((368, 300, 402, 330), fill=(255, 152, 124))
d.arc((225, 285, 310, 367), start=205, end=330, fill=(23, 48, 68), width=10)
d.rounded_rectangle((124, 354, 164, 394), radius=9, fill=(244, 197, 106))
d.rounded_rectangle((176, 386, 210, 420), radius=8, fill=(244, 197, 106))
out = Path("assets")
out.mkdir(exist_ok=True)
im.save(out / "frameforge.ico", format="ICO", sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
im.save(out / "frameforge_icon.png")
