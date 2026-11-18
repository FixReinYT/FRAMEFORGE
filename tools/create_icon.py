from PIL import Image, ImageDraw
from pathlib import Path

S=512
im=Image.new("RGBA",(S,S),(16,10,29,255))
d=ImageDraw.Draw(im)
d.rounded_rectangle((18,18,494,494),radius=112,fill=(28,17,48),outline=(171,75,255),width=16)
# soft inner frame
d.rounded_rectangle((43,43,469,469),radius=88,outline=(94,47,145),width=5)
# panda ears and head
d.ellipse((112,62,236,190),fill=(8,7,16),outline=(184,112,255),width=8)
d.ellipse((276,62,400,190),fill=(8,7,16),outline=(184,112,255),width=8)
d.ellipse((126,90,386,328),fill=(248,245,252),outline=(184,112,255),width=8)
# eye patches and eyes
d.ellipse((145,170,246,267),fill=(12,10,19))
d.ellipse((266,170,367,267),fill=(12,10,19))
d.ellipse((179,199,215,235),fill=(55,224,128))
d.ellipse((297,199,333,235),fill=(173,89,255))
d.ellipse((190,204,204,218),fill="white")
d.ellipse((308,204,322,218),fill="white")
d.ellipse((240,264,272,286),fill=(15,11,21))
# clapper board across lower part
d.rounded_rectangle((82,306,430,423),radius=25,fill=(24,16,40),outline=(173,91,255),width=9)
d.polygon([(82,306),(430,306),(405,263),(57,263)],fill=(111,49,185),outline=(229,205,255))
for x in (105,190,275,360):
    d.polygon([(x,267),(x+40,267),(x+65,302),(x+25,302)],fill=(248,240,255))
# play symbol
d.polygon([(230,337),(230,397),(286,367)],fill=(197,128,255))
out=Path("assets"); out.mkdir(exist_ok=True)
im.save(out/"frameforge.ico",format="ICO",sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
im.save(out/"frameforge_icon.png")
