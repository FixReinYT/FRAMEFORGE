import json, os, sys, tkinter as tk, zipfile, subprocess
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
from PIL import Image, ImageDraw, ImageTk, ImageSequence, ImageFilter, ImageFont
from contour_fill import apply_fill
from project_io import read_project, write_project

APP_NAME = "FRAMEFORGE"
VERSION = "0.10.2"
BG, PANEL, ALT, BORDER = "#202630", "#293342", "#303b4b", "#3b485b"
TEXT, MUTED, ACCENT = "#e8edf5", "#a5b2c5", "#68a9e8"

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
        self.root.geometry(f"{min(1500,self.root.winfo_screenwidth()-80)}x{min(920,self.root.winfo_screenheight()-100)}")
        self.root.protocol("WM_DELETE_WINDOW", self.close_project)
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
        self.size, self.opacity = tk.IntVar(value=int(self.user_settings.get("brush_size",8))), tk.IntVar(value=int(self.user_settings.get("brush_opacity",100)))
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
        self.dirty=False
        self.fps.trace_add("write",lambda *_: setattr(self,"dirty",True))
        self.onion.trace_add("write",lambda *_: setattr(self,"dirty",True))
        self.stroke_before, self.shape_start = None, None
        self.stroke_points = []
        self.shape_fill = {"rect":False,"ellipse":False}
        self.fill_source = tk.StringVar(value="Активный слой")
        self.fill_gap = tk.IntVar(value=int(self.user_settings.get("fill_gap",0)))
        self.fill_line_layer = tk.StringVar(value="")
        self.selection_box = None
        self.selection_mask = None
        self.stamp_source = None
        self.symmetry_enabled = False
        self.move_anchor = None
        self.move_image = None
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
        # Krita-inspired dock workspace: compact menu, vertical tools, canvas,
        # contextual right dockers and a full-width animation timeline.
        self.root.configure(bg="#202630")
        menubar=tk.Menu(self.root,tearoff=0,bg="#252d39",fg=TEXT,
                        activebackground="#365575",activeforeground="white")
        file_menu=tk.Menu(menubar,tearoff=0)
        for label,fn in [("Новый проект",self.new),("Открыть…",self.open),
                         ("Вставить изображение…",self.insert_image),("Сохранить",self.save),("Сохранить как…",self.save_as),
                         ("Экспорт…",self.export_menu),("Главное меню",self.return_to_menu)]:
            file_menu.add_command(label=label,command=fn)
        file_menu.add_separator();file_menu.add_command(label="Выход",command=self.close_project)
        menubar.add_cascade(label="Файл",menu=file_menu)
        edit=tk.Menu(menubar,tearoff=0)
        edit.add_command(label="Отменить  Ctrl+Z",command=self.undo)
        edit.add_command(label="Повторить  Ctrl+U",command=self.redo)
        menubar.add_cascade(label="Правка",menu=edit)
        image_menu=tk.Menu(menubar,tearoff=0)
        image_menu.add_command(label="Отразить слой по горизонтали",command=self.flip_layer_horizontal)
        image_menu.add_command(label="Отразить слой по вертикали",command=self.flip_layer_vertical)
        menubar.add_cascade(label="Изображение",menu=image_menu)
        layer_menu=tk.Menu(menubar,tearoff=0)
        layer_menu.add_command(label="Добавить слой",command=self.add_layer)
        layer_menu.add_command(label="Удалить слой",command=self.delete_layer)
        layer_menu.add_command(label="Переместить слой вверх",command=lambda:self.move_layer(-1))
        layer_menu.add_command(label="Переместить слой вниз",command=lambda:self.move_layer(1))
        menubar.add_cascade(label="Слой",menu=layer_menu)
        frame_menu=tk.Menu(menubar,tearoff=0)
        frame_menu.add_command(label="Добавить кадр",command=self.add)
        frame_menu.add_command(label="Дублировать кадр",command=self.duplicate)
        frame_menu.add_command(label="Удалить кадр",command=self.delete)
        menubar.add_cascade(label="Кадр",menu=frame_menu)
        animation_menu=tk.Menu(menubar,tearoff=0)
        animation_menu.add_command(label="Воспроизвести / остановить",command=self.play)
        animation_menu.add_command(label="Экспорт анимации",command=self.export_menu)
        menubar.add_cascade(label="Анимация",menu=animation_menu)
        view_menu=tk.Menu(menubar,tearoff=0)
        view_menu.add_command(label="Во весь экран  F11",command=self.toggle_fullscreen)
        view_menu.add_command(label="Масштаб 100%",command=self.actual_size)
        view_menu.add_command(label="Вписать холст",command=self.fit_canvas)
        menubar.add_cascade(label="Вид",menu=view_menu)
        self.root.configure(menu=menubar)

        top=tk.Frame(self.root,bg="#171d27",height=48);top.pack(fill="x");top.pack_propagate(False)
        brand=tk.Frame(top,bg="#171d27");brand.pack(side="left",padx=(14,20))
        tk.Label(brand,text="FRAME",bg="#171d27",fg="#edf3fb",font=("Segoe UI",15,"bold")).pack(side="left")
        tk.Label(brand,text="FORGE",bg="#171d27",fg="#77b5f5",font=("Segoe UI",15,"bold")).pack(side="left")
        tk.Label(brand,text="  0.10",bg="#171d27",fg="#8190a5",font=("Segoe UI",8,"bold")).pack(side="left",pady=(8,0))
        ttk.Button(top,text="Открыть",command=self.open).pack(side="left",padx=3,pady=7)
        ttk.Button(top,text="Сохранить",command=self.save,style="Accent.TButton").pack(side="left",padx=3,pady=7)
        ttk.Button(top,text="↶",width=3,command=self.undo).pack(side="left",padx=(15,2),pady=7)
        ttk.Button(top,text="↷",width=3,command=self.redo).pack(side="left",padx=2,pady=7)
        tk.Label(top,text="2D ANIMATION WORKSPACE",bg="#171d27",fg="#8494aa",
                 font=("Segoe UI",8,"bold")).pack(side="right",padx=14)
        ttk.Button(top,text="⛶",width=3,command=self.toggle_fullscreen).pack(side="right",padx=8,pady=7)

        # Context toolbar: controls stay visible while the user draws.
        context=tk.Frame(self.root,bg="#293342",height=38);context.pack(fill="x");context.pack_propagate(False)
        tk.Label(context,text="ИНСТРУМЕНТ",bg="#293342",fg="#8fa1b8",
                 font=("Segoe UI",8,"bold")).pack(side="left",padx=(13,8))
        self.context_tool_name=tk.Label(context,text="Кисть",bg="#293342",fg="#e6edf7",
                                        font=("Segoe UI",9,"bold"))
        self.context_tool_name.pack(side="left",padx=(0,18))
        tk.Label(context,text="Размер",bg="#293342",fg="#aebbd0").pack(side="left")
        self.size_label=tk.Label(context,text="8 px",bg="#293342",fg="#edf3fb",width=6)
        self.size_label.pack(side="left",padx=4)
        ttk.Scale(context,from_=1,to=100,variable=self.size,command=self.size_changed,length=125).pack(side="left",padx=3)
        tk.Label(context,text="Непрозрачность",bg="#293342",fg="#aebbd0").pack(side="left",padx=(16,3))
        self.opacity_label=tk.Label(context,text="100%",bg="#293342",fg="#edf3fb",width=5)
        self.opacity_label.pack(side="left")
        ttk.Scale(context,from_=1,to=100,variable=self.opacity,command=self.opacity_changed,length=115).pack(side="left",padx=3)
        tk.Label(context,text="Цвет",bg="#293342",fg="#aebbd0").pack(side="left",padx=(16,5))
        self.swatch=tk.Button(context,bg=self.color,width=3,relief="flat",command=self.pick,
                              activebackground=self.color)
        self.swatch.pack(side="left",pady=5)
        tk.Label(context,text="Колесо: масштаб  •  Средняя кнопка: перемещение холста",
                 bg="#293342",fg="#8192a8",font=("Segoe UI",8)).pack(side="right",padx=14)

        work=tk.Frame(self.root,bg="#202630");work.pack(fill="both",expand=True,padx=7,pady=7)
        # Narrow icon-only toolbox on the left.
        left=tk.Frame(work,bg="#252d39",width=190,highlightthickness=1,highlightbackground="#354153")
        left.pack(side="left",fill="y");left.pack_propagate(False)
        toolbox=tk.Canvas(left,bg="#252d39",highlightthickness=0)
        tool_scroll=ttk.Scrollbar(left,orient="vertical",command=toolbox.yview)
        toolbox.configure(yscrollcommand=tool_scroll.set)
        toolbox.pack(side="left",fill="both",expand=True);tool_scroll.pack(side="right",fill="y")
        tool_inner=tk.Frame(toolbox,bg="#252d39");tool_window=toolbox.create_window((0,0),window=tool_inner,anchor="nw")
        toolbox.bind("<Configure>",lambda e:toolbox.itemconfigure(tool_window,width=e.width))
        tool_inner.bind("<Configure>",lambda e:toolbox.configure(scrollregion=toolbox.bbox("all")))
        tools=[("pencil","Карандаш"),("brush","Кисть"),("airbrush","Аэрограф"),("eraser","Ластик"),
               ("line","Линия"),("rect","Прямоугольник"),("ellipse","Эллипс"),("triangle","Треугольник"),
               ("polygon","Многоугольник"),("bezier","Кривая Безье"),("text","Текст"),("lasso","Лассо"),
               ("magic_wand","Волшебная палочка"),("select","Выделение"),("move","Перемещение"),
               ("transform","Трансформация"),("fill","Заливка"),("gradient","Градиент"),
               ("blur","Размытие"),("sharpen","Резкость"),("stamp","Штамп"),("symmetry","Симметрия"),
               ("eyedropper","Пипетка")]
        self.tool_buttons={}
        for value,label in tools:
            cell=tk.Frame(tool_inner,bg="#252d39",highlightthickness=1,highlightbackground="#354153",height=43)
            cell.pack(fill="x",padx=4,pady=2);cell.pack_propagate(False)
            icon=tk.Canvas(cell,width=38,height=32,bg="#252d39",highlightthickness=0)
            icon.pack(side="left",padx=(7,8),pady=4)
            self.draw_tool_icon(icon,value)
            label_widget=tk.Label(cell,text=label,anchor="w",bg="#252d39",fg="#e8edf5",font=("Segoe UI",9))
            label_widget.pack(side="left",fill="x",expand=True)
            for widget in (cell,icon,label_widget):
                widget.bind("<Button-1>",lambda e,v=value:self.choose_tool(v))
                widget.bind("<Enter>",lambda e,w=cell:w.configure(highlightbackground="#79b7f2"))
                widget.bind("<Leave>",lambda e,w=cell,v=value:w.configure(highlightbackground="#79b7f2" if self.tool.get()==v else "#354153"))
                if value in ("rect","ellipse"):
                    widget.bind("<Button-3>",lambda e,v=value:self.shape_options(v))
            self.tool_buttons[value]=cell
        tk.Frame(left,bg="#3a4658",height=1).pack(fill="x",padx=8,pady=8)
        tk.Label(left,text="FG",bg="#252d39",fg="#aab8ca",font=("Segoe UI",8,"bold")).pack()
        self.mini_swatch=tk.Button(left,bg=self.color,width=3,relief="flat",command=self.pick)
        self.mini_swatch.pack(pady=4)
        self.update_tool_buttons()

        center=tk.Frame(work,bg="#202630");center.pack(side="left",fill="both",expand=True,padx=7)
        head=tk.Frame(center,bg="#293342",height=34);head.pack(fill="x");head.pack_propagate(False)
        tk.Label(head,text="ХОЛСТ",bg="#293342",fg="#e5edf8",
                 font=("Segoe UI",9,"bold")).pack(side="left",padx=12)
        self.canvas_info=tk.Label(head,text="1280 × 720  •  100%",bg="#293342",fg="#aab9ce")
        self.canvas_info.pack(side="right",padx=12)
        shell=tk.Frame(center,bg="#171d27",padx=8,pady=8,
                       highlightthickness=1,highlightbackground="#354153")
        shell.pack(fill="both",expand=True,pady=(5,0))
        self.canvas=tk.Canvas(shell,bg="#202630",highlightthickness=0,cursor="crosshair")
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",self.on_canvas_resize)
        self.canvas.bind("<Button-1>",self.start)
        self.canvas.bind("<Button-3>",lambda e:self.shape_options(self.tool.get()) if self.tool.get() in ("rect","ellipse") else None)
        self.canvas.bind("<B1-Motion>",self.drag)
        self.canvas.bind("<ButtonRelease-1>",self.release)
        self.canvas.bind("<MouseWheel>",self.zoom_wheel)
        self.canvas.bind("<Button-4>",lambda e:self.zoom_at(e.x,e.y,1.12))
        self.canvas.bind("<Button-5>",lambda e:self.zoom_at(e.x,e.y,1/1.12))
        self.canvas.bind("<ButtonPress-2>",self.pan_start)
        self.canvas.bind("<B2-Motion>",self.pan_drag)

        # Right-side dockers, grouped into tabs like a professional painting workspace.
        right=self.panel(work,278);right.pack(side="right",fill="y")
        tabs=ttk.Notebook(right);tabs.pack(fill="both",expand=True,padx=5,pady=5)
        tooltab=tk.Frame(tabs,bg=PANEL);colortab=tk.Frame(tabs,bg=PANEL)
        layertab=tk.Frame(tabs,bg=PANEL);animtab=tk.Frame(tabs,bg=PANEL)
        tabs.add(tooltab,text="Инструмент");tabs.add(colortab,text="Цвет")
        tabs.add(layertab,text="Слои");tabs.add(animtab,text="Анимация")
        self.section(tooltab,"Параметры инструмента")
        tk.Label(tooltab,text="Размер кисти",bg=PANEL,fg=MUTED).pack(anchor="w",padx=12,pady=(8,0))
        ttk.Scale(tooltab,from_=1,to=100,variable=self.size,command=self.size_changed).pack(fill="x",padx=12)
        tk.Label(tooltab,text="Непрозрачность",bg=PANEL,fg=MUTED).pack(anchor="w",padx=12,pady=(8,0))
        ttk.Scale(tooltab,from_=1,to=100,variable=self.opacity,command=self.opacity_changed).pack(fill="x",padx=12)
        self.section(tooltab,"Заливка • контуры")
        ttk.Label(tooltab,text="Источник границ").pack(anchor="w",padx=10)
        self.fill_source_choice=ttk.Combobox(tooltab,textvariable=self.fill_source,
            values=["Активный слой","Другой слой"],state="readonly")
        self.fill_source_choice.pack(fill="x",padx=10,pady=3)
        ttk.Label(tooltab,text="Слой с контуром").pack(anchor="w",padx=10)
        self.fill_layer_choice=ttk.Combobox(tooltab,textvariable=self.fill_line_layer,state="readonly")
        self.fill_layer_choice.pack(fill="x",padx=10,pady=3)
        ttk.Label(tooltab,text="Допустимый зазор (0–12 px)").pack(anchor="w",padx=10)
        ttk.Spinbox(tooltab,from_=0,to=12,textvariable=self.fill_gap,width=8).pack(anchor="w",padx=10,pady=3)
        ttk.Label(tooltab,text="Замыкание применяется только при поиске области.",wraplength=235).pack(anchor="w",padx=10,pady=4)
        ttk.Checkbutton(tooltab,text="Луковая шелуха",variable=self.onion,command=self.render).pack(anchor="w",padx=12,pady=10)

        self.section(colortab,"Основной цвет")
        colorrow=tk.Frame(colortab,bg=PANEL);colorrow.pack(fill="x",padx=12,pady=8)
        self.color_preview=tk.Label(colorrow,text=self.color.upper(),bg=self.color,fg="#ffffff",
                                    font=("Segoe UI",10,"bold"),width=13,height=3)
        self.color_preview.pack(fill="x")
        ttk.Button(colortab,text="Выбрать цвет…",command=self.pick,style="Accent.TButton").pack(fill="x",padx=12,pady=6)
        ttk.Button(colortab,text="Палитра цветов…",command=self.pick).pack(fill="x",padx=12,pady=3)
        self.section(colortab,"Быстрая палитра")
        palette=["#111318","#343941","#626a76","#9ba3af","#dce1e8","#ffffff",
                 "#5b2028","#a8323e","#e14b59","#ff8290","#f5b4ba","#fce4e6",
                 "#64351d","#a85b2b","#d88945","#f2b66d","#f6d7a8","#fff0d8",
                 "#66501c","#a58a2b","#d6bd45","#f1dc75","#f7edb2","#fff9dc",
                 "#24523b","#347b55","#4ca879","#82c99c","#b7e4c7","#e3f5e9",
                 "#1d5260","#287f91","#42b5c9","#83d4df","#bcebf0","#e7f8fa",
                 "#263c70","#365da6","#5884d8","#8eafea","#c3d4f5","#eaf0fc",
                 "#49316f","#704ca5","#966bd0","#bd9ce8","#d9c5f3","#f1eafa",
                 "#7b315d","#b34d87","#dc78b0","#eda4cc","#f5cce1","#fceaf3"]
        pal=tk.Frame(colortab,bg=PANEL);pal.pack(fill="x",padx=10,pady=5)
        for i,col in enumerate(palette):
            b=tk.Button(pal,bg=col,width=2,height=1,relief="flat",bd=0,
                        activebackground=col,command=lambda value=col:self.set_color(value))
            b.grid(row=i//6,column=i%6,padx=2,pady=2,sticky="nsew")
        for col in range(6):pal.grid_columnconfigure(col,weight=1)

        self.section(layertab,"Слои • порядок наложения")
        layerbar=tk.Frame(layertab,bg=PANEL);layerbar.pack(fill="x",padx=8)
        for label,fn in [("+",self.add_layer),("−",self.delete_layer),
                         ("↑",lambda:self.move_layer(-1)),("↓",lambda:self.move_layer(1)),
                         ("◉",self.toggle_layer_visibility)]:
            ttk.Button(layerbar,text=label,width=3,command=fn).pack(side="left",expand=True,fill="x",padx=1)
        self.layer_list=tk.Listbox(layertab,height=14,bg=ALT,fg=TEXT,selectbackground="#365a83",
                                   relief="flat",highlightthickness=0,exportselection=False)
        self.layer_list.pack(fill="both",expand=True,padx=9,pady=7)
        self.layer_list.bind("<<ListboxSelect>>",self.select_layer)
        ttk.Button(layertab,text="Залить фон цветом",command=self.fill_background).pack(fill="x",padx=9,pady=4)

        self.section(animtab,"Воспроизведение")
        tk.Label(animtab,text="Кадров в секунду",bg=PANEL,fg=MUTED).pack(anchor="w",padx=12)
        ttk.Spinbox(animtab,from_=1,to=60,textvariable=self.fps,width=8).pack(anchor="w",padx=12,pady=5)
        self.playbtn=ttk.Button(animtab,text="▶ Воспроизвести",style="Accent.TButton",command=self.play)
        self.playbtn.pack(fill="x",padx=10,pady=8)
        self.section(animtab,"Управление кадрами")
        for label,fn in [("+ Добавить кадр",self.add),("▣ Дублировать",self.duplicate),("− Удалить кадр",self.delete)]:
            ttk.Button(animtab,text=label,command=fn).pack(fill="x",padx=10,pady=3)
        nav=tk.Frame(animtab,bg=PANEL);nav.pack(fill="x",padx=10,pady=8)
        ttk.Button(nav,text="← Предыдущий",command=lambda:self.select(self.index-1)).pack(side="left",expand=True,fill="x",padx=2)
        ttk.Button(nav,text="Следующий →",command=lambda:self.select(self.index+1)).pack(side="left",expand=True,fill="x",padx=2)
        self.counter=tk.Label(animtab,text="КАДР 1 / 1",bg=PANEL,fg=TEXT,font=("Segoe UI",11,"bold"));self.counter.pack(pady=10)

        timeline=self.panel(self.root);timeline.pack(fill="x",padx=7,pady=(0,6))
        th=tk.Frame(timeline,bg=PANEL);th.pack(fill="x")
        tk.Label(th,text="ТАЙМЛАЙН КАДРОВ",bg=PANEL,fg=TEXT,font=("Segoe UI",9,"bold")).pack(side="left",padx=12,pady=7)
        self.timeline_hint=tk.Label(th,text="",bg=PANEL,fg=MUTED);self.timeline_hint.pack(side="right",padx=12)
        self.timeline_scroll=ttk.Scrollbar(timeline,orient="horizontal")
        self.timeline_scroll.pack(side="bottom",fill="x",padx=6,pady=(0,4))
        self.timeline_canvas=tk.Canvas(timeline,bg="#1a202b",height=76,highlightthickness=0,xscrollcommand=self.timeline_scroll.set)
        self.timeline_canvas.pack(fill="x",padx=6)
        self.timeline_scroll.configure(command=self.timeline_canvas.xview)
        self.timeline=tk.Frame(self.timeline_canvas,bg="#1a202b")
        self.timeline_canvas.create_window((0,0),window=self.timeline,anchor="nw")
        self.timeline.bind("<Configure>",lambda e:self.timeline_canvas.configure(scrollregion=self.timeline_canvas.bbox("all")))
        self.timeline_canvas.bind("<MouseWheel>",self.scroll_timeline)
        self.timeline_canvas.bind("<Button-4>",self.scroll_timeline)
        self.timeline_canvas.bind("<Button-5>",self.scroll_timeline)
        footer=tk.Frame(self.root,bg="#171d27",height=24);footer.pack(fill="x",side="bottom");footer.pack_propagate(False)
        tk.Label(footer,textvariable=self.status,bg="#171d27",fg="#aab8ca").pack(side="left",padx=10)
        tk.Label(footer,text="FRAMEFORGE  •  THELUCASSDEN",bg="#171d27",fg="#71839b",
                 font=("Segoe UI",8,"bold")).pack(side="right",padx=10)
    def shape_options(self,tool):
        menu=tk.Menu(self.root,tearoff=0)
        menu.add_command(label="Только контур",command=lambda:self.set_shape_fill(tool,False))
        menu.add_command(label="С заливкой",command=lambda:self.set_shape_fill(tool,True))
        menu.tk_popup(self.root.winfo_pointerx(),self.root.winfo_pointery())

    def set_shape_fill(self,tool,value):
        self.shape_fill[tool]=value
        self.status.set(("Заливка включена" if value else "Только контур")+" — "+("прямоугольник" if tool=="rect" else "эллипс"))

    def choose_tool(self,value):
        self.tool.set(value)
        self.update_tool_buttons()

    def update_tool_buttons(self):
        labels={"pencil":"Карандаш","brush":"Кисть","airbrush":"Аэрограф","eraser":"Ластик",
                "line":"Линия","rect":"Прямоугольник","ellipse":"Эллипс","triangle":"Треугольник",
                "select":"Выделение","move":"Перемещение","fill":"Заливка","eyedropper":"Пипетка"}
        selected=self.tool.get()
        if hasattr(self,"context_tool_name"):
            self.context_tool_name.config(text=labels.get(selected,selected))
        for name,widget in getattr(self,"tool_buttons",{}).items():
            active=name==selected
            bg="#314b68" if active else "#252d39"
            widget.configure(bg=bg,highlightbackground="#79b7f2" if active else "#354153")
            for child in widget.winfo_children():
                try: child.configure(bg=bg)
                except tk.TclError: pass

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
        elif name in ("polygon","bezier"):
            if name=="polygon":canvas.create_polygon(19,4,31,13,26,28,9,28,5,13,outline=accent,fill="",width=2)
            else:canvas.create_line(5,25,12,5,26,27,32,7,smooth=True,fill=accent,width=3)
        elif name in ("text","lasso","magic_wand","transform","gradient","blur","sharpen","stamp","symmetry"):
            glyph={"text":"T","lasso":"⌁","magic_wand":"✦","transform":"↗","gradient":"◩","blur":"◌","sharpen":"✣","stamp":"▣","symmetry":"⇄"}[name]
            canvas.create_text(19,17,text=glyph,fill=accent,font=("Segoe UI",18,"bold"))

    def bind_shortcuts(self):
        self.root.bind("<Control-z>", lambda e: (self.undo(),"break")[1])
        self.root.bind("<Control-u>", lambda e: self.redo())
        self.root.bind("<Control-y>", lambda e: (self.redo(),"break")[1])
        self.root.bind("<Control-Shift-Z>", lambda e: (self.redo(),"break")[1])
        self.root.bind("<Control-Shift-S>", lambda e: (self.save_as(),"break")[1])
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
        for widget_name in ("swatch","mini_swatch"):
            widget=getattr(self,widget_name,None)
            if widget is not None: widget.config(bg=color,activebackground=color)
        preview=getattr(self,"color_preview",None)
        if preview is not None: preview.config(bg=color,text=color.upper())

    def active_image(self):
        return self.layer_frames[self.index][self.active_layer]["image"]

    def sync_frame_cache(self):
        count=len(self.layer_frames)
        if len(self.frames)!=count:
            self.frames=[None]*count

    def compose_frame(self, index):
        self.sync_frame_cache()
        result=Image.new("RGBA",(self.w,self.h),(0,0,0,0))
        for layer in self.layer_frames[index]:
            if layer["visible"]:
                image=layer["image"]
                opacity=layer.get("opacity",100)
                if opacity!=100:
                    image=image.copy(); image.putalpha(image.getchannel("A").point(lambda a:round(a*opacity/100)))
                result.alpha_composite(image)
        self.frames[index]=result
        return result

    def refresh_layers(self):
        if not hasattr(self,"layer_list"): return
        self.layer_list.delete(0,"end")
        for layer in self.layer_frames[self.index]:
            self.layer_list.insert("end",("● " if layer["visible"] else "○ ")+layer["name"])
        self.active_layer=max(0,min(self.active_layer,len(self.layer_frames[self.index])-1))
        self.layer_list.selection_set(self.active_layer)
        if hasattr(self,"fill_layer_choice"):
            options=[f"{i}: {l['name']}" for i,l in enumerate(self.layer_frames[self.index])]
            self.fill_layer_choice.configure(values=options)
            if self.fill_line_layer.get() not in options:
                candidates=[v for i,v in enumerate(options) if i!=self.active_layer]
                self.fill_line_layer.set(candidates[0] if candidates else "")

    def select_layer(self,event=None):
        selection=self.layer_list.curselection()
        if selection: self.active_layer=selection[0]

    def toggle_layer_visibility(self):
        self.snapshot()
        layer=self.layer_frames[self.index][self.active_layer]
        layer["visible"]=not layer["visible"]
        self.compose_frame(self.index); self.refresh_layers(); self.render()

    def add_layer(self):
        self.snapshot()
        self.layer_frames[self.index].append({"name":f"Слой {len(self.layer_frames[self.index])+1}","image":Image.new("RGBA",(self.w,self.h),(0,0,0,0)),"visible":True})
        self.active_layer=len(self.layer_frames[self.index])-1
        self.compose_frame(self.index); self.refresh_layers(); self.render()

    def delete_layer(self):
        layers=self.layer_frames[self.index]
        if len(layers)<=1:
            messagebox.showinfo(APP_NAME,"Нельзя удалить последний слой."); return
        self.snapshot()
        layers.pop(self.active_layer); self.active_layer=max(0,self.active_layer-1)
        self.compose_frame(self.index); self.refresh_layers(); self.render()

    def move_layer(self,delta):
        layers=self.layer_frames[self.index]; target=self.active_layer+delta
        if not 0<=target<len(layers): return
        self.snapshot()
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

    def fit_canvas(self):
        self.zoom=1.0; self.pan_x=self.pan_y=0.0; self.render()

    def actual_size(self):
        self.zoom=1.0; self.pan_x=self.pan_y=0.0
        scale,_,_=self.geometry()
        self.zoom=1.0/scale; self.render()

    def zoom_wheel(self, event):
        self.zoom_at(event.x, event.y, (1+int(self.user_settings.get("zoom_step",12))/100) ** (event.delta / 120 if sys.platform == "win32" else max(-4,min(4,event.delta))))

    def zoom_at(self, sx, sy, factor):
        old_x, old_y, old_scale = self.origin
        image_x = (sx - old_x) / old_scale
        image_y = (sy - old_y) / old_scale
        self.zoom = max(0.10, min(8.0, self.zoom * factor))
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        fit = min(max(1,cw - 30) / self.w, max(1,ch - 30) / self.h)
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

    def capture_state(self, all_frames=False, idx=None):
        idx=self.index if idx is None else idx
        def clone(frame):
            return [dict(l,image=l["image"].copy()) for l in frame]
        payload=[clone(f) for f in self.layer_frames] if all_frames else clone(self.layer_frames[idx])
        return ("all" if all_frames else "frame",idx,payload,self.active_layer,self.selection_box)

    def snapshot(self, all_frames=False):
        self.undo_stack.append(self.capture_state(all_frames))
        self.redo_stack.clear()
        self.dirty=True
        self.limit_history(self.undo_stack)

    def limit_history(self, stack):
        def cost(state):
            frames=state[2] if state[0]=="all" else [state[2]]
            return sum(l["image"].width*l["image"].height*4 for f in frames for l in f)
        total=sum(map(cost,stack))
        while len(stack)>1 and (len(stack)>getattr(self,"user_settings",{}).get("history_steps",40) or total>getattr(self,"user_settings",{}).get("history_mb",128)*1024*1024):
            total-=cost(stack.pop(0))

    def restore(self, stack_from, stack_to):
        if not stack_from or self.last is not None: return
        self.playing=False
        kind,idx,payload,active,selection=stack_from[-1]
        stack_to.append(self.capture_state(kind=="all",None if kind=="all" else idx))
        self.limit_history(stack_to)
        stack_from.pop()
        if kind=="all":
            self.layer_frames=payload
            self.frames=[None]*len(payload)
            for i in range(len(payload)): self.compose_frame(i)
        else:
            self.layer_frames[idx]=payload
            self.compose_frame(idx)
        self.index=idx
        self.active_layer=active
        self.selection_box=selection
        self.dirty=True
        self.refresh(); self.render(); self.status.set("История действий обновлена")

    def undo(self): self.restore(self.undo_stack, self.redo_stack)
    def redo(self): self.restore(self.redo_stack, self.undo_stack)

    def geometry(self):
        cw, ch = max(1,self.canvas.winfo_width()), max(1,self.canvas.winfo_height())
        scale = min(max(1,cw-30)/self.w, max(1,ch-30)/self.h) * self.zoom
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
            tile=max(8,int(self.user_settings.get("checker_tile",16)*s))
            dark=self.user_settings.get("checker_theme")=="dark"
            checker=Image.new("RGB",(ww,hh),"#414650" if dark else "#c7ced8")
            cd=ImageDraw.Draw(checker)
            for yy in range(0,hh,tile):
                for xx in range(0,ww,tile):
                    if ((xx//tile)+(yy//tile))%2==0:
                        cd.rectangle((xx,yy,min(ww-1,xx+tile-1),min(hh-1,yy+tile-1)),fill="#535963" if dark else "#dce1e8")
            self.checker_cache=checker
        base=self.checker_cache.convert("RGBA")
        im=self.compose_frame(self.index).copy()
        if self.onion.get() and self.index>0:
            prev=self.compose_frame(self.index-1)
            tint=Image.new("RGBA",prev.size,(255,75,95,0))
            tint.putalpha(prev.getchannel("A").point(lambda a:int(a*self.user_settings.get("onion_opacity",22)/100)))
            tint.alpha_composite(im); im=tint
        base.alpha_composite(im.resize((ww,hh),{"fast":Image.Resampling.NEAREST,"balanced":Image.Resampling.BILINEAR,"high":Image.Resampling.LANCZOS}.get(self.user_settings.get("preview_quality"),Image.Resampling.BILINEAR)))
        self.photo=ImageTk.PhotoImage(base.convert("RGB"))
        self.canvas.create_image(x,y,image=self.photo,anchor="nw")
        self.canvas.create_rectangle(x,y,x+ww,y+hh,outline="#718096")
        self.origin=(x,y,s)
        self.canvas_info.config(text=f"{self.w} × {self.h}  •  {s*100:.0f}%")

    def coords(self,e):
        x,y,s=self.origin
        return max(0,min(self.w-1,int((e.x-x)/s))),max(0,min(self.h-1,int((e.y-y)/s)))

    def rgba(self):
        rgb=tuple(bytes.fromhex(self.color.lstrip("#")))
        return (*rgb, int(255*self.opacity.get()/100))

    def start(self,e):
        if self.playing:return
        p=self.coords(e); tool=self.tool.get()
        if tool=="select":
            self.selection_box=self.active_image().getbbox();self.render()
            self.status.set("Выделено содержимое активного слоя" if self.selection_box else "На слое нет рисунка")
            return
        if tool=="magic_wand":
            from collections import deque
            src=self.active_image().convert("RGB");target=src.getpixel(p);pixels=src.load()
            mask=Image.new("L",(self.w,self.h),0);mp=mask.load();queue=deque([p]);mp[p[0],p[1]]=255
            tolerance=32
            while queue and len(queue)<self.w*self.h:
                x,y=queue.popleft()
                for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                    if 0<=nx<self.w and 0<=ny<self.h and mp[nx,ny]==0:
                        px=pixels[nx,ny]
                        if sum((px[k]-target[k])**2 for k in range(3))<=tolerance*tolerance*3:
                            mp[nx,ny]=255;queue.append((nx,ny))
            self.selection_mask=mask;self.selection_box=mask.getbbox()
            self.status.set("Область по цвету выделена" if self.selection_box else "Область не найдена")
            return
        if tool=="text":
            value=simpledialog.askstring(APP_NAME,"Введите текст:",parent=self.root)
            if value:
                self.snapshot()
                try: font=ImageFont.truetype("arial.ttf",max(12,self.size.get()*3))
                except Exception: font=ImageFont.load_default()
                ImageDraw.Draw(self.active_image()).text(p,value,fill=self.rgba(),font=font)
                self.compose_frame(self.index);self.render();self.status.set("Текст добавлен")
            return
        if tool=="symmetry":
            self.symmetry_enabled=not self.symmetry_enabled
            self.status.set("Зеркальное рисование: "+("ВКЛ" if self.symmetry_enabled else "ВЫКЛ"))
            self.choose_tool("brush");return
        if tool=="transform":
            box=self.active_image().getbbox()
            if not box:self.status.set("На слое нет содержимого");return
            scale=simpledialog.askfloat(APP_NAME,"Масштаб (%)",initialvalue=100,minvalue=1,maxvalue=1000,parent=self.root)
            if scale is None:return
            angle=simpledialog.askfloat(APP_NAME,"Поворот (градусы)",initialvalue=0,parent=self.root)
            if angle is None:return
            self.snapshot();src=self.active_image();crop=src.crop(box)
            crop=crop.resize((max(1,int(crop.width*scale/100)),max(1,int(crop.height*scale/100))),Image.Resampling.LANCZOS).rotate(angle,expand=True,resample=Image.Resampling.BICUBIC)
            out=Image.new("RGBA",(self.w,self.h),(0,0,0,0));out.alpha_composite(crop,(max(0,(self.w-crop.width)//2),max(0,(self.h-crop.height)//2)))
            self.layer_frames[self.index][self.active_layer]["image"]=out;self.compose_frame(self.index);self.render();self.status.set("Трансформация применена");return
        if tool=="stamp":
            if e.state & 0x0008 or e.state & 0x0004:
                self.stamp_source=p;self.status.set("Источник штампа выбран");return
            if self.stamp_source is None:self.status.set("Удерживай Alt и щёлкни по источнику");return
        if tool=="move":
            self.snapshot();self.move_anchor=p;self.move_image=self.active_image().copy();self.last=p;return
        if tool=="eyedropper":
            # Sample the visible composite so colors on other layers can be picked.
            try:
                col=self.compose_frame(self.index).convert("RGBA").getpixel(p)
                if col[3]:
                    self.set_color("#%02x%02x%02x"%col[:3])
                    self.status.set("Цвет выбран: "+self.color.upper())
                else:
                    self.status.set("В этой точке нет видимого цвета")
            except Exception as exc:
                messagebox.showerror(APP_NAME,"Не удалось взять цвет: "+str(exc),parent=self.root)
            return
        if tool=="fill":
            layers=self.layer_frames[self.index]
            separate=self.fill_source.get()=="Другой слой"
            source=self.active_image()
            if separate:
                selected=self.fill_line_layer.get()
                try:source_index=int(selected.split(":",1)[0])
                except (ValueError,IndexError):
                    messagebox.showwarning(APP_NAME,"Выбери слой с контуром.");return
                if source_index==self.active_layer:
                    messagebox.showwarning(APP_NAME,"Для раздельной раскраски выбери другой слой с линиями.");return
                if not 0<=source_index<len(layers):return
                source=layers[source_index]["image"]
            try:
                output=apply_fill(self.active_image(),source,p,self.rgba(),
                    gap=self.fill_gap.get(),separate=separate)
            except Exception as exc:
                messagebox.showerror(APP_NAME,"Ошибка заливки: "+str(exc));return
            if output is None:
                self.status.set("Область заливки не найдена");return
            self.snapshot()
            layers[self.active_layer]["image"]=output
            self.compose_frame(self.index);self.render()
            self.status.set("Область закрашена");return
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
        if tool=="move" and self.move_anchor is not None:
            dx=p[0]-self.move_anchor[0];dy=p[1]-self.move_anchor[1]
            moved=Image.new("RGBA",(self.w,self.h),(0,0,0,0));moved.alpha_composite(self.move_image,(dx,dy))
            self.layer_frames[self.index][self.active_layer]["image"]=moved
            self.compose_frame(self.index);self.render();return
        if tool in ("select","eyedropper","fill","text","transform","symmetry","magic_wand"):return
        if e.state & 0x0001 and tool in ("brush","pencil","airbrush","eraser","line","rect","ellipse","triangle"):
            dx=p[0]-self.shape_start[0];dy=p[1]-self.shape_start[1]
            if tool in ("rect","ellipse","triangle"):
                side=max(abs(dx),abs(dy));p=(self.shape_start[0]+(side if dx>=0 else -side),self.shape_start[1]+(side if dy>=0 else -side))
            else:p=(p[0],self.shape_start[1])
        a=self.to_canvas(self.last); b=self.to_canvas(p)
        if tool=="move" and self.move_anchor is not None:
            self.move_anchor=None;self.move_image=None;self.last=None;self.compose_frame(self.index);self.render();self.status.set("Слой перемещён");return
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
            else:
                item=self.canvas.create_oval(*a,*b,outline=self.color,fill=self.color if self.shape_fill["ellipse"] else "",width=max(1,int(self.size.get()*self.origin[2])))
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
        if tool=="move":
            self.move_anchor=None; self.move_image=None; self.last=None; self.render(); return
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
        elif tool in ("line","rect","ellipse","triangle"):
            if e.state & 0x0001 and tool in ("rect","ellipse","triangle"):
                dx=p[0]-self.shape_start[0];dy=p[1]-self.shape_start[1];side=max(abs(dx),abs(dy))
                p=(self.shape_start[0]+(side if dx>=0 else -side),self.shape_start[1]+(side if dy>=0 else -side))
            a=self.shape_start
            if tool=="line":d.line([a,p],fill=color,width=width)
            elif tool=="rect":d.rectangle([min(a[0],p[0]),min(a[1],p[1]),max(a[0],p[0]),max(a[1],p[1])],outline=color,fill=color if self.shape_fill["rect"] else None,width=width)
            elif tool=="triangle":
                mid=(a[0]+p[0])//2
                d.line([(mid,a[1]),p,(a[0],p[1]),(mid,a[1])],fill=color,width=width)
            elif tool=="rect":d.rectangle([a,p],outline=color,fill=color if self.shape_fill["rect"] else None,width=width)
            else:d.ellipse([min(a[0],p[0]),min(a[1],p[1]),max(a[0],p[0]),max(a[1],p[1])],outline=color,fill=color if self.shape_fill["ellipse"] else None,width=width)
        if tool in ("blur","sharpen") and points:
            pad=max(4,width*2)
            box=(max(0,min(q[0] for q in points)-pad),max(0,min(q[1] for q in points)-pad),min(self.w,max(q[0] for q in points)+pad+1),min(self.h,max(q[1] for q in points)+pad+1))
            original=im.crop(box)
            filtered=original.filter(ImageFilter.GaussianBlur(radius=max(1,width/5))) if tool=="blur" else original.filter(ImageFilter.UnsharpMask(radius=max(1,width/8),percent=180,threshold=2))
            mask=Image.new("L",original.size,0);md=ImageDraw.Draw(mask);local=[(x-box[0],y-box[1]) for x,y in points]
            md.line(local,fill=255,width=max(3,width*2),joint="curve");im.paste(filtered,box,mask)
        if tool=="lasso" and len(points)>=3:
            mask=Image.new("L",(self.w,self.h),0);ImageDraw.Draw(mask).polygon(points,fill=255)
            self.selection_mask=mask;self.selection_box=mask.getbbox();self.status.set("Свободное выделение создано")
        if tool=="stamp" and self.stamp_source is not None:
            sx,sy=self.stamp_source;r=max(4,width)
            source=im.crop((max(0,sx-r),max(0,sy-r),min(self.w,sx+r+1),min(self.h,sy+r+1)))
            for x,y in points:im.paste(source,(max(0,min(self.w-source.width,x-r)),max(0,min(self.h-source.height,y-r))),source)
        if tool=="gradient":
            x0,y0=self.shape_start;x1,y1=p;left,top=max(0,min(x0,x1)),max(0,min(y0,y1));right,bottom=min(self.w,max(x0,x1)),min(self.h,max(y0,y1))
            if right>left and bottom>top:
                patch=Image.new("RGBA",(right-left,bottom-top));pix=patch.load();vx=x1-x0;vy=y1-y0;den=max(1,vx*vx+vy*vy);base=self.rgba()
                for yy in range(patch.height):
                    for xx in range(patch.width):
                        t=max(0,min(1,((left+xx-x0)*vx+(top+yy-y0)*vy)/den));pix[xx,yy]=(base[0],base[1],base[2],int(base[3]*(1-t)))
                im.alpha_composite(patch,(left,top))
        if tool=="polygon":
            import math
            x0,y0=self.shape_start;cx=(x0+p[0])//2;cy=(y0+p[1])//2;rx=max(1,abs(p[0]-x0)//2);ry=max(1,abs(p[1]-y0)//2)
            pts=[(cx+rx*math.cos(i*math.pi/3-math.pi/2),cy+ry*math.sin(i*math.pi/3-math.pi/2)) for i in range(6)];d.polygon(pts,outline=color)
        if tool=="bezier":
            x0,y0=self.shape_start;pts=[]
            for i in range(101):
                t=i/100;u=1-t;cx=(x0+p[0])//2;cy=min(y0,p[1])-abs(p[1]-y0)//2
                pts.append((int(u*u*x0+2*u*t*cx+t*t*p[0]),int(u*u*y0+2*u*t*cy+t*t*p[1])))
            d.line(pts,fill=color,width=width)
        if tool in ("pencil","brush","airbrush") and self.symmetry_enabled:
            mirrored=[(self.w-1-x,y) for x,y in points]
            if len(mirrored)>1:d.line(mirrored,fill=color,width=width,joint="curve")
        for item in self.preview_ids:self.canvas.delete(item)
        self.preview_ids=[]; self.last=None; self.stroke_points=[];self.move_anchor=None;self.move_image=None
        self.compose_frame(self.index)
        self.render()
        self.status.set("Изменения внесены")

    def refresh(self):
        for w in self.timeline.winfo_children(): w.destroy()
        for i in range(len(self.frames)):
            sel=i==self.index
            button=tk.Button(self.timeline,text=f"КАДР\n{i+1}",command=lambda n=i:self.select(n),
                bg="#284d75" if sel else ALT,fg="white",relief="flat",bd=0,width=8,height=3,
                highlightthickness=1,highlightbackground=ACCENT if sel else BORDER)
            button.pack(side="left",padx=3,pady=5)
            for event in ("<MouseWheel>","<Button-4>","<Button-5>"):button.bind(event,self.scroll_timeline)
            if sel:self.timeline_selected=button
        self.counter.config(text=f"КАДР {self.index+1} / {len(self.frames)}")
        self.refresh_layers()
        self.timeline_hint.config(text=f"{len(self.frames)} кадров • {self.fps.get()} FPS")

        self.timeline_canvas.update_idletasks()
        self.timeline_canvas.configure(scrollregion=self.timeline_canvas.bbox("all"))
        if self.frames:
            width=max(1,self.timeline.winfo_reqwidth())
            left=self.timeline_canvas.canvasx(0)
            view=self.timeline_canvas.winfo_width()
            x=self.timeline_selected.winfo_x()
            right=x+self.timeline_selected.winfo_width()+6
            if x<left:self.timeline_canvas.xview_moveto(max(0,x-6)/width)
            elif right>left+view:self.timeline_canvas.xview_moveto(max(0,right-view)/width)

    def scroll_timeline(self,event):
        direction=-1 if getattr(event,"num",0)==4 or getattr(event,"delta",0)>0 else 1
        self.timeline_canvas.xview_scroll(direction*3,"units")
        return "break"

    def select(self,n):
        self.index=max(0,min(len(self.frames)-1,n)); self.refresh(); self.render()

    def add(self):
        self.snapshot(all_frames=True); self.frames.insert(self.index+1,Image.new("RGBA",(self.w,self.h),(0,0,0,0))); self.layer_frames.insert(self.index+1,[{"name":l["name"],"image":Image.new("RGBA",(self.w,self.h),(0,0,0,0)),"visible":l["visible"]} for l in self.layer_frames[self.index]]); self.select(self.index+1)
    def duplicate(self):
        self.snapshot(all_frames=True); self.frames.insert(self.index+1,self.frames[self.index].copy()); self.layer_frames.insert(self.index+1,[{"name":l["name"],"image":l["image"].copy(),"visible":l["visible"]} for l in self.layer_frames[self.index]]); self.select(self.index+1)
    def delete(self):
        self.snapshot(all_frames=True)
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
        preset=tk.StringVar(value=self.user_settings.get("default_canvas","HD 1280 × 720"))
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
        if not self.confirm_discard():return
        cfg=self.choose_canvas()
        if not cfg:return
        self.w,self.h=cfg["w"],cfg["h"]
        self.zoom=1.0; self.pan_x=0; self.pan_y=0
        self.layer_frames=[[{"name":"Фон","image":Image.new("RGBA",(self.w,self.h),cfg["bg"]),"visible":True},{"name":"Рисунок","image":Image.new("RGBA",(self.w,self.h),(0,0,0,0)),"visible":True}]]; self.active_layer=1; self.frames=[None]; self.compose_frame(0)
        self.index=0; self.project=None; self.undo_stack.clear(); self.redo_stack.clear(); self.dirty=True; self.selection_box=None
        self.canvas_info.config(text=f"{self.w} × {self.h}"); self.refresh(); self.render()
        self.refresh_layers(); self.status.set("Создан новый холст")

    def confirm_discard(self):
        if not self.dirty: return True
        answer=messagebox.askyesnocancel(APP_NAME,"Сохранить изменения проекта?",parent=self.root)
        return False if answer is None else (self.save() if answer else True)

    def close_project(self):
        if self.confirm_discard(): self.root.destroy()

    def save_as(self):
        return self.save(True)

    def save(self, save_as=False):
        path=(None if save_as else self.project) or filedialog.asksaveasfilename(defaultextension=".ffg",filetypes=[("FRAMEFORGE project","*.ffg")])
        if not path:return False
        try:
            write_project(path,self.w,self.h,self.fps.get(),self.layer_frames,self.index,self.active_layer,{"onion":self.onion.get()})
            self.project=path; self.dirty=False; self.status.set("Проект сохранён вместе со слоями")
            return True
        except Exception as exc:
            messagebox.showerror(APP_NAME,f"Не удалось сохранить проект: {exc}")
            return False

    def open(self,path=None):
        if path is None:
            path=filedialog.askopenfilename(filetypes=[("FRAMEFORGE project","*.ffg"),("Legacy project","*.json")])
        if not path or not self.confirm_discard():return False
        try:
            data,layers=read_project(path)
        except Exception as exc:
            messagebox.showerror(APP_NAME,f"Не удалось открыть проект: {exc}")
            return False
        self.playing=False
        self.w,self.h=data["width"],data["height"]
        self.layer_frames=layers
        self.frames=[None]*len(layers)
        for i in range(len(layers)):self.compose_frame(i)
        self.index=max(0,min(int(data.get("active_frame",0)),len(layers)-1))
        self.active_layer=max(0,min(int(data.get("active_layer",0)),len(layers[self.index])-1))
        self.fps.set(data.get("fps",12)); self.project=path if zipfile.is_zipfile(path) else None
        self.onion.set(data.get("settings",{}).get("onion",self.onion.get()))
        self.zoom=1.0; self.pan_x=self.pan_y=0
        self.last=None; self.selection_box=None; self.undo_stack.clear(); self.redo_stack.clear()
        self.dirty=False
        self.refresh(); self.render(); self.status.set("Проект загружен")
        return True

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
            frame_count=len(self.layer_frames)
            self.sync_frame_cache()
            if not frame_count:raise RuntimeError("В проекте нет кадров для экспорта.")
            fps=max(1,min(60,int(self.fps.get())))
            width=self.w+(self.w%2); height=self.h+(self.h%2)
            cmd=[ffmpeg,"-hide_banner","-loglevel","error","-y",
                 "-f","rawvideo","-pixel_format","rgb24",
                 "-video_size",f"{width}x{height}","-framerate",str(fps),
                 "-i","pipe:0","-an","-c:v",codec]
            cmd.extend(extra_args)
            cmd.extend(["-pix_fmt","yuv420p","-r",str(fps),
                        "-frames:v",str(frame_count),"-movflags","+faststart",path])
            proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            for i in range(frame_count):
                rgba=self.compose_frame(i)
                if rgba.size!=(self.w,self.h):
                    rgba=rgba.resize((self.w,self.h),Image.Resampling.LANCZOS)
                rgb=Image.new("RGBA",(self.w,self.h),self.user_settings.get("video_background","white"))
                rgb.alpha_composite(rgba)
                if width!=self.w or height!=self.h:
                    padded=Image.new("RGBA",(width,height),self.user_settings.get("video_background","white"))
                    padded.alpha_composite(rgb,(0,0))
                    rgb=padded
                proc.stdin.write(rgb.convert("RGB").tobytes())
            proc.stdin.close()
            code=proc.wait()
            if code!=0:raise RuntimeError("FFmpeg не смог собрать видео. Проверьте свободное место и повторите экспорт.")
            if not os.path.isfile(path) or os.path.getsize(path)==0:
                raise RuntimeError("Видео не было создано: выходной файл пуст.")
            self.status.set("Видео экспортировано: "+os.path.basename(path))
            messagebox.showinfo(APP_NAME,f"Анимация экспортирована в {extension.upper()}.\\nКадров: {frame_count} · FPS: {fps}",parent=self.root)
        except Exception as exc:
            if proc is not None and proc.poll() is None:
                try:
                    if proc.stdin:proc.stdin.close()
                except Exception:pass
                proc.kill();proc.wait()
            messagebox.showerror(APP_NAME,"Не удалось экспортировать видео.\\n"+str(exc),parent=self.root)

    def export_mp4(self):
        self.export_video("mp4","libx264",["-crf",str(self.user_settings.get("mp4_crf",18)),"-movflags","+faststart"])

    def export_webm(self):
        self.export_video("webm","libvpx-vp9",["-crf",str(self.user_settings.get("webm_crf",30)),"-b:v","0"])

    def return_to_menu(self):
        if not self.confirm_discard():return
        self.playing=False
        for widget in self.root.winfo_children():widget.destroy()
        MainMenu(self.root)

    def png(self):
        p=filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG","*.png")])
        if p:self.compose_frame(self.index).save(p)
    def gif(self):
        p=filedialog.asksaveasfilename(defaultextension=".gif",filetypes=[("GIF","*.gif")])
        if p:
            ims=[self.compose_frame(i) for i in range(len(self.layer_frames))]
            ims[0].save(p,save_all=True,append_images=ims[1:],duration=max(1,int(1000/max(1,self.fps.get()))),loop=0,disposal=2)
    def png_sequence(self):
        p=filedialog.asksaveasfilename(defaultextension=".zip",filetypes=[("ZIP archive","*.zip")])
        if p:
            with zipfile.ZipFile(p,"w",zipfile.ZIP_DEFLATED) as z:
                for i in range(len(self.layer_frames)):
                    im=self.compose_frame(i)
                    import io
                    b=io.BytesIO(); im.save(b,format="PNG"); z.writestr(f"frame_{i+1:05d}.png",b.getvalue())
    def sprite_sheet(self):
        cols=max(1,int(simpledialog.askinteger(APP_NAME,"Количество колонок:",initialvalue=5,minvalue=1,maxvalue=50) or 5))
        rows=(len(self.frames)+cols-1)//cols
        if self.w*cols>16000 or self.h*rows>16000:
            messagebox.showerror(APP_NAME,"Sprite Sheet слишком большой. Уменьшите число колонок."); return
        sheet=Image.new("RGBA",(self.w*cols,self.h*rows),(0,0,0,0))
        for i in range(len(self.layer_frames)):
            im=self.compose_frame(i); sheet.alpha_composite(im,((i%cols)*self.w,(i//cols)*self.h))
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
        app=FrameForge(self.root)
        if not app.open(path):return
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
        win=tk.Toplevel(self.root);win.title("Настройки FRAMEFORGE");win.geometry("780x580")
        win.minsize(620,460);win.configure(bg="#20242c");win.transient(self.root);win.grab_set()
        tk.Label(win,text="Настройки",bg="#20242c",fg="#f1f5fc",font=("Segoe UI",20,"bold")).pack(anchor="w",padx=20,pady=16)
        tabs=ttk.Notebook(win);tabs.pack(fill="both",expand=True,padx=20,pady=6)
        values={}; specs={}
        def page(title):
            p=ttk.Frame(tabs,padding=18);tabs.add(p,text=title);p.columnconfigure(0,weight=1);return p
        def field(p,key,title,default,options=None,bounds=None):
            row=len(p.grid_slaves())//2
            var=(tk.BooleanVar if isinstance(default,bool) else tk.IntVar if isinstance(default,int) else tk.StringVar)(value=self.settings.get(key,default))
            values[key]=var;specs[key]=(default,options,bounds)
            ttk.Label(p,text=title).grid(row=row,column=0,sticky="w",pady=9)
            if isinstance(default,bool):w=ttk.Checkbutton(p,variable=var)
            elif options:w=ttk.Combobox(p,textvariable=var,values=options,state="readonly",width=24)
            else:w=ttk.Spinbox(p,textvariable=var,from_=bounds[0],to=bounds[1],width=12)
            w.grid(row=row,column=1,sticky="e",padx=8)
        p=page("Общие")
        field(p,"confirm_exit","Подтверждение выхода",True)
        field(p,"show_tips","Советы в главном меню",True)
        p=page("Рисование")
        field(p,"default_canvas","Размер нового холста","HD 1280 × 720",list(PRESETS))
        field(p,"brush_size","Начальная толщина кисти (px)",8,bounds=(1,100))
        field(p,"brush_opacity","Начальная непрозрачность (%)",100,bounds=(1,100))
        field(p,"fill_gap","Допустимый разрыв контура (px)",0,bounds=(0,10))
        p=page("Холст")
        field(p,"zoom_step","Шаг приближения (%)",12,bounds=(5,30))
        field(p,"checker_tile","Размер клетки прозрачности (px)",16,bounds=(8,64))
        field(p,"checker_theme","Фон прозрачности","light",["light","dark"])
        p=page("Анимация")
        field(p,"default_fps","FPS нового проекта",12,bounds=(1,60))
        field(p,"onion_skin","Включать кальку",True)
        field(p,"onion_opacity","Непрозрачность кальки (%)",22,bounds=(5,80))
        p=page("Производительность")
        field(p,"preview_quality","Качество предпросмотра","balanced",["fast","balanced","high"])
        field(p,"history_steps","Максимум действий в истории",40,bounds=(5,100))
        field(p,"history_mb","Лимит памяти истории (МБ)",128,bounds=(32,512))
        p=page("Экспорт")
        field(p,"mp4_crf","MP4 CRF (меньше — лучше качество)",18,bounds=(0,51))
        field(p,"webm_crf","WebM CRF (меньше — лучше качество)",30,bounds=(0,63))
        field(p,"video_background","Фон прозрачных областей видео","white",["white","black"])
        def reset():
            for key,var in values.items():var.set(specs[key][0])
        def save():
            try:
                result={}
                for key,var in values.items():
                    default,options,bounds=specs[key];v=var.get()
                    if bounds and not bounds[0]<=v<=bounds[1]:raise ValueError(key)
                    if options and v not in options:raise ValueError(key)
                    result[key]=v
                self.settings.update(result);self.save_settings()
            except Exception as exc:
                messagebox.showerror(APP_NAME,"Не удалось сохранить настройки: "+str(exc),parent=win);return
            win.destroy()
        bar=ttk.Frame(win,padding=12);bar.pack(fill="x")
        ttk.Button(bar,text="По умолчанию",command=reset).pack(side="left")
        ttk.Button(bar,text="Отмена",command=win.destroy).pack(side="right",padx=5)
        ttk.Button(bar,text="Применить и закрыть",command=save).pack(side="right")
        tk.Label(win,text="Параметры применяются при следующем открытии редактора.",bg="#20242c",fg="#b0b8c8").pack(pady=(0,10))

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
        c.create_rectangle(0,0,640,500,fill="#111827",outline="")
        c.create_oval(95,30,545,480,outline="#24143c",width=3)
        c.create_oval(125,60,515,450,outline="#321b52",width=2)
        # Panda mascot and clapperboard logo
        c.create_oval(228,63,302,137,fill="#090711",outline="#70aaff",width=3)
        c.create_oval(338,63,412,137,fill="#090711",outline="#a65bff",width=3)
        c.create_oval(226,82,414,240,fill="#f6f1fc",outline="#8cbcff",width=4)
        c.create_oval(235,139,309,211,fill="#11101a")
        c.create_oval(331,139,405,211,fill="#11101a")
        c.create_oval(260,163,286,189,fill="#42dc88")
        c.create_oval(354,163,380,189,fill="#a65bff")
        c.create_oval(309,205,331,220,fill="#171321")
        c.create_rectangle(157,250,483,354,fill="#211735",outline="#a65bff",width=5)
        c.create_polygon(157,250,483,250,461,213,135,213,fill="#315f98",outline="#a9ceff",width=3)
        for xx in (165,245,325,405):
            c.create_polygon(xx,216,xx+34,216,xx+56,247,xx+22,247,fill="#f0e5ff")
        c.create_polygon(286,276,286,330,337,303,fill="#8dbbff")
        c.create_text(320,390,text="FRAMEFORGE",fill="#f6efff",font=("Segoe UI",29,"bold"))
        c.create_text(320,422,text="DRAW  •  ANIMATE  •  CREATE",fill="#b7a4d2",font=("Segoe UI",10,"bold"))
        c.create_rectangle(105,454,535,466,fill="#202e43",outline="#42658e")
        c.create_rectangle(107,456,107+426*self.progress,464,fill="#a65bff",outline="")
        c.create_text(320,481,text="Подготавливаем рабочее пространство...",
                      fill="#b8cde8",font=("Segoe UI",9))

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
