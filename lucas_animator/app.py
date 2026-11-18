import json, os, sys, tkinter as tk, zipfile, subprocess
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
from PIL import Image, ImageDraw, ImageTk, ImageSequence

APP_NAME = "FRAMEFORGE"
VERSION = "0.8.2"
BG, PANEL, ALT, BORDER = "#171b24", "#202633", "#252d3b", "#354052"
TEXT, MUTED, ACCENT = "#e8edf5", "#9aa8bb", "#4f9cf9"

PRESETS = {
    "Квадрат 512 × 512": (512, 512),
    "Квадрат 1024 × 1024": (1024, 1024),
    "HD 1280 × 720": (1280, 720),
    "Full HD 1920 × 1080": (1920, 1080),
    "4K 3840 × 2160": (3840, 2160),
    "Портрет 1080 × 1920": (1080, 1920),
    "A4 2480 × 3508": (2480, 3508),
    "Пользовательский размер": None,
}

class FrameForge:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} {VERSION}")
        self.root.geometry("1500x920")
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.minsize(900, 600)
        self.root.resizable(True, True)
        self.w, self.h = 1280, 720
        self.frames = [Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))]
        self.layer_frames = [[
            {"name":"Фон","image":Image.new("RGBA",(self.w,self.h),(0,0,0,0)),"visible":True},
            {"name":"Рисунок","image":Image.new("RGBA",(self.w,self.h),(0,0,0,0)),"visible":True}
        ]]
        self.active_layer = 1
        user_cfg=os.path.join(os.getenv("APPDATA",os.path.expanduser("~")),"FRAMEFORGE","settings.json")
        try:
            with open(user_cfg,encoding="utf-8") as cfg_file: self.user_settings=json.load(cfg_file)
        except Exception: self.user_settings={}
        self.index, self.fps = 0, tk.IntVar(value=max(1,min(60,int(self.user_settings.get("default_fps",12)))))
        self.size, self.opacity = tk.IntVar(value=8), tk.IntVar(value=100)
        self.color, self.tool = "#202633", tk.StringVar(value="brush")
        self.onion, self.playing = tk.BooleanVar(value=bool(self.user_settings.get("onion_skin",True))), False
        self.project, self.last, self.photo = None, None, None
        self.origin, self.status = (0, 0, 1), tk.StringVar(value="Готово")
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.fullscreen = False
        self.pan_anchor = None
        self.undo_stack, self.redo_stack = [], []
        self.stroke_before, self.shape_start = None, None
        self.stroke_points = []
        self.checker_cache = None
        self.canvas_image_id = None
        self.preview_ids = []
        self.setup_style()
        self.build()
        self.bind_shortcuts()
        self.refresh()
        self.update_tool_buttons()
        self.render()

    def setup_style(self):
        self.root.configure(bg=BG)
        try:
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(base, "assets", "frameforge_icon.png")
            self._window_icon = tk.PhotoImage(file=icon_path)
            self.root.iconphoto(True, self._window_icon)
        except Exception:
            pass
        s = ttk.Style(); s.theme_use("clam")
        s.configure(".", font=("Segoe UI", 10))
        s.configure("TLabel", background=PANEL, foreground=TEXT)
        s.configure("Section.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9, "bold"))
        s.configure("TButton", background=ALT, foreground=TEXT, borderwidth=0, padding=(9, 7))
        s.map("TButton", background=[("active", "#35445a")])
        s.configure("Accent.TButton", background=ACCENT, foreground="white", padding=(10, 8))
        s.configure("Tool.TRadiobutton", background=PANEL, foreground=TEXT, padding=(7, 5))
        s.map("Tool.TRadiobutton", background=[("selected", "#263e5c"), ("active", ALT)])
        s.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        s.configure("TSpinbox", fieldbackground=ALT, foreground=TEXT)
        s.configure("Horizontal.TScale", background=PANEL, troughcolor=ALT)

    def panel(self, parent, width=None):
        f = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER, width=width)
        if width: f.pack_propagate(False)
        return f

    def section(self, parent, title):
        ttk.Label(parent, text=title.upper(), style="Section.TLabel").pack(anchor="w", padx=12, pady=(13, 6))

    def build(self):
        header = tk.Frame(self.root, bg="#11151d", height=60); header.pack(fill="x"); header.pack_propagate(False)
        brand = tk.Frame(header, bg="#11151d"); brand.pack(side="left", padx=16)
        tk.Label(brand, text="FRAME", bg="#11151d", fg=TEXT, font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(brand, text="FORGE", bg="#11151d", fg=ACCENT, font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(brand, text="  0.8.2", bg="#11151d", fg=MUTED).pack(side="left", padx=6)
        ttk.Button(header,text="⌂ Главное меню",command=self.return_to_menu).pack(side="left",padx=4,pady=12)
        for label, fn in [("Новый", self.new), ("Открыть", self.open), ("Вставить изображение", self.insert_image), ("Сохранить", self.save),
                          ("Экспорт", self.export_menu)]:
            ttk.Button(header, text=label, command=fn).pack(side="left", padx=4, pady=12)
        ttk.Button(header, text="↶ Отмена", command=self.undo).pack(side="left", padx=(18, 3), pady=12)
        ttk.Button(header, text="↷ Повтор", command=self.redo).pack(side="left", padx=3, pady=12)
        ttk.Button(header, text="⛶ Во весь экран (F11)", command=self.toggle_fullscreen).pack(side="right", padx=8, pady=12)
        tk.Label(header, text="2D ANIMATION WORKSPACE", bg="#11151d", fg="#718096").pack(side="right", padx=16)

        work = tk.Frame(self.root, bg=BG); work.pack(fill="both", expand=True, padx=9, pady=8)
        left_outer = self.panel(work, 210); left_outer.pack(side="left", fill="y")
        left_outer.pack_propagate(False)
        left_canvas = tk.Canvas(left_outer,bg=PANEL,highlightthickness=0,width=190)
        left_scroll = ttk.Scrollbar(left_outer,orient="vertical",command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scroll.set)
        left_scroll.pack(side="right",fill="y")
        left_canvas.pack(side="left",fill="both",expand=True)
        left = tk.Frame(left_canvas,bg=PANEL)
        left_window = left_canvas.create_window((0,0),window=left,anchor="nw")
        def _sync_left_scroll(_event=None):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
            left_canvas.itemconfigure(left_window,width=left_canvas.winfo_width())
        left.bind("<Configure>",_sync_left_scroll)
        left_canvas.bind("<Configure>",_sync_left_scroll)
        def _left_wheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)),"units")
            return "break"
        left_canvas.bind("<MouseWheel>",_left_wheel)
        left_canvas.bind("<Button-4>",lambda e:left_canvas.yview_scroll(-1,"units"))
        left_canvas.bind("<Button-5>",lambda e:left_canvas.yview_scroll(1,"units"))
        self.section(left, "Инструменты")
        tools = [("✎ Карандаш","pencil"),("● Кисть","brush"),("◌ Аэрограф","airbrush"),
                 ("▱ Ластик","eraser"),("／ Линия","line"),("□ Прямоуг.","rect"),
                 ("○ Эллипс","ellipse"),("▰ Прямоуг. заливка","filled_rect"),("● Эллипс заливка","filled_ellipse"),("△ Треугол.","triangle"),("▨ Заливка","fill"),("⌖ Пипетка","eyedropper")]
        toolgrid=tk.Frame(left,bg=PANEL); toolgrid.pack(fill="x",padx=6)
        self.tool_buttons={}
        for n,(label,value) in enumerate(tools):
            cell=tk.Frame(toolgrid,bg=ALT,highlightthickness=1,highlightbackground=BORDER)
            cell.grid(row=n//2,column=n%2,sticky="nsew",padx=2,pady=2)
            icon=tk.Canvas(cell,width=38,height=30,bg=ALT,highlightthickness=0)
            icon.pack(pady=(3,0))
            self.draw_tool_icon(icon,value)
            tk.Label(cell,text=label.split(" ",1)[-1],bg=ALT,fg=TEXT,font=("Segoe UI",8)).pack(pady=(0,4))
            for widget in (cell,icon):
                widget.bind("<Button-1>",lambda e,v=value:self.choose_tool(v))
            self.tool_buttons[value]=cell
        toolgrid.grid_columnconfigure(0,weight=1); toolgrid.grid_columnconfigure(1,weight=1)
        self.update_tool_buttons()
        self.section(left, "Параметры")
        row = tk.Frame(left, bg=PANEL); row.pack(fill="x", padx=12, pady=4)
        tk.Label(row, text="Цвет", bg=PANEL, fg=MUTED).pack(side="left")
        self.swatch = tk.Button(row, bg=self.color, width=5, relief="flat", command=self.pick)
        self.swatch.pack(side="right", ipady=6)
        self.section(left, "Палитра • цветовые группы")
        palette = ["#111318","#343941","#626a76","#9ba3af","#dce1e8","#ffffff",
                   "#5b2028","#a8323e","#e14b59","#ff8290","#f5b4ba","#fce4e6",
                   "#64351d","#a85b2b","#d88945","#f2b66d","#f6d7a8","#fff0d8",
                   "#66501c","#a58a2b","#d6bd45","#f1dc75","#f7edb2","#fff9dc",
                   "#24523b","#347b55","#4ca879","#82c99c","#b7e4c7","#e3f5e9",
                   "#1d5260","#287f91","#42b5c9","#83d4df","#bcebf0","#e7f8fa",
                   "#263c70","#365da6","#5884d8","#8eafea","#c3d4f5","#eaf0fc",
                   "#49316f","#704ca5","#966bd0","#bd9ce8","#d9c5f3","#f1eafa",
                   "#7b315d","#b34d87","#dc78b0","#eda4cc","#f5cce1","#fceaf3"]
        pal = tk.Frame(left, bg=PANEL); pal.pack(fill="x", padx=9, pady=3)
        for i, col in enumerate(palette):
            b=tk.Button(pal,bg=col,width=1,height=1,relief="flat",bd=0,
                        activebackground=col,command=lambda value=col:self.set_color(value))
            b.grid(row=i//6,column=i%6,padx=2,pady=2,sticky="nsew")
        for col in range(6): pal.grid_columnconfigure(col,weight=1)
        ttk.Button(left,text="Выбрать цвет…",command=self.pick).pack(fill="x",padx=10,pady=3)
        ttk.Button(left,text="Отразить слой ↔",command=self.flip_layer_horizontal).pack(fill="x",padx=10,pady=2)
        ttk.Button(left,text="Отразить слой ↕",command=self.flip_layer_vertical).pack(fill="x",padx=10,pady=2)
        tk.Label(left, text="Размер кисти", bg=PANEL, fg=MUTED).pack(anchor="w", padx=12, pady=(8, 0))
        self.size_label = tk.Label(left, text="8 px", bg=PANEL, fg=TEXT); self.size_label.pack(anchor="e", padx=12)
        ttk.Scale(left, from_=1, to=100, variable=self.size, command=self.size_changed).pack(fill="x", padx=12)
        tk.Label(left, text="Непрозрачность", bg=PANEL, fg=MUTED).pack(anchor="w", padx=12, pady=(8, 0))
        self.opacity_label = tk.Label(left, text="100%", bg=PANEL, fg=TEXT); self.opacity_label.pack(anchor="e", padx=12)
        ttk.Scale(left, from_=1, to=100, variable=self.opacity, command=self.opacity_changed).pack(fill="x", padx=12)
        ttk.Checkbutton(left, text="Луковая шелуха", variable=self.onion, command=self.render).pack(anchor="w", padx=12, pady=10)

        center = tk.Frame(work, bg=BG); center.pack(side="left", fill="both", expand=True, padx=8)
        head = tk.Frame(center, bg=PANEL, height=38); head.pack(fill="x"); head.pack_propagate(False)
        tk.Label(head, text="ХОЛСТ", bg=PANEL, fg=TEXT).pack(side="left", padx=12)
        self.canvas_info = tk.Label(head, text="1280 × 720", bg=PANEL, fg=MUTED); self.canvas_info.pack(side="right", padx=12)
        shell = tk.Frame(center, bg="#11151d", padx=10, pady=10); shell.pack(fill="both", expand=True, pady=(5, 0))
        self.canvas = tk.Canvas(shell, bg="#171c25", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.canvas.bind("<Button-1>", self.start)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<MouseWheel>", self.zoom_wheel)
        self.canvas.bind("<Button-4>", lambda e:self.zoom_at(e.x,e.y,1.12))
        self.canvas.bind("<Button-5>", lambda e:self.zoom_at(e.x,e.y,1/1.12))
        self.canvas.bind("<ButtonPress-2>", self.pan_start)
        self.canvas.bind("<B2-Motion>", self.pan_drag)

        right = self.panel(work, 205); right.pack(side="right", fill="y")
        self.section(right, "Анимация • таймлайн")
        tk.Label(right, text="Кадров в секунду", bg=PANEL, fg=MUTED).pack(anchor="w", padx=12)
        ttk.Spinbox(right, from_=1, to=60, textvariable=self.fps, width=7).pack(anchor="w", padx=12, pady=5)
        self.playbtn = ttk.Button(right, text="▶ Воспроизвести", style="Accent.TButton", command=self.play)
        self.playbtn.pack(fill="x", padx=10, pady=8)
        self.section(right, "Кадры")
        for label, fn in [("+ Добавить", self.add), ("▣ Дублировать", self.duplicate), ("− Удалить", self.delete)]:
            ttk.Button(right, text=label, command=fn).pack(fill="x", padx=10, pady=3)
        nav = tk.Frame(right, bg=PANEL); nav.pack(fill="x", padx=10, pady=8)
        ttk.Button(nav, text="←", command=lambda: self.select(self.index-1)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(nav, text="→", command=lambda: self.select(self.index+1)).pack(side="left", expand=True, fill="x", padx=2)
        self.counter = tk.Label(right, text="КАДР 1 / 1", bg=PANEL, fg=TEXT, font=("Segoe UI", 11, "bold")); self.counter.pack(pady=10)
        self.section(right, "Слои • порядок наложения")
        layerbar=tk.Frame(right,bg=PANEL); layerbar.pack(fill="x",padx=8)
        ttk.Button(layerbar,text="+",width=3,command=self.add_layer).pack(side="left",expand=True,fill="x",padx=1)
        ttk.Button(layerbar,text="−",width=3,command=self.delete_layer).pack(side="left",expand=True,fill="x",padx=1)
        ttk.Button(layerbar,text="↑",width=3,command=lambda:self.move_layer(-1)).pack(side="left",expand=True,fill="x",padx=1)
        ttk.Button(layerbar,text="↓",width=3,command=lambda:self.move_layer(1)).pack(side="left",expand=True,fill="x",padx=1)
        ttk.Button(layerbar,text="◉",width=3,command=self.toggle_layer_visibility).pack(side="left",expand=True,fill="x",padx=1)
        self.layer_list=tk.Listbox(right,height=7,bg=ALT,fg=TEXT,selectbackground="#365a83",relief="flat",highlightthickness=0,exportselection=False)
        self.layer_list.pack(fill="x",padx=9,pady=5)
        self.layer_list.bind("<<ListboxSelect>>",self.select_layer)
        ttk.Button(right,text="Залить фон цветом",command=self.fill_background).pack(fill="x",padx=9,pady=3)
        self.section(right, "История")
        ttk.Button(right, text="↶ Отменить  Ctrl+Z", command=self.undo).pack(fill="x", padx=10, pady=3)
        ttk.Button(right, text="↷ Вернуть  Ctrl+U", command=self.redo).pack(fill="x", padx=10, pady=3)

        timeline = self.panel(self.root); timeline.pack(fill="x", padx=9, pady=(0, 7))
        th = tk.Frame(timeline, bg=PANEL); th.pack(fill="x")
        tk.Label(th, text="ТАЙМЛАЙН", bg=PANEL, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(side="left", padx=12, pady=8)
        self.timeline_hint = tk.Label(th, text="", bg=PANEL, fg=MUTED); self.timeline_hint.pack(side="right", padx=12)
        self.timeline = tk.Frame(timeline, bg="#1a202b"); self.timeline.pack(fill="x", padx=6, pady=(0, 6))
        footer = tk.Frame(self.root, bg="#11151d", height=25); footer.pack(fill="x", side="bottom"); footer.pack_propagate(False)
        tk.Label(footer, textvariable=self.status, bg="#11151d", fg=MUTED).pack(side="left", padx=10)
        tk.Label(footer, text="FRAMEFORGE • THELUCASSDEN", bg="#11151d", fg="#65748a").pack(side="right", padx=10)

    def choose_tool(self,value):
        self.tool.set(value)
        self.update_tool_buttons()

    def update_tool_buttons(self):
        for name,widget in getattr(self,"tool_buttons",{}).items():
            active=name==self.tool.get()
            widget.configure(bg="#263e5c" if active else ALT,
                             highlightbackground=ACCENT if active else BORDER)
            for child in widget.winfo_children():
                child.configure(bg="#263e5c" if active else ALT)

    def draw_tool_icon(self,canvas,name):
        fg="#e8edf5"; accent="#72b7ff"
        def line(points,width=2,color=fg):
            for a,b in zip(points,points[1:]):
                canvas.create_line(*a,*b,fill=color,width=width,capstyle="round",joinstyle="round")
        if name=="pencil":
            line([(8,23),(25,6),(30,11),(13,28),(7,29),(8,23)],3)
        elif name=="brush":
            line([(8,25),(17,16),(24,7)],4,accent); canvas.create_oval(5,22,12,29,outline=fg,width=2)
        elif name=="airbrush":
            canvas.create_oval(7,5,25,23,outline=fg,width=2); canvas.create_line(17,23,17,29,fill=accent,width=3)
            for x,y in [(5,8),(29,7),(29,19),(7,27)]:canvas.create_oval(x,y,x+2,y+2,fill=accent,outline=accent)
        elif name=="eraser":
            canvas.create_polygon(7,20,19,6,31,17,19,29,fill="#e58ab4",outline=fg,width=2)
            canvas.create_line(14,25,25,13,fill=fg,width=1)
        elif name=="line": line([(6,25),(31,5)],3,accent)
        elif name=="rect": canvas.create_rectangle(7,6,31,26,outline=fg,width=2)
        elif name=="ellipse": canvas.create_oval(7,5,31,27,outline=fg,width=2)
        elif name=="triangle": canvas.create_polygon(19,5,32,27,6,27,outline=fg,fill="",width=2)
        elif name=="filled_rect": canvas.create_rectangle(7,6,31,26,outline=accent,fill=accent,width=1)
        elif name=="filled_ellipse": canvas.create_oval(7,5,31,27,outline=accent,fill=accent,width=1)
        elif name=="fill":
            canvas.create_polygon(8,17,18,6,29,17,18,28,fill="#72b7ff",outline=fg,width=1)
            canvas.create_arc(19,18,31,30,start=180,extent=180,outline=accent,width=2)
        elif name=="eyedropper":
            line([(9,25),(25,9),(29,13),(13,29),(9,25)],3)
            canvas.create_line(20,8,26,14,fill=accent,width=3)

    def bind_shortcuts(self):
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-u>", lambda e: self.redo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-s>", lambda e: self.save())
        self.root.bind("<Control-o>", lambda e: self.open())
        self.root.bind("<Control-n>", lambda e: self.new())
        self.root.bind("<space>", lambda e: self.play())
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self.exit_fullscreen())

    def size_changed(self, v): self.size_label.config(text=f"{int(float(v))} px")
    def opacity_changed(self, v): self.opacity_label.config(text=f"{int(float(v))}%")
    def pick(self):
        import colorsys
        win=tk.Toplevel(self.root)
        win.title("Цветовой круг")
        win.configure(bg=PANEL)
        win.resizable(False,False)
        win.transient(self.root)
        win.grab_set()
        try:
            rgb=tuple(int(self.color[i:i+2],16)/255 for i in (1,3,5))
            h,s,v=colorsys.rgb_to_hsv(*rgb)
        except Exception: h,s,v=0,1,1
        state={"h":h,"s":s,"v":v,"color":self.color}
        wheel=tk.Canvas(win,width=360,height=330,bg=PANEL,highlightthickness=0)
        wheel.grid(row=0,column=0,rowspan=4,padx=12,pady=12)
        preview=tk.Label(win,text="Текущий цвет",bg=self.color,fg="#ffffff",width=15,height=3)
        preview.grid(row=0,column=1,padx=12,pady=(25,8))
        hexvar=tk.StringVar(value=self.color.upper())
        ttk.Entry(win,textvariable=hexvar,width=14).grid(row=1,column=1,padx=12,pady=5)
        def render():
            import math
            wheel.delete("all")
            cx=cy=165
            # Raster SV square: saturation on X, value on Y
            square=Image.new("RGB",(200,200))
            pix=square.load()
            for yy in range(200):
                vv=1-yy/199
                for xx in range(200):
                    ss=xx/199
                    rr,gg,bb=colorsys.hsv_to_rgb(state["h"],ss,vv)
                    pix[xx,yy]=(int(rr*255),int(gg*255),int(bb*255))
            self._color_square=ImageTk.PhotoImage(square)
            wheel.create_image(65,65,image=self._color_square,anchor="nw")
            # Ring segments, drawn as short colored arcs
            for deg in range(0,360,2):
                rgb=colorsys.hsv_to_rgb(deg/360,1,1)
                col="#%02x%02x%02x"%tuple(int(k*255) for k in rgb)
                wheel.create_arc(17,17,313,313,start=deg,extent=2.5,style="arc",outline=col,width=16)
            sx=65+state["s"]*200
            sy=65+(1-state["v"])*200
            wheel.create_oval(sx-6,sy-6,sx+6,sy+6,outline="#ffffff",width=2)
            wheel.create_oval(sx-3,sy-3,sx+3,sy+3,outline="#10131a",width=1)
            angle=math.radians(state["h"]*360)
            hx=165+148*math.cos(angle); hy=165-148*math.sin(angle)
            wheel.create_oval(hx-7,hy-7,hx+7,hy+7,outline="#ffffff",width=2)
            rr,gg,bb=colorsys.hsv_to_rgb(state["h"],state["s"],state["v"])
            state["color"]="#%02x%02x%02x"%(int(rr*255),int(gg*255),int(bb*255))
            preview.configure(bg=state["color"])
            hexvar.set(state["color"].upper())
        def choose(event):
            import math
            dx=event.x-165; dy=165-event.y
            radius=math.hypot(dx,dy)
            if 135<=radius<=160:
                state["h"]=(math.atan2(dy,dx)%(2*math.pi))/(2*math.pi)
            elif 65<=event.x<=265 and 65<=event.y<=265:
                state["s"]=(event.x-65)/200
                state["v"]=1-(event.y-65)/200
            else:return
            render()
        wheel.bind("<Button-1>",choose)
        wheel.bind("<B1-Motion>",choose)
        def accept():
            color=hexvar.get().strip()
            if len(color)==7 and color.startswith("#"):
                self.set_color(color); win.destroy()
            else: messagebox.showerror(APP_NAME,"Формат цвета: #RRGGBB",parent=win)
        ttk.Button(win,text="Применить цвет",style="Accent.TButton",command=accept).grid(row=2,column=1,padx=12,pady=8)
        ttk.Button(win,text="Отмена",command=win.destroy).grid(row=3,column=1,padx=12,pady=(0,15))
        render()

    def set_color(self, color):
        self.color = color
        self.swatch.config(bg=color)

    def active_image(self):
        return self.layer_frames[self.index][self.active_layer]["image"]

    def compose_frame(self, index):
        result=Image.new("RGBA",(self.w,self.h),(0,0,0,0))
        for layer in self.layer_frames[index]:
            if layer["visible"]:
                result.alpha_composite(layer["image"])
        self.frames[index]=result
        return result

    def refresh_layers(self):
        if not hasattr(self,"layer_list"): return
        self.layer_list.delete(0,"end")
        for layer in self.layer_frames[self.index]:
            self.layer_list.insert("end",("● " if layer["visible"] else "○ ")+layer["name"])
        self.active_layer=max(0,min(self.active_layer,len(self.layer_frames[self.index])-1))
        self.layer_list.selection_set(self.active_layer)

    def select_layer(self,event=None):
        selection=self.layer_list.curselection()
        if selection: self.active_layer=selection[0]

    def toggle_layer_visibility(self):
        layer=self.layer_frames[self.index][self.active_layer]
        layer["visible"]=not layer["visible"]
        self.compose_frame(self.index); self.refresh_layers(); self.render()

    def add_layer(self):
        self.layer_frames[self.index].append({"name":f"Слой {len(self.layer_frames[self.index])+1}","image":Image.new("RGBA",(self.w,self.h),(0,0,0,0)),"visible":True})
        self.active_layer=len(self.layer_frames[self.index])-1
        self.compose_frame(self.index); self.refresh_layers(); self.render()

    def delete_layer(self):
        layers=self.layer_frames[self.index]
        if len(layers)<=1:
            messagebox.showinfo(APP_NAME,"Нельзя удалить последний слой."); return
        layers.pop(self.active_layer); self.active_layer=max(0,self.active_layer-1)
        self.compose_frame(self.index); self.refresh_layers(); self.render()

    def move_layer(self,delta):
        layers=self.layer_frames[self.index]; target=self.active_layer+delta
        if not 0<=target<len(layers): return
        layers[self.active_layer],layers[target]=layers[target],layers[self.active_layer]
        self.active_layer=target; self.compose_frame(self.index); self.refresh_layers(); self.render()

    def flip_layer_horizontal(self):
        self.snapshot()
        self.active_image().transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        self.layer_frames[self.index][self.active_layer]["image"]=self.active_image().transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        self.compose_frame(self.index);self.render();self.status.set("Слой отражён по горизонтали")

    def flip_layer_vertical(self):
        self.snapshot()
        self.layer_frames[self.index][self.active_layer]["image"]=self.active_image().transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        self.compose_frame(self.index);self.render();self.status.set("Слой отражён по вертикали")

    def fill_background(self):
        bg=self.layer_frames[self.index][0]["image"]
        bg.paste(self.rgba(),(0,0,self.w,self.h))
        self.compose_frame(self.index); self.render()


    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def exit_fullscreen(self):
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes("-fullscreen", False)

    def pan_start(self, event):
        self.pan_anchor = (event.x, event.y, self.pan_x, self.pan_y)

    def pan_drag(self, event):
        if self.pan_anchor is None:
            return
        ax, ay, px, py = self.pan_anchor
        self.pan_x = px + event.x - ax
        self.pan_y = py + event.y - ay
        self.render()

    def zoom_wheel(self, event):
        self.zoom_at(event.x, event.y, 1.12 if event.delta > 0 else 1 / 1.12)

    def zoom_at(self, sx, sy, factor):
        old_scale, old_x, old_y = self.origin
        image_x = (sx - old_x) / old_scale
        image_y = (sy - old_y) / old_scale
        self.zoom = max(0.10, min(8.0, self.zoom * factor))
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        fit = min((cw - 30) / self.w, (ch - 30) / self.h)
        new_scale = fit * self.zoom
        self.pan_x = sx - image_x * new_scale - (cw - self.w * new_scale) / 2
        self.pan_y = sy - image_y * new_scale - (ch - self.h * new_scale) / 2
        self.render()

    def insert_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                       ("Все файлы", "*.*")])
        if not path:
            return
        try:
            with Image.open(path) as source:
                source.seek(0)
                layer = source.convert("RGBA")
            if layer.width > self.w or layer.height > self.h:
                layer.thumbnail((self.w, self.h), Image.Resampling.LANCZOS)
            self.snapshot()
            x = (self.w - layer.width) // 2
            y = (self.h - layer.height) // 2
            self.active_image().alpha_composite(layer, (x, y))
            self.compose_frame(self.index)
            self.render()
            self.status.set("Изображение вставлено в текущий кадр")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Не удалось вставить изображение: {exc}")

    def snapshot(self, all_frames=False):
        # A paint stroke only snapshots its active frame, not every frame in the project.
        if all_frames:
            layers=[[{"name":l["name"],"image":l["image"].copy(),"visible":l["visible"]} for l in frame] for frame in self.layer_frames]
            state=("all",self.index,layers)
        else:
            layers=[{"name":l["name"],"image":l["image"].copy(),"visible":l["visible"]} for l in self.layer_frames[self.index]]
            state=("frame",self.index,layers)
        self.undo_stack.append(state)
        if len(self.undo_stack) > 40: self.undo_stack.pop(0)
        self.redo_stack.clear()

    def restore(self, stack_from, stack_to):
        if not stack_from: return
        current=("all",self.index,[[{"name":l["name"],"image":l["image"].copy(),"visible":l["visible"]} for l in frame] for frame in self.layer_frames])
        state = stack_from.pop()
        stack_to.append(current)
        kind, idx, payload = state
        if kind=="all":
            self.index,self.layer_frames=idx,payload
            self.frames=[self.compose_frame(i) for i in range(len(self.layer_frames))]
        else:
            self.index=min(idx,len(self.layer_frames)-1)
            self.layer_frames[self.index]=payload
            self.compose_frame(self.index)
        self.refresh(); self.refresh_layers(); self.render(); self.status.set("История действий обновлена")

    def undo(self): self.restore(self.undo_stack, self.redo_stack)
    def redo(self): self.restore(self.redo_stack, self.undo_stack)

    def geometry(self):
        cw, ch = max(1,self.canvas.winfo_width()), max(1,self.canvas.winfo_height())
        scale = min((cw-30)/self.w, (ch-30)/self.h) * self.zoom
        return scale, (cw-self.w*scale)/2 + self.pan_x, (ch-self.h*scale)/2 + self.pan_y

    def on_canvas_resize(self, event=None):
        self.checker_cache = None
        self.render()

    def render(self):
        if not hasattr(self, "canvas"): return
        self.canvas.delete("all")
        self.preview_ids = []
        s,x,y = self.geometry(); ww,hh = max(1,int(self.w*s)),max(1,int(self.h*s))
        # Cache the checkerboard: do not create hundreds of Tk rectangles per redraw.
        if self.checker_cache is None or self.checker_cache.size != (ww,hh):
            tile=max(8,int(16*s))
            checker=Image.new("RGB",(ww,hh),"#c7ced8")
            cd=ImageDraw.Draw(checker)
            for yy in range(0,hh,tile):
                for xx in range(0,ww,tile):
                    if ((xx//tile)+(yy//tile))%2==0:
                        cd.rectangle((xx,yy,min(ww-1,xx+tile-1),min(hh-1,yy+tile-1)),fill="#dce1e8")
            self.checker_cache=checker
        base=self.checker_cache.convert("RGBA")
        im=self.compose_frame(self.index).copy()
        if self.onion.get() and self.index>0:
            prev=self.frames[self.index-1]
            tint=Image.new("RGBA",prev.size,(255,75,95,0))
            tint.putalpha(prev.getchannel("A").point(lambda a:int(a*.22)))
            tint.alpha_composite(im); im=tint
        base.alpha_composite(im.resize((ww,hh),Image.Resampling.BILINEAR))
        self.photo=ImageTk.PhotoImage(base.convert("RGB"))
        self.canvas.create_image(x,y,image=self.photo,anchor="nw")
        self.canvas.create_rectangle(x,y,x+ww,y+hh,outline="#718096")
        self.origin=(x,y,s)

    def coords(self,e):
        x,y,s=self.origin
        return max(0,min(self.w-1,int((e.x-x)/s))),max(0,min(self.h-1,int((e.y-y)/s)))

    def rgba(self):
        rgb=tuple(bytes.fromhex(self.color.lstrip("#")))
        return (*rgb, int(255*self.opacity.get()/100))

    def start(self,e):
        if self.playing:return
        p=self.coords(e); tool=self.tool.get()
        if tool=="eyedropper":
            col=self.active_image().getpixel(p)
            if col[3]: self.color="#%02x%02x%02x"%col[:3]; self.swatch.config(bg=self.color)
            return
        if tool=="fill":
            self.snapshot()
            ImageDraw.floodfill(self.active_image(),p,self.rgba(),thresh=20)
            self.compose_frame(self.index); self.render(); return
        self.snapshot()
        self.last=p; self.shape_start=p; self.stroke_points=[p]
        # Draw live preview with Tk primitives. The full bitmap is not rescaled on every mouse event.
        cx,cy=self.to_canvas(p)
        self.preview_ids=[self.canvas.create_oval(cx-1,cy-1,cx+1,cy+1,fill=self.color,outline=self.color)]
        if tool in ("line","rect","ellipse","triangle","filled_rect","filled_ellipse"):
            self.preview_ids=[]
        self.status.set("Рисование...")

    def to_canvas(self,p):
        x,y,s=self.origin
        return x+p[0]*s, y+p[1]*s

    def drag(self,e):
        if self.last is None or self.playing:return
        p=self.coords(e); tool=self.tool.get()
        a=self.to_canvas(self.last); b=self.to_canvas(p)
        if tool in ("pencil","brush","airbrush","eraser"):
            color="#171c25" if tool=="eraser" else self.color
            width=max(1,int(self.size.get()*self.origin[2]))
            item=self.canvas.create_line(*a,*b,fill=color,width=width,
                                         capstyle=tk.ROUND,joinstyle=tk.ROUND)
            self.preview_ids.append(item)
        elif tool in ("line","rect","ellipse","triangle","filled_rect","filled_ellipse"):
            for item in self.preview_ids:self.canvas.delete(item)
            self.preview_ids=[]
            a=self.to_canvas(self.shape_start)
            if tool=="line":
                item=self.canvas.create_line(*a,*b,fill=self.color,width=max(1,int(self.size.get()*self.origin[2])))
            elif tool=="rect":
                item=self.canvas.create_rectangle(*a,*b,outline=self.color,width=max(1,int(self.size.get()*self.origin[2])))
            elif tool=="triangle":
                mid=(a[0]+b[0])/2
                item=self.canvas.create_polygon(mid,a[1],b[0],b[1],a[0],b[1],outline=self.color,fill="",width=max(1,int(self.size.get()*self.origin[2])))
            elif tool=="filled_rect": item=self.canvas.create_rectangle(*a,*b,outline=self.color,fill=self.color)
            elif tool=="filled_ellipse": item=self.canvas.create_oval(*a,*b,outline=self.color,fill=self.color)
            else:
                item=self.canvas.create_oval(*a,*b,outline=self.color,width=max(1,int(self.size.get()*self.origin[2])))
            self.preview_ids=[item]
        self.stroke_points.append(p)
        self.last=p

    def release(self,e):
        if self.last is None:return
        p=self.coords(e); tool=self.tool.get()
        points=self.stroke_points or [p]
        im=self.active_image()
        color=(0,0,0,0) if tool=="eraser" else self.rgba()
        d=ImageDraw.Draw(im)
        width=max(1,self.size.get())
        if tool in ("pencil","brush","eraser","airbrush"):
            # Commit the collected path once, instead of repainting/resampling the canvas on each event.
            if len(points)==1:
                q=points[0]; r=0 if tool=="pencil" else width/2
                d.ellipse((q[0]-r,q[1]-r,q[0]+r,q[1]+r),fill=color)
            else:
                d.line(points,fill=color,width=1 if tool=="pencil" else width,joint="curve")
                if tool!="pencil":
                    r=width/2
                    for q in (points[0],points[-1]):
                        d.ellipse((q[0]-r,q[1]-r,q[0]+r,q[1]+r),fill=color)
        elif tool in ("line","rect","ellipse","triangle","filled_rect","filled_ellipse"):
            a=self.shape_start
            if tool=="line":d.line([a,p],fill=color,width=width)
            elif tool=="rect":d.rectangle([a,p],outline=color,width=width)
            elif tool=="triangle":
                mid=(a[0]+p[0])//2
                d.line([(mid,a[1]),p,(a[0],p[1]),(mid,a[1])],fill=color,width=width)
            elif tool=="filled_rect":d.rectangle([a,p],fill=color)
            elif tool=="filled_ellipse":d.ellipse([a,p],fill=color)
            else:d.ellipse([a,p],outline=color,width=width)
        for item in self.preview_ids:self.canvas.delete(item)
        self.preview_ids=[]; self.last=None; self.stroke_points=[]
        self.compose_frame(self.index)
        self.render()
        self.status.set("Изменения внесены")

    def refresh(self):
        for w in self.timeline.winfo_children(): w.destroy()
        for i in range(len(self.frames)):
            sel=i==self.index
            tk.Button(self.timeline,text=f"КАДР\n{i+1}",command=lambda n=i:self.select(n),
                bg="#284d75" if sel else ALT,fg="white",relief="flat",bd=0,width=8,height=3,
                highlightthickness=1,highlightbackground=ACCENT if sel else BORDER).pack(side="left",padx=3,pady=5)
        self.counter.config(text=f"КАДР {self.index+1} / {len(self.frames)}")
        self.refresh_layers()
        self.timeline_hint.config(text=f"{len(self.frames)} кадров • {self.fps.get()} FPS")

    def select(self,n):
        self.index=max(0,min(len(self.frames)-1,n)); self.refresh(); self.render()

    def add(self):
        self.snapshot(all_frames=True); self.frames.insert(self.index+1,Image.new("RGBA",(self.w,self.h),(0,0,0,0))); self.layer_frames.insert(self.index+1,[{"name":l["name"],"image":Image.new("RGBA",(self.w,self.h),(0,0,0,0)),"visible":l["visible"]} for l in self.layer_frames[self.index]]); self.select(self.index+1)
    def duplicate(self):
        self.snapshot(all_frames=True); self.frames.insert(self.index+1,self.frames[self.index].copy()); self.layer_frames.insert(self.index+1,[{"name":l["name"],"image":l["image"].copy(),"visible":l["visible"]} for l in self.layer_frames[self.index]]); self.select(self.index+1)
    def delete(self):
        self.snapshot()
        if len(self.frames)==1:
            self.layer_frames[0]=[{"name":"Фон","image":Image.new("RGBA",(self.w,self.h),(0,0,0,0)),"visible":True},{"name":"Рисунок","image":Image.new("RGBA",(self.w,self.h),(0,0,0,0)),"visible":True}]
            self.active_layer=1; self.frames[0]=self.compose_frame(0)
        else:self.frames.pop(self.index); self.layer_frames.pop(self.index); self.index=min(self.index,len(self.frames)-1)
        self.refresh(); self.render()

    def play(self):
        self.playing=not self.playing
        self.playbtn.config(text="■ Стоп" if self.playing else "▶ Воспроизвести")
        if self.playing:self.tick()
    def tick(self):
        if not self.playing:return
        self.index=(self.index+1)%len(self.frames); self.refresh(); self.render()
        self.root.after(max(1,int(1000/max(1,self.fps.get()))),self.tick)

    def choose_canvas(self):
        win=tk.Toplevel(self.root); win.title("Новый холст"); win.configure(bg=PANEL); win.resizable(False,False); win.grab_set()
        tk.Label(win,text="Создание нового холста",bg=PANEL,fg=TEXT,font=("Segoe UI",14,"bold")).pack(padx=20,pady=14)
        preset=tk.StringVar(value="Full HD 1920 × 1080")
        ttk.Combobox(win,textvariable=preset,values=list(PRESETS),state="readonly",width=28).pack(padx=20,pady=6)
        row=tk.Frame(win,bg=PANEL); row.pack(padx=20,pady=8)
        wv,hv=tk.StringVar(value="1920"),tk.StringVar(value="1080")
        for label,var in [("Ширина",wv),("Высота",hv)]:
            col=tk.Frame(row,bg=PANEL); col.pack(side="left",padx=6)
            tk.Label(col,text=label,bg=PANEL,fg=MUTED).pack()
            ttk.Entry(col,textvariable=var,width=10).pack()
        bgv=tk.StringVar(value="Прозрачный")
        ttk.Combobox(win,textvariable=bgv,values=["Прозрачный","Белый"],state="readonly",width=25).pack(pady=7)
        def changed(*_):
            dims=PRESETS.get(preset.get())
            if dims: wv.set(str(dims[0])); hv.set(str(dims[1]))
        preset.trace_add("write",changed)
        result={}
        def accept():
            try:
                ww,hh=int(wv.get()),int(hv.get())
                if not (1<=ww<=8192 and 1<=hh<=8192): raise ValueError()
                result.update(w=ww,h=hh,bg=(255,255,255,255) if bgv.get()=="Белый" else (0,0,0,0)); win.destroy()
            except ValueError: messagebox.showerror(APP_NAME,"Размеры должны быть от 1 до 8192 пикселей.",parent=win)
        ttk.Button(win,text="Создать холст",style="Accent.TButton",command=accept).pack(pady=14)
        self.root.wait_window(win)
        return result or None

    def new(self):
        cfg=self.choose_canvas()
        if not cfg:return
        self.w,self.h=cfg["w"],cfg["h"]
        self.zoom=1.0; self.pan_x=0; self.pan_y=0
        self.snapshot(all_frames=True); self.layer_frames=[[{"name":"Фон","image":Image.new("RGBA",(self.w,self.h),cfg["bg"]),"visible":True},{"name":"Рисунок","image":Image.new("RGBA",(self.w,self.h),(0,0,0,0)),"visible":True}]]; self.active_layer=1; self.frames=[self.compose_frame(0)]
        self.index=0; self.project=None; self.undo_stack.clear(); self.redo_stack.clear()
        self.canvas_info.config(text=f"{self.w} × {self.h}"); self.refresh(); self.render()
        self.refresh_layers(); self.status.set("Создан новый холст")

    def save(self):
        path=self.project or filedialog.asksaveasfilename(defaultextension=".ffg",filetypes=[("FRAMEFORGE project","*.ffg")])
        if not path:return
        import io
        manifest={"format":"FRAMEFORGE","version":VERSION,"width":self.w,"height":self.h,"fps":self.fps.get(),"active_layer":self.active_layer,"frames":[]}
        try:
            with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as archive:
                for fi,frame in enumerate(self.layer_frames):
                    frame_data={"layers":[]}
                    for li,layer in enumerate(frame):
                        name=f"frames/{fi:05d}/layer_{li:03d}.png"
                        buf=io.BytesIO(); layer["image"].save(buf,format="PNG")
                        archive.writestr(name,buf.getvalue())
                        frame_data["layers"].append({"name":layer["name"],"visible":layer["visible"],"file":name})
                    manifest["frames"].append(frame_data)
                archive.writestr("project.json",json.dumps(manifest,ensure_ascii=False,indent=2))
            self.project=path; self.status.set("Проект сохранён вместе со слоями")
        except Exception as exc:
            messagebox.showerror(APP_NAME,f"Не удалось сохранить проект: {exc}")

    def open(self,path=None):
        if path is None:
            path=filedialog.askopenfilename(filetypes=[("FRAMEFORGE project","*.ffg"),("Legacy project","*.json")])
        if not path:return
        try:
            import io
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path,"r") as archive:
                    data=json.loads(archive.read("project.json").decode("utf-8"))
                    self.w,self.h=data["width"],data["height"]
                    if data["frames"] and isinstance(data["frames"][0],dict):
                        layer_frames=[]
                        for frame in data["frames"]:
                            layers=[]
                            for layer in frame["layers"]:
                                image=Image.open(io.BytesIO(archive.read(layer["file"]))).convert("RGBA")
                                layers.append({"name":layer["name"],"visible":layer.get("visible",True),"image":image})
                            layer_frames.append(layers)
                        self.layer_frames=layer_frames
                        self.frames=[self.compose_frame(i) for i in range(len(layer_frames))]
                        self.active_layer=min(data.get("active_layer",0),len(layer_frames[0])-1)
                    else:
                        self.frames=[Image.open(io.BytesIO(archive.read(name))).convert("RGBA") for name in data["frames"]]
                        self.layer_frames=[[{"name":"Рисунок","image":im.copy(),"visible":True}] for im in self.frames]
                        self.active_layer=0
            else:
                with open(path,encoding="utf-8") as f:data=json.load(f)
                folder=os.path.join(os.path.dirname(path),data["folder"])
                self.frames=[Image.open(os.path.join(folder,n)).convert("RGBA") for n in data["frames"]]
                self.layer_frames=[[{"name":"Рисунок (старый проект)","image":im.copy(),"visible":True}] for im in self.frames]
                self.active_layer=0
            self.w,self.h=data["width"],data["height"]
            self.fps.set(data.get("fps",12)); self.index=0; self.project=path
            self.zoom=1.0; self.pan_x=0; self.pan_y=0
            self.undo_stack.clear(); self.redo_stack.clear()
            self.canvas_info.config(text=f"{self.w} × {self.h}")
            self.refresh(); self.refresh_layers(); self.render()
            self.status.set("Проект загружен")
        except Exception as exc:
            messagebox.showerror(APP_NAME,f"Не удалось открыть проект: {exc}")

    def export_menu(self):
        win=tk.Toplevel(self.root); win.title("Экспорт"); win.configure(bg=PANEL); win.resizable(False,False)
        tk.Label(win,text="Экспорт проекта",bg=PANEL,fg=TEXT,font=("Segoe UI",13,"bold")).pack(padx=25,pady=12)
        for label,fn in [("Экспорт всей анимации в MP4 — H.264",self.export_mp4),("Экспорт всей анимации в WebM — VP9",self.export_webm),("Текущий кадр — PNG",self.png),("Анимация — GIF",self.gif),
                         ("Последовательность PNG — ZIP",self.png_sequence),("Sprite Sheet — PNG",self.sprite_sheet)]:
            ttk.Button(win,text=label,command=lambda f=fn:(win.destroy(),f())).pack(fill="x",padx=18,pady=4)

    def export_video(self, extension, codec, extra_args):
        path=filedialog.asksaveasfilename(
            parent=self.root,defaultextension="."+extension,
            filetypes=[(extension.upper()+" video","*."+extension)])
        if not path:return
        proc=None
        try:
            import imageio_ffmpeg
            ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
            frames=[self.compose_frame(i).copy() for i in range(len(self.layer_frames))]
            if not frames:raise RuntimeError("В проекте нет кадров для экспорта.")
            fps=max(1,min(60,int(self.fps.get())))
            width=self.w+(self.w%2); height=self.h+(self.h%2)
            cmd=[ffmpeg,"-hide_banner","-loglevel","error","-y",
                 "-f","rawvideo","-pixel_format","rgb24",
                 "-video_size",f"{width}x{height}","-framerate",str(fps),
                 "-i","pipe:0","-an","-c:v",codec]
            cmd.extend(extra_args)
            cmd.extend(["-pix_fmt","yuv420p","-r",str(fps),
                        "-frames:v",str(len(frames)),"-movflags","+faststart",path])
            proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            for frame in frames:
                rgba=frame.convert("RGBA")
                if rgba.size!=(self.w,self.h):
                    rgba=rgba.resize((self.w,self.h),Image.Resampling.LANCZOS)
                rgb=Image.new("RGBA",(self.w,self.h),(255,255,255,255))
                rgb.alpha_composite(rgba)
                if width!=self.w or height!=self.h:
                    padded=Image.new("RGBA",(width,height),(255,255,255,255))
                    padded.alpha_composite(rgb,(0,0))
                    rgb=padded
                proc.stdin.write(rgb.convert("RGB").tobytes())
            proc.stdin.close()
            code=proc.wait()
            if code!=0:raise RuntimeError("FFmpeg не смог собрать видео. Проверьте свободное место и повторите экспорт.")
            if not os.path.isfile(path) or os.path.getsize(path)==0:
                raise RuntimeError("Видео не было создано: выходной файл пуст.")
            self.status.set("Видео экспортировано: "+os.path.basename(path))
            messagebox.showinfo(APP_NAME,f"Анимация экспортирована в {extension.upper()}.\\nКадров: {len(frames)} · FPS: {fps}",parent=self.root)
        except Exception as exc:
            if proc is not None and proc.poll() is None:
                try:
                    if proc.stdin:proc.stdin.close()
                except Exception:pass
                proc.kill();proc.wait()
            messagebox.showerror(APP_NAME,"Не удалось экспортировать видео.\\n"+str(exc),parent=self.root)

    def export_mp4(self):
        self.export_video("mp4","libx264",["-crf","18","-movflags","+faststart"])

    def export_webm(self):
        self.export_video("webm","libvpx-vp9",["-crf","30","-b:v","0"])

    def return_to_menu(self):
        self.playing=False
        for widget in self.root.winfo_children():widget.destroy()
        MainMenu(self.root)

    def png(self):
        p=filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG","*.png")])
        if p:self.frames[self.index].save(p)
    def gif(self):
        p=filedialog.asksaveasfilename(defaultextension=".gif",filetypes=[("GIF","*.gif")])
        if p:
            ims=[im.convert("RGBA") for im in self.frames]
            ims[0].save(p,save_all=True,append_images=ims[1:],duration=max(1,int(1000/max(1,self.fps.get()))),loop=0,disposal=2)
    def png_sequence(self):
        p=filedialog.asksaveasfilename(defaultextension=".zip",filetypes=[("ZIP archive","*.zip")])
        if p:
            with zipfile.ZipFile(p,"w",zipfile.ZIP_DEFLATED) as z:
                for i,im in enumerate(self.frames):
                    import io
                    b=io.BytesIO(); im.save(b,format="PNG"); z.writestr(f"frame_{i+1:05d}.png",b.getvalue())
    def sprite_sheet(self):
        cols=max(1,int(simpledialog.askinteger(APP_NAME,"Количество колонок:",initialvalue=5,minvalue=1,maxvalue=50) or 5))
        rows=(len(self.frames)+cols-1)//cols
        if self.w*cols>16000 or self.h*rows>16000:
            messagebox.showerror(APP_NAME,"Sprite Sheet слишком большой. Уменьшите число колонок."); return
        sheet=Image.new("RGBA",(self.w*cols,self.h*rows),(0,0,0,0))
        for i,im in enumerate(self.frames): sheet.alpha_composite(im,((i%cols)*self.w,(i//cols)*self.h))
        p=filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG","*.png")])
        if p:sheet.save(p)


class MainMenu:
    def __init__(self,root):
        self.root=root
        root.protocol("WM_DELETE_WINDOW",self.close_app)
        root.title(f"{APP_NAME} {VERSION} — главное меню")
        root.geometry("1120x760");root.minsize(900,650);root.configure(bg="#0d111b")
        try:
            base=getattr(sys,"_MEIPASS",os.path.dirname(os.path.abspath(__file__)))
            self.icon=tk.PhotoImage(file=os.path.join(base,"assets","frameforge_icon.png"));root.iconphoto(True,self.icon)
        except Exception:self.icon=None
        self.settings_path=os.path.join(os.getenv("APPDATA",os.path.expanduser("~")),"FRAMEFORGE","settings.json")
        self.settings=self.load_settings()
        self.build()

    def load_settings(self):
        defaults={"default_fps":12,"onion_skin":True,"preview_quality":"balanced",
                  "default_canvas":"HD 1280 × 720","confirm_exit":True,"show_tips":True,"recent":[]}
        try:
            with open(self.settings_path,encoding="utf-8") as f:defaults.update(json.load(f))
        except Exception:pass
        return defaults

    def save_settings(self):
        os.makedirs(os.path.dirname(self.settings_path),exist_ok=True)
        with open(self.settings_path,"w",encoding="utf-8") as f:json.dump(self.settings,f,ensure_ascii=False,indent=2)

    def close_app(self):
        if self.settings.get("confirm_exit",True):
            if not messagebox.askyesno(APP_NAME,"Закрыть FRAMEFORGE?",parent=self.root):return
        self.root.destroy()

    def build(self):
        for w in self.root.winfo_children():w.destroy()
        shell=tk.Frame(self.root,bg="#0d111b");shell.pack(fill="both",expand=True)
        top=tk.Frame(shell,bg="#111827",height=76);top.pack(fill="x");top.pack_propagate(False)
        brand=tk.Frame(top,bg="#111827");brand.pack(side="left",padx=28)
        tk.Label(brand,text="▣",bg="#111827",fg="#80b8ff",font=("Segoe UI",25,"bold")).pack(side="left",padx=(0,10))
        tk.Label(brand,text="FRAME",bg="#111827",fg="#f4f7ff",font=("Segoe UI",20,"bold")).pack(side="left")
        tk.Label(brand,text="FORGE",bg="#111827",fg="#75aaff",font=("Segoe UI",20,"bold")).pack(side="left")
        tk.Label(top,text="2D ANIMATION STUDIO",bg="#111827",fg="#71829e",font=("Segoe UI",9,"bold")).pack(side="right",padx=28)
        content=tk.Frame(shell,bg="#0d111b");content.pack(fill="both",expand=True,padx=30,pady=25)
        hero=tk.Frame(content,bg="#17243a",highlightthickness=1,highlightbackground="#2b4164")
        hero.pack(fill="x",pady=(0,20))
        left=tk.Frame(hero,bg="#17243a");left.pack(side="left",fill="both",expand=True,padx=28,pady=24)
        tk.Label(left,text="ТВОЯ МАСТЕРСКАЯ АНИМАЦИИ",bg="#17243a",fg="#7fb6ff",font=("Segoe UI",9,"bold")).pack(anchor="w")
        tk.Label(left,text="От первого штриха\nдо ожившей истории.",bg="#17243a",fg="#f4f7ff",font=("Segoe UI",25,"bold"),justify="left").pack(anchor="w",pady=(8,5))
        tk.Label(left,text="Рисуй. Создавай кадры. Задавай движение.",bg="#17243a",fg="#aab8cd",font=("Segoe UI",11)).pack(anchor="w")
        tk.Label(hero,text="FF",bg="#17243a",fg="#294a77",font=("Segoe UI",64,"bold")).pack(side="right",padx=42)
        area=tk.Frame(content,bg="#0d111b");area.pack(fill="both",expand=True)
        main=tk.Frame(area,bg="#0d111b");main.pack(side="left",fill="both",expand=True)
        side=tk.Frame(area,bg="#141c2a",width=300,highlightthickness=1,highlightbackground="#29374c")
        side.pack(side="right",fill="y",padx=(20,0));side.pack_propagate(False)
        tk.Label(main,text="НАЧАТЬ РАБОТУ",bg="#0d111b",fg="#8194b1",font=("Segoe UI",9,"bold")).pack(anchor="w",pady=(0,10))
        self.menu_button(main,"＋","Новый проект","Создай холст и начни рисовать",self.new_project,True)
        self.menu_button(main,"▧","Открыть проект","Продолжить работу с файлом .FFG",self.open_project)
        self.menu_button(main,"▶","Обучение","Короткий интерактивный гид по созданию 2D-анимации",self.tutorial)
        tk.Label(main,text="ПЕРСОНАЛИЗАЦИЯ",bg="#0d111b",fg="#8194b1",font=("Segoe UI",9,"bold")).pack(anchor="w",pady=(19,10))
        row=tk.Frame(main,bg="#0d111b");row.pack(fill="x")
        self.small_button(row,"⚙  Настройки",self.preferences)
        self.small_button(row,"✦  Авторы",self.about)
        tk.Label(side,text="НЕДАВНИЕ ПРОЕКТЫ",bg="#141c2a",fg="#83b8ff",font=("Segoe UI",9,"bold")).pack(anchor="w",padx=18,pady=(20,10))
        recent=self.settings.get("recent",[])
        if recent:
            for p in recent[:6]:
                if os.path.isfile(p):
                    b=tk.Button(side,text="▣  "+os.path.basename(p),anchor="w",command=lambda path=p:self.open_project(path),
                        bg="#1d293b",fg="#e7edf8",activebackground="#2b4160",activeforeground="white",
                        relief="flat",bd=0,padx=12,pady=10,cursor="hand2")
                    b.pack(fill="x",padx=12,pady=3)
        else:
            tk.Label(side,text="Пока пусто.\nТвои проекты появятся здесь.",bg="#141c2a",fg="#7889a2",
                     justify="left",font=("Segoe UI",10)).pack(anchor="w",padx=18,pady=8)
        tk.Frame(side,bg="#29374c",height=1).pack(fill="x",padx=14,pady=14)
        tk.Label(side,text="СОВЕТ ДНЯ",bg="#141c2a",fg="#83b8ff",font=("Segoe UI",9,"bold")).pack(anchor="w",padx=18)
        tips=["Сначала сделай ключевые позы — промежуточные кадры добавишь позже.",
              "Разделяй фон и персонажа по слоям: так проще вносить правки.",
              "Короткая анимация на 12 FPS — отличный способ начать.",
              "Дублируй кадр, а затем слегка меняй позу для плавного движения."]
        tip=tips[sum(map(ord,__import__("datetime").date.today().isoformat()))%len(tips)] if self.settings.get("show_tips",True) else "Подсказки отключены в настройках."
        tk.Label(side,text=tip,bg="#141c2a",fg="#aab8cd",wraplength=250,justify="left").pack(anchor="w",padx=18,pady=(7,18))
        footer=tk.Frame(shell,bg="#0a0e16",height=32);footer.pack(fill="x",side="bottom");footer.pack_propagate(False)
        tk.Label(footer,text=f"FRAMEFORGE {VERSION}  •  THELUCASSDEN",bg="#0a0e16",fg="#66758d",font=("Segoe UI",8,"bold")).pack(side="left",padx=18)
        tk.Label(footer,text="DRAW  •  ANIMATE  •  CREATE",bg="#0a0e16",fg="#66758d",font=("Segoe UI",8)).pack(side="right",padx=18)

    def menu_button(self,parent,icon,title,subtitle,command,primary=False):
        bg="#244b7b" if primary else "#172233";edge="#4c85c4" if primary else "#2c3c53"
        box=tk.Frame(parent,bg=bg,highlightthickness=1,highlightbackground=edge)
        box.pack(fill="x",pady=5)
        btn=tk.Button(box,text=icon,bg=bg,fg="#8fc1ff",activebackground=bg,activeforeground="#ffffff",
                      font=("Segoe UI",19,"bold"),relief="flat",bd=0,width=3,cursor="hand2",command=command)
        btn.pack(side="left",padx=(10,0),pady=9)
        textf=tk.Frame(box,bg=bg);textf.pack(side="left",fill="both",expand=True,padx=8,pady=8)
        tk.Button(textf,text=title,anchor="w",bg=bg,fg="#f0f4fc",activebackground=bg,activeforeground="#ffffff",
                  font=("Segoe UI",12,"bold"),relief="flat",bd=0,cursor="hand2",command=command).pack(fill="x")
        tk.Label(textf,text=subtitle,anchor="w",bg=bg,fg="#a1b0c5",font=("Segoe UI",9)).pack(fill="x")

    def small_button(self,parent,label,command):
        tk.Button(parent,text=label,command=command,bg="#1a2638",fg="#dce8fa",activebackground="#2b4160",
                  activeforeground="white",relief="flat",bd=0,font=("Segoe UI",10,"bold"),
                  padx=18,pady=13,cursor="hand2").pack(side="left",fill="x",expand=True,padx=(0,8))

    def new_project(self):
        for w in self.root.winfo_children():w.destroy()
        FrameForge(self.root)

    def open_project(self,path=None):
        if path is None:path=filedialog.askopenfilename(parent=self.root,filetypes=[("FRAMEFORGE project","*.ffg")])
        if not path:return
        for w in self.root.winfo_children():w.destroy()
        app=FrameForge(self.root);app.open(path)
        self.settings["recent"]=[path]+[p for p in self.settings.get("recent",[]) if p!=path]
        self.settings["recent"]=self.settings["recent"][:8];self.save_settings()

    def tutorial(self):
        win=tk.Toplevel(self.root);win.title("FRAMEFORGE — основы 2D-анимации")
        win.geometry("760x620");win.minsize(650,540);win.configure(bg="#111827");win.transient(self.root)
        pages=[
          ("01  СОЗДАЙ ХОЛСТ","Нажми «Новый проект». Выбери разрешение: для первых упражнений подойдёт HD 1280 × 720. Прозрачный фон удобен для персонажей, белый — для набросков.",
           "Упражнение: создай холст 512 × 512 и нарисуй простой круг — это будет голова персонажа."),
          ("02  ОСВОЙ ИНСТРУМЕНТЫ","Кисть и карандаш рисуют линии, ластик стирает, аэрограф добавляет мягкие пятна. Размер и непрозрачность настраиваются в прокручиваемой левой панели.",
           "Совет: используй крупную кисть для силуэта, маленькую — для глаз и деталей."),
          ("03  РАБОТАЙ СО СЛОЯМИ","Разделяй фон, персонажа и детали по разным слоям. Меняй порядок слоёв и видимость, чтобы редактировать элементы независимо.",
           "Упражнение: создай слой «Фон» и слой «Персонаж». Нарисуй фон отдельно от героя."),
          ("04  СОЗДАЙ ДВИЖЕНИЕ","Добавь кадр кнопкой «Добавить» или продублируй предыдущий. На новом кадре немного измени положение объекта. Повторяй, чтобы получить последовательность движения.",
           "Начни с 2–3 кадров: круг слева, круг посередине, круг справа — получится простое перемещение."),
          ("05  ВКЛЮЧИ ONION SKIN","Луковая шелуха помогает видеть соседние кадры и сравнивать положения рисунка. Настрой FPS: 12 кадров/с — удобная стартовая скорость для рисованной анимации.",
           "Если движение дёргается, добавь промежуточные кадры или измени расстояние между ключевыми позами."),
          ("06  ПРОСМОТР И ЭКСПОРТ","Нажми «Воспроизвести», чтобы проверить результат. Сохрани исходник в .FFG. Через «Экспорт» можно вывести GIF, MP4, WebM, PNG, PNG Sequence или Sprite Sheet.",
           "Важно: .FFG — редактируемый проект, MP4/GIF — готовое видео для просмотра и публикации.")
        ]
        state={"page":0}
        top=tk.Frame(win,bg="#111827");top.pack(fill="x",padx=24,pady=(22,10))
        tk.Label(top,text="FRAMEFORGE ACADEMY",bg="#111827",fg="#78b5ff",font=("Segoe UI",9,"bold")).pack(anchor="w")
        title=tk.Label(top,text="",bg="#111827",fg="#f2f6ff",font=("Segoe UI",20,"bold"));title.pack(anchor="w",pady=(7,0))
        progress=tk.Label(top,text="",bg="#111827",fg="#8293ad",font=("Segoe UI",9));progress.pack(anchor="w",pady=5)
        body=tk.Frame(win,bg="#1a2638",highlightthickness=1,highlightbackground="#30445f");body.pack(fill="both",expand=True,padx=24,pady=12)
        desc=tk.Label(body,text="",bg="#1a2638",fg="#e1e9f6",font=("Segoe UI",12),wraplength=660,justify="left",anchor="nw")
        desc.pack(fill="both",expand=True,padx=24,pady=(24,12))
        task=tk.Label(body,text="",bg="#243651",fg="#a9ceff",font=("Segoe UI",10),wraplength=650,justify="left",anchor="w")
        task.pack(fill="x",padx=18,pady=(0,18),ipady=12)
        nav=tk.Frame(win,bg="#111827");nav.pack(fill="x",padx=24,pady=(0,20))
        back=tk.Button(nav,text="← Назад",command=lambda:move(-1),bg="#202e43",fg="white",relief="flat",padx=18,pady=10)
        back.pack(side="left")
        close=tk.Button(nav,text="Закрыть",command=win.destroy,bg="#202e43",fg="white",relief="flat",padx=18,pady=10);close.pack(side="right")
        nxt=tk.Button(nav,text="Далее →",command=lambda:move(1),bg="#326bb0",fg="white",relief="flat",padx=20,pady=10);nxt.pack(side="right",padx=8)
        def move(delta):
            state["page"]=max(0,min(len(pages)-1,state["page"]+delta))
            a,b,d=pages[state["page"]]
            title.config(text=a);desc.config(text=b);task.config(text=d)
            progress.config(text=f"Урок {state['page']+1} из {len(pages)}")
            back.config(state="normal" if state["page"] else "disabled")
            nxt.config(text="Готово ✓" if state["page"]==len(pages)-1 else "Далее →",
                       command=win.destroy if state["page"]==len(pages)-1 else lambda:move(1))
        move(0)

    def preferences(self):
        win=tk.Toplevel(self.root);win.title("Настройки FRAMEFORGE");win.geometry("570x570")
        win.configure(bg="#111827");win.resizable(False,False);win.transient(self.root);win.grab_set()
        tk.Label(win,text="Настройки FRAMEFORGE",bg="#111827",fg="#f1f5fc",font=("Segoe UI",20,"bold")).pack(anchor="w",padx=24,pady=(22,4))
        tk.Label(win,text="Настрой рабочую среду под свой процесс.",bg="#111827",fg="#91a1b8",font=("Segoe UI",10)).pack(anchor="w",padx=24,pady=(0,14))
        body=tk.Frame(win,bg="#182336");body.pack(fill="both",expand=True,padx=20,pady=8)
        fps=tk.IntVar(value=int(self.settings.get("default_fps",12)))
        onion=tk.BooleanVar(value=bool(self.settings.get("onion_skin",True)))
        quality=tk.StringVar(value=self.settings.get("preview_quality","balanced"))
        preset=tk.StringVar(value=self.settings.get("default_canvas","HD 1280 × 720"))
        confirm=tk.BooleanVar(value=bool(self.settings.get("confirm_exit",True)))
        tips=tk.BooleanVar(value=bool(self.settings.get("show_tips",True)))
        def label(text,row):
            tk.Label(body,text=text,bg="#182336",fg="#dce6f5",font=("Segoe UI",10,"bold")).grid(row=row,column=0,sticky="w",padx=16,pady=10)
        label("FPS по умолчанию",0);ttk.Spinbox(body,from_=1,to=60,textvariable=fps,width=9).grid(row=0,column=1,padx=12)
        label("Размер нового холста",1);ttk.Combobox(body,textvariable=preset,values=list(PRESETS),state="readonly",width=25).grid(row=1,column=1,padx=12)
        ttk.Checkbutton(body,text="Включать Onion Skin в новых проектах",variable=onion).grid(row=2,column=0,columnspan=2,sticky="w",padx=16,pady=8)
        ttk.Checkbutton(body,text="Спрашивать подтверждение при выходе",variable=confirm).grid(row=3,column=0,columnspan=2,sticky="w",padx=16,pady=8)
        ttk.Checkbutton(body,text="Показывать совет дня в главном меню",variable=tips).grid(row=4,column=0,columnspan=2,sticky="w",padx=16,pady=8)
        label("Качество предпросмотра",5);ttk.Combobox(body,textvariable=quality,values=["fast","balanced","high"],state="readonly",width=13).grid(row=5,column=1,padx=12)
        tk.Label(body,text="Параметры сохраняются в профиле Windows и применяются при следующем запуске проекта.",bg="#182336",fg="#91a1b8",wraplength=490,justify="left").grid(row=6,column=0,columnspan=2,sticky="w",padx=16,pady=14)
        def save():
            try:f=max(1,min(60,int(fps.get())))
            except Exception:messagebox.showerror(APP_NAME,"FPS должен быть числом от 1 до 60.",parent=win);return
            self.settings.update(default_fps=f,onion_skin=onion.get(),preview_quality=quality.get(),
                                 default_canvas=preset.get(),confirm_exit=confirm.get(),show_tips=tips.get())
            self.save_settings();win.destroy();messagebox.showinfo(APP_NAME,"Настройки сохранены.",parent=self.root)
        tk.Button(win,text="СОХРАНИТЬ НАСТРОЙКИ",command=save,bg="#3477bd",fg="white",activebackground="#438bd4",
                  relief="flat",font=("Segoe UI",10,"bold"),pady=12,cursor="hand2").pack(fill="x",padx=20,pady=(8,18))

    def about(self):
        win=tk.Toplevel(self.root);win.title("Авторы FRAMEFORGE");win.geometry("520x480")
        win.configure(bg="#111827");win.resizable(False,False);win.transient(self.root)
        card=tk.Frame(win,bg="#1a2638",highlightthickness=1,highlightbackground="#395476");card.pack(fill="both",expand=True,padx=22,pady=22)
        tk.Label(card,text="✦",bg="#1a2638",fg="#82baff",font=("Segoe UI",34,"bold")).pack(pady=(24,0))
        tk.Label(card,text="FRAMEFORGE",bg="#1a2638",fg="#f4f7ff",font=("Segoe UI",24,"bold")).pack(pady=2)
        tk.Label(card,text=f"Версия {VERSION}  •  2D Drawing & Animation",bg="#1a2638",fg="#91a6c3",font=("Segoe UI",9)).pack()
        tk.Frame(card,bg="#344a67",height=1).pack(fill="x",padx=35,pady=20)
        tk.Label(card,text="Создатель и автор проекта",bg="#1a2638",fg="#9db0ca",font=("Segoe UI",9)).pack()
        tk.Label(card,text="TheLucassDen",bg="#1a2638",fg="#8fc0ff",font=("Segoe UI",17,"bold")).pack(pady=4)
        tk.Label(card,text="Программа для художников, аниматоров и авторов независимых проектов.\nСоздавай свои миры — кадр за кадром.",bg="#1a2638",fg="#d3ddec",
                 font=("Segoe UI",10),justify="center",wraplength=410).pack(pady=12)
        tk.Button(card,text="Закрыть",command=win.destroy,bg="#26374f",fg="white",activebackground="#344d70",
                  relief="flat",padx=30,pady=9,cursor="hand2").pack(pady=16)

class FrameForgeSplash:
    """Visible startup screen hosted by the root window (not a hidden-root Toplevel)."""
    def __init__(self, root):
        self.root=root
        self.progress=0
        root.title("FRAMEFORGE — запуск")
        root.configure(bg="#100a1d")
        root.geometry("640x500")
        root.resizable(False,False)
        root.update_idletasks()
        try:
            base=getattr(sys,"_MEIPASS",os.path.dirname(os.path.abspath(__file__)))
            self.icon=tk.PhotoImage(file=os.path.join(base,"assets","frameforge_icon.png"))
            root.iconphoto(True,self.icon)
        except Exception:
            self.icon=None
        self.canvas=tk.Canvas(root,width=640,height=500,bg="#100a1d",highlightthickness=0)
        self.canvas.pack(fill="both",expand=True)
        self.draw()
        root.after(120,self.animate)

    def draw(self):
        c=self.canvas
        c.delete("all")
        c.create_rectangle(0,0,640,500,fill="#100a1d",outline="")
        c.create_oval(95,30,545,480,outline="#24143c",width=3)
        c.create_oval(125,60,515,450,outline="#321b52",width=2)
        # Panda mascot and clapperboard logo
        c.create_oval(228,63,302,137,fill="#090711",outline="#a65bff",width=3)
        c.create_oval(338,63,412,137,fill="#090711",outline="#a65bff",width=3)
        c.create_oval(226,82,414,240,fill="#f6f1fc",outline="#b77aff",width=4)
        c.create_oval(235,139,309,211,fill="#11101a")
        c.create_oval(331,139,405,211,fill="#11101a")
        c.create_oval(260,163,286,189,fill="#42dc88")
        c.create_oval(354,163,380,189,fill="#a65bff")
        c.create_oval(309,205,331,220,fill="#171321")
        c.create_rectangle(157,250,483,354,fill="#211735",outline="#a65bff",width=5)
        c.create_polygon(157,250,483,250,461,213,135,213,fill="#6d39b8",outline="#d9b8ff",width=3)
        for xx in (165,245,325,405):
            c.create_polygon(xx,216,xx+34,216,xx+56,247,xx+22,247,fill="#f0e5ff")
        c.create_polygon(286,276,286,330,337,303,fill="#bd83ff")
        c.create_text(320,390,text="FRAMEFORGE",fill="#f6efff",font=("Segoe UI",29,"bold"))
        c.create_text(320,422,text="DRAW  •  ANIMATE  •  CREATE",fill="#b7a4d2",font=("Segoe UI",10,"bold"))
        c.create_rectangle(105,454,535,466,fill="#292038",outline="#6d43a0")
        c.create_rectangle(107,456,107+426*self.progress,464,fill="#a65bff",outline="")
        c.create_text(320,481,text="Подготавливаем рабочее пространство...",
                      fill="#cdb6ed",font=("Segoe UI",9))

    def animate(self):
        self.progress=min(1.0,self.progress+0.055)
        self.draw()
        if self.progress < 1:
            self.root.after(110,self.animate)
        else:
            self.root.after(250,self.finish)

    def finish(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        if len(sys.argv)>1 and os.path.isfile(sys.argv[1]):
            MainMenu(self.root).open_project(sys.argv[1])
        else:
            MainMenu(self.root)


def register_project_association():
    if sys.platform!="win32" or not getattr(sys,"frozen",False):
        return
    try:
        import winreg
        exe=os.path.abspath(sys.executable)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r"Software\Classes\.ffg") as key:
            winreg.SetValueEx(key,"",0,winreg.REG_SZ,"FRAMEFORGE.Project")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r"Software\Classes\FRAMEFORGE.Project") as key:
            winreg.SetValueEx(key,"",0,winreg.REG_SZ,"FRAMEFORGE Project")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r"Software\Classes\FRAMEFORGE.Project\DefaultIcon") as key:
            winreg.SetValueEx(key,"",0,winreg.REG_SZ,exe+",0")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r"Software\Classes\FRAMEFORGE.Project\shell\open\command") as key:
            winreg.SetValueEx(key,"",0,winreg.REG_SZ,f'"{exe}" "%1"')
    except Exception:
        pass


def launch():
    register_project_association()
    root=tk.Tk()
    FrameForgeSplash(root)
    root.mainloop()



if __name__=="__main__":
    launch()
