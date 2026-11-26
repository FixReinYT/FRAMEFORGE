"""Original FRAMEFORGE mascot: FLiK, a folded-frame sprite.

The character is drawn from native vector primitives so it stays crisp at any UI
scale and does not depend on a downloaded raster illustration.
"""


def draw_mascot(canvas, x, y, size, mood="calm"):
    s = float(size)
    def p(a, b):
        return x + a * s, y + b * s

    # Soft hover shadow and asymmetric folded-frame body.
    canvas.create_oval(*p(.18, .86), *p(.84, .96), fill="#0b1420", outline="", tags=("mascot",))
    body = [p(.20,.30), p(.34,.10), p(.70,.12), p(.88,.34), p(.83,.68),
            p(.62,.88), p(.30,.84), p(.12,.61), p(.12,.43)]
    canvas.create_polygon(*[v for point in body for v in point], fill="#36c9b6",
                          outline="#a6fff0", width=max(1, int(s*.018)), smooth=True, tags=("mascot",))
    # Folded coral corner and small film-perforation tail.
    fold = [p(.69,.13), p(.84,.19), p(.88,.35), p(.74,.31)]
    canvas.create_polygon(*[v for point in fold for v in point], fill="#ff8d70",
                          outline="#ffe0b5", width=max(1, int(s*.012)), tags=("mascot",))
    canvas.create_rectangle(*p(.19,.68), *p(.29,.78), fill="#f4c56a", outline="", tags=("mascot",))
    canvas.create_rectangle(*p(.31,.74), *p(.39,.82), fill="#f4c56a", outline="", tags=("mascot",))
    # One antenna, deliberately offset to give the silhouette a recognizable profile.
    canvas.create_line(*p(.31,.16), *p(.22,.00), fill="#a6fff0", width=max(2,int(s*.025)),
                       capstyle="round", tags=("mascot",))
    canvas.create_oval(*p(.16,-.045), *p(.27,.065), fill="#ffb56f", outline="#fff0c9",
                       width=max(1,int(s*.012)), tags=("mascot",))
    # Unequal eyes and pupils.
    canvas.create_oval(*p(.28,.35), *p(.48,.57), fill="#122331", outline="#e8fff8",
                       width=max(1,int(s*.012)), tags=("mascot",))
    canvas.create_oval(*p(.56,.36), *p(.73,.55), fill="#122331", outline="#e8fff8",
                       width=max(1,int(s*.012)), tags=("mascot",))
    if mood == "wink":
        canvas.create_line(*p(.59,.46), *p(.70,.46), fill="#f7fffb", width=max(2,int(s*.025)),
                           capstyle="round", tags=("mascot",))
    else:
        look = .025 if mood == "thinking" else 0
        canvas.create_oval(*p(.35+look,.40), *p(.42+look,.50), fill="#f8ffff", outline="", tags=("mascot",))
        canvas.create_oval(*p(.62+look,.405), *p(.68+look,.49), fill="#f8ffff", outline="", tags=("mascot",))
    canvas.create_oval(*p(.24,.58), *p(.32,.64), fill="#ff987c", outline="", tags=("mascot",))
    canvas.create_oval(*p(.70,.58), *p(.78,.64), fill="#ff987c", outline="", tags=("mascot",))
    if mood == "oops":
        canvas.create_oval(*p(.47,.61), *p(.56,.70), outline="#173044", width=max(2,int(s*.018)), tags=("mascot",))
    elif mood == "thinking":
        canvas.create_line(*p(.46,.66), *p(.58,.64), fill="#173044", width=max(2,int(s*.018)), tags=("mascot",))
    else:
        canvas.create_arc(*p(.43,.57), *p(.60,.73), start=205, extent=130, style="arc",
                          outline="#173044", width=max(2,int(s*.018)), tags=("mascot",))
    return "mascot"


def draw_empty_state(canvas, x, y, width, height):
    size = max(44, min(118, min(width, height) * .22))
    draw_mascot(canvas, x + width/2 - size/2, y + height*.34 - size/2, size, "wave")
    canvas.create_text(x + width/2, y + height*.34 + size*.60,
                       text="Холст ждёт первого кадра", fill="#aebdd0",
                       font=("Segoe UI", 10, "bold"), tags=("mascot",))
