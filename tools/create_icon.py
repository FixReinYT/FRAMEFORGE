from PIL import Image, ImageDraw, ImageFont
import os
S=512
im=Image.new("RGBA",(S,S),(17,12,29,255))
d=ImageDraw.Draw(im)
# purple radial-ish background and rounded tile
for inset in range(0,70,2):
    col=(34+inset//4,17+inset//5,58+inset//3,255)
    d.rounded_rectangle((inset,inset,S-inset,S-inset),radius=105,outline=col,width=3)
d.rounded_rectangle((42,42,470,470),radius=92,fill=(29,20,48,255),outline=(157,85,245,255),width=14)
# clapperboard body
d.rounded_rectangle((105,170,407,390),radius=35,fill=(23,17,38,255),outline=(169,103,255,255),width=15)
d.polygon([(105,170),(407,170),(380,112),(78,112)],fill=(105,53,176,255),outline=(225,194,255,255))
for x in (105,185,265,345):
    d.polygon([(x,116),(x+38,116),(x+70,165),(x+32,165)],fill=(243,231,255,255))
# panda head
d.ellipse((158,55,245,145),fill=(7,7,15,255),outline=(190,137,255,255),width=7)
d.ellipse((268,55,355,145),fill=(7,7,15,255),outline=(190,137,255,255),width=7)
d.ellipse((170,72,344,230),fill=(247,243,251,255),outline=(190,137,255,255),width=6)
d.ellipse((183,125,245,187),fill=(10,9,18,255))
d.ellipse((269,125,331,187),fill=(10,9,18,255))
d.ellipse((203,145,224,166),fill=(64,221,137,255))
d.ellipse((291,145,312,166),fill=(164,91,255,255))
d.ellipse((247,185,268,201),fill=(15,12,22,255))
# FF monogram
try: font=ImageFont.truetype("arialbd.ttf",100)
except: font=ImageFont.load_default()
d.text((256,292),"FF",font=font,anchor="mm",fill=(245,232,255,255),stroke_width=2,stroke_fill=(150,75,235,255))
os.makedirs("assets",exist_ok=True)
im.save("assets/frameforge.ico",format="ICO",sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
im.save("assets/frameforge_icon.png")
