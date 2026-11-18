import json, os, tkinter as tk, zipfile
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
from PIL import Image, ImageDraw, ImageTk, ImageSequence

APP_NAME = "FRAMEFORGE"
VERSION = "0.3.0"
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
        self.root.minsize(1100, 720)
        self.w, self.h = 1280, 720
        self.frames = [Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))]
        self.index, self.fps = 0, tk.IntVar(value=12)
        self.size, self.opacity = tk.IntVar(value=8), tk.IntVar(value=100)
        self.color, self.tool = "#202633", tk.StringVar(value="brush")
        self.onion, self.playing = tk.BooleanVar(value=True), False
        self.project, self.last, self.photo = None, None, None
        self.origin, self.status = (0, 0, 1), tk.StringVar(value="Готово")
        self.undo_stack, self.redo_stack = [], []
        self.stroke_before, self.shape_start = None, None
        self.setup_style()
        self.build()
        self.bind_shortcuts()
        self.refresh()
        self.render()

    def setup_style(self):
        self.root.configure(bg=BG)
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
        tk.Label(brand, text="  0.3", bg="#11151d", fg=MUTED).pack(side="left", padx=6)
        for label, fn in [("Новый", self.new), ("Открыть", self.open), ("Сохранить", self.save),
                          ("Экспорт", self.export_menu)]:
            ttk.Button(header, text=label, command=fn).pack(side="left", padx=4, pady=12)
        ttk.Button(header, text="↶ Отмена", command=self.undo).pack(side="left", padx=(18, 3), pady=12)
        ttk.Button(header, text="↷ Повтор", command=self.redo).pack(side="left", padx=3, pady=12)
        tk.Label(header, text="2D ANIMATION WORKSPACE", bg="#11151d", fg="#718096").pack(side="right", padx=16)

        work = tk.Frame(self.root, bg=BG); work.pack(fill="both", expand=True, padx=9, pady=8)
        left = self.panel(work, 190); left.pack(side="left", fill="y")
        self.section(left, "Инструменты")
        tools = [("Карандаш", "pencil"), ("Кисть", "brush"), ("Аэрограф", "airbrush"),
                 ("Ластик", "eraser"), ("Линия", "line"), ("Прямоугольник", "rect"),
                 ("Эллипс", "ellipse"), ("Заливка", "fill"), ("Пипетка", "eyedropper")]
        for label, value in tools:
            ttk.Radiobutton(left, text=label, value=value, variable=self.tool,
                            style="Tool.TRadiobutton").pack(fill="x", padx=7)
        self.section(left, "Параметры")
        row = tk.Frame(left, bg=PANEL); row.pack(fill="x", padx=12, pady=4)
        tk.Label(row, text="Цвет", bg=PANEL, fg=MUTED).pack(side="left")
        self.swatch = tk.Button(row, bg=self.color, width=5, relief="flat", command=self.pick)
        self.swatch.pack(side="right", ipady=6)
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
        self.canvas.bind("<Configure>", lambda e: self.render())
        self.canvas.bind("<Button-1>", self.start)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)

        right = self.panel(work, 205); right.pack(side="right", fill="y")
        self.section(right, "Анимация")
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

    def bind_shortcuts(self):
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-u>", lambda e: self.redo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-s>", lambda e: self.save())
        self.root.bind("<Control-o>", lambda e: self.open())
        self.root.bind("<Control-n>", lambda e: self.new())
        self.root.bind("<space>", lambda e: self.play())

    def size_changed(self, v): self.size_label.config(text=f"{int(float(v))} px")
    def opacity_changed(self, v): self.opacity_label.config(text=f"{int(float(v))}%")
    def pick(self):
        c = colorchooser.askcolor(self.color, title="Цвет кисти")[1]
        if c: self.color = c; self.swatch.config(bg=c)

    def snapshot(self):
        self.undo_stack.append((self.index, [im.copy() for im in self.frames]))
        if len(self.undo_stack) > 40: self.undo_stack.pop(0)
        self.redo_stack.clear()

    def restore(self, stack_from, stack_to):
        if not stack_from: return
        stack_to.append((self.index, [im.copy() for im in self.frames]))
        self.index, self.frames = stack_from.pop()
        self.index = min(self.index, len(self.frames)-1)
        self.refresh(); self.render(); self.status.set("История действий обновлена")

    def undo(self): self.restore(self.undo_stack, self.redo_stack)
    def redo(self): self.restore(self.redo_stack, self.undo_stack)

    def geometry(self):
        cw, ch = max(1,self.canvas.winfo_width()), max(1,self.canvas.winfo_height())
        scale = min((cw-30)/self.w, (ch-30)/self.h)
        return scale, (cw-self.w*scale)/2, (ch-self.h*scale)/2

    def render(self):
        if not hasattr(self, "canvas"): return
        self.canvas.delete("all")
        s,x,y = self.geometry(); ww,hh = max(1,int(self.w*s)),max(1,int(self.h*s))
        tile=max(8,int(16*s))
        for yy in range(0,hh,tile):
            for xx in range(0,ww,tile):
                c="#dce1e8" if ((xx//tile)+(yy//tile))%2==0 else "#c7ced8"
                self.canvas.create_rectangle(x+xx,y+yy,x+min(ww,xx+tile),y+min(hh,yy+tile),fill=c,outline=c)
        im=self.frames[self.index].copy()
        if self.onion.get() and self.index>0:
            prev=self.frames[self.index-1]
            tint=Image.new("RGBA",prev.size,(255,75,95,0)); tint.putalpha(prev.getchannel("A").point(lambda a:int(a*.22)))
            tint.alpha_composite(im); im=tint
        self.photo=ImageTk.PhotoImage(im.resize((ww,hh),Image.Resampling.LANCZOS))
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
            c=self.frames[self.index].getpixel(p)
            if c[3]: self.color="#%02x%02x%02x"%c[:3]; self.swatch.config(bg=self.color)
            return
        if tool=="fill":
            self.snapshot(); ImageDraw.floodfill(self.frames[self.index],p,self.rgba(),thresh=20); self.render(); return
        self.snapshot(); self.stroke_before=self.frames[self.index].copy()
        self.last=p; self.shape_start=p
        if tool in ("pencil","brush","airbrush","eraser"): self.paint_segment(p,p)
        self.render()

    def paint_segment(self,a,b):
        tool=self.tool.get(); im=self.frames[self.index]
        size=max(1,self.size.get()); color=(0,0,0,0) if tool=="eraser" else self.rgba()
        d=ImageDraw.Draw(im)
        if tool=="airbrush":
            layer=Image.new("RGBA",im.size,(0,0,0,0)); ld=ImageDraw.Draw(layer)
            r=max(1,size//2)
            for k in range(4,0,-1):
                rr=max(1,int(r*k/4)); ld.ellipse((b[0]-rr,b[1]-rr,b[0]+rr,b[1]+rr),fill=(*self.rgba()[:3],int(self.rgba()[3]/4)))
            im.alpha_composite(layer)
        else:
            d.line([a,b],fill=color,width=1 if tool=="pencil" else size)
            r=0 if tool=="pencil" else size/2
            d.ellipse((b[0]-r,b[1]-r,b[0]+r,b[1]+r),fill=color)

    def drag(self,e):
        if self.last is None or self.playing:return
        p=self.coords(e); tool=self.tool.get()
        if tool in ("pencil","brush","airbrush","eraser"):
            self.paint_segment(self.last,p); self.last=p; self.render()
        elif tool in ("line","rect","ellipse"):
            self.frames[self.index]=self.stroke_before.copy()
            d=ImageDraw.Draw(self.frames[self.index]); c=self.rgba(); width=max(1,self.size.get())
            if tool=="line": d.line([self.shape_start,p],fill=c,width=width)
            elif tool=="rect": d.rectangle([self.shape_start,p],outline=c,width=width)
            else: d.ellipse([self.shape_start,p],outline=c,width=width)
            self.render()

    def release(self,e):
        if self.last is not None:
            self.last=None; self.render(); self.status.set("Изменения внесены")

    def refresh(self):
        for w in self.timeline.winfo_children(): w.destroy()
        for i in range(len(self.frames)):
            sel=i==self.index
            tk.Button(self.timeline,text=f"КАДР\n{i+1}",command=lambda n=i:self.select(n),
                bg="#284d75" if sel else ALT,fg="white",relief="flat",bd=0,width=8,height=3,
                highlightthickness=1,highlightbackground=ACCENT if sel else BORDER).pack(side="left",padx=3,pady=5)
        self.counter.config(text=f"КАДР {self.index+1} / {len(self.frames)}")
        self.timeline_hint.config(text=f"{len(self.frames)} кадров • {self.fps.get()} FPS")

    def select(self,n):
        self.index=max(0,min(len(self.frames)-1,n)); self.refresh(); self.render()

    def add(self):
        self.snapshot(); self.frames.insert(self.index+1,Image.new("RGBA",(self.w,self.h),(0,0,0,0))); self.select(self.index+1)
    def duplicate(self):
        self.snapshot(); self.frames.insert(self.index+1,self.frames[self.index].copy()); self.select(self.index+1)
    def delete(self):
        self.snapshot()
        if len(self.frames)==1:self.frames[0]=Image.new("RGBA",(self.w,self.h),(0,0,0,0))
        else:self.frames.pop(self.index); self.index=min(self.index,len(self.frames)-1)
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
        self.snapshot(); self.frames=[Image.new("RGBA",(self.w,self.h),cfg["bg"])]
        self.index=0; self.project=None; self.undo_stack.clear(); self.redo_stack.clear()
        self.canvas_info.config(text=f"{self.w} × {self.h}"); self.refresh(); self.render()
        self.status.set("Создан новый холст")

    def save(self):
        path=self.project or filedialog.asksaveasfilename(defaultextension=".ffg",filetypes=[("FRAMEFORGE project","*.ffg")])
        if not path:return
        folder=path+".frames"; os.makedirs(folder,exist_ok=True); names=[]
        for i,im in enumerate(self.frames):
            name=f"frame_{i:05d}.png"; im.save(os.path.join(folder,name)); names.append(name)
        with open(path,"w",encoding="utf-8") as f: json.dump({"version":VERSION,"width":self.w,"height":self.h,"fps":self.fps.get(),"folder":os.path.basename(folder),"frames":names},f,indent=2)
        self.project=path; self.status.set("Проект сохранён"); messagebox.showinfo(APP_NAME,"Проект сохранён.")

    def open(self):
        path=filedialog.askopenfilename(filetypes=[("FRAMEFORGE project","*.ffg")])
        if not path:return
        try:
            with open(path,encoding="utf-8") as f:data=json.load(f)
            folder=os.path.join(os.path.dirname(path),data["folder"])
            self.frames=[Image.open(os.path.join(folder,n)).convert("RGBA") for n in data["frames"]]
            self.w,self.h=data["width"],data["height"]; self.fps.set(data.get("fps",12)); self.index=0; self.project=path
            self.undo_stack.clear(); self.redo_stack.clear()
            self.canvas_info.config(text=f"{self.w} × {self.h}"); self.refresh(); self.render()
        except Exception as e: messagebox.showerror(APP_NAME,str(e))

    def export_menu(self):
        win=tk.Toplevel(self.root); win.title("Экспорт"); win.configure(bg=PANEL); win.resizable(False,False)
        tk.Label(win,text="Экспорт проекта",bg=PANEL,fg=TEXT,font=("Segoe UI",13,"bold")).pack(padx=25,pady=12)
        for label,fn in [("Текущий кадр — PNG",self.png),("Анимация — GIF",self.gif),
                         ("Последовательность PNG — ZIP",self.png_sequence),("Sprite Sheet — PNG",self.sprite_sheet)]:
            ttk.Button(win,text=label,command=lambda f=fn:(win.destroy(),f())).pack(fill="x",padx=18,pady=4)

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


class FrameForgeSplash:
    def __init__(self, root, done):
        self.root, self.done, self.step = root, done, 0
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg="#100d1c")
        width, height = 680, 390
        x = (self.win.winfo_screenwidth()-width)//2
        y = (self.win.winfo_screenheight()-height)//2
        self.win.geometry(f"{width}x{height}+{x}+{y}")
        self.canvas = tk.Canvas(self.win, width=width, height=height,
                                bg="#100d1c", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.draw()
        self.animate()

    def draw(self):
        c=self.canvas; c.delete("all")
        c.create_rectangle(0,0,680,390,fill="#100d1c",outline="")
        for i in range(18):
            xx=(i*83)%680; yy=(i*47)%390
            c.create_oval(xx,yy,xx+2,yy+2,fill="#6840a8",outline="")
        c.create_rounded_rectangle = None
        c.create_rectangle(28,28,652,362,outline="#503078",width=2)
        # Clapperboard mark and animated panda silhouette
        c.create_rectangle(245,78,435,230,fill="#211735",outline="#9d55f5",width=5)
        c.create_polygon(245,78,435,78,414,108,225,108,fill="#6d39b8",outline="#d9b8ff",width=3)
        for xx in (260,310,360,410):
            c.create_line(xx,80,xx+24,106,fill="#f0e5ff",width=7)
        c.create_text(340,159,text="FF",fill="#f5eaff",font=("Segoe UI",48,"bold"))
        # Panda ears/head
        c.create_oval(270,35,325,91,fill="#080811",outline="#b77aff",width=3)
        c.create_oval(355,35,410,91,fill="#080811",outline="#b77aff",width=3)
        c.create_oval(280,48,400,151,fill="#f4f0fa",outline="#b77aff",width=3)
        c.create_oval(289,81,330,122,fill="#11101a")
        c.create_oval(350,81,391,122,fill="#11101a")
        c.create_oval(300,93,314,107,fill="#42d58b")
        c.create_oval(366,93,380,107,fill="#a65bff")
        c.create_oval(330,116,350,130,fill="#171321")
        c.create_text(340,264,text="FRAMEFORGE",fill="#f6efff",
                      font=("Segoe UI",31,"bold"))
        c.create_text(340,296,text="РЕДАКТОР РИСУНКА И 2D-АНИМАЦИИ",
                      fill="#b7a4d2",font=("Segoe UI",10,"bold"))
        c.create_rectangle(95,330,585,340,fill="#292038",outline="#6d43a0")
        progress=min(1,(self.step+1)/18)
        c.create_rectangle(97,332,97+486*progress,338,fill="#a65bff",outline="")
        c.create_text(340,350,text="Загрузка..." if self.step<17 else "Готово",
                      fill="#cdb6ed",font=("Segoe UI",9))

    def animate(self):
        if self.step < 18:
            self.draw()
            self.step += 1
            self.root.after(100,self.animate)
        else:
            self.win.destroy()
            self.done()


def launch():
    root=tk.Tk()
    root.withdraw()
    def open_editor():
        root.deiconify()
        FrameForge(root)
    FrameForgeSplash(root,open_editor)
    root.mainloop()


if __name__=="__main__":
    launch()
