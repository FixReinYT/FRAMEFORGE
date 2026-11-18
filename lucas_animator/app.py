import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageDraw, ImageTk

APP_NAME = "FRAMEFORGE"
VERSION = "0.2.0"

BG = "#171b24"
PANEL = "#202633"
PANEL_ALT = "#252d3b"
BORDER = "#354052"
TEXT = "#e8edf5"
MUTED = "#9aa8bb"
ACCENT = "#4f9cf9"
ACCENT_HOVER = "#70adff"


class FrameForge:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} {VERSION}")
        self.root.geometry("1440x900")
        self.root.minsize(1050, 700)

        self.w, self.h = 1280, 720
        self.frames = [Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))]
        self.index = 0
        self.fps = tk.IntVar(value=12)
        self.size = tk.IntVar(value=8)
        self.color = "#202633"
        self.tool = tk.StringVar(value="brush")
        self.onion = tk.BooleanVar(value=True)
        self.playing = False
        self.project = None
        self.last = None
        self.photo = None
        self.origin = (0, 0, 1)
        self.status = tk.StringVar(value="Готово")
        self.frame_buttons = []

        self.setup_style()
        self.build()
        self.bind_shortcuts()
        self.refresh()
        self.render()

    def setup_style(self):
        self.root.configure(bg=BG)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Alt.TFrame", background=PANEL_ALT)
        style.configure("TLabel", background=PANEL, foreground=TEXT)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Title.TLabel", background=BG, foreground=TEXT,
                        font=("Segoe UI", 15, "bold"))
        style.configure("Section.TLabel", background=PANEL, foreground=MUTED,
                        font=("Segoe UI", 9, "bold"))
        style.configure("TButton", background=PANEL_ALT, foreground=TEXT,
                        borderwidth=0, padding=(11, 8))
        style.map("TButton", background=[("active", "#35445a"), ("pressed", "#26384f")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                        font=("Segoe UI", 10, "bold"), padding=(13, 9))
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER)])
        style.configure("Tool.TRadiobutton", background=PANEL, foreground=TEXT,
                        padding=(10, 9), indicatorcolor=PANEL_ALT)
        style.map("Tool.TRadiobutton",
                  background=[("selected", "#263e5c"), ("active", PANEL_ALT)],
                  foreground=[("selected", "#ffffff")])
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        style.configure("TSpinbox", fieldbackground=PANEL_ALT, foreground=TEXT,
                        arrowcolor=TEXT, bordercolor=BORDER)
        style.configure("Horizontal.TScale", background=PANEL, troughcolor=PANEL_ALT)

    def panel(self, parent, width=None):
        frame = tk.Frame(parent, bg=PANEL, highlightthickness=1,
                         highlightbackground=BORDER, width=width)
        if width:
            frame.pack_propagate(False)
        return frame

    def section(self, parent, text):
        ttk.Label(parent, text=text.upper(), style="Section.TLabel").pack(
            anchor="w", padx=14, pady=(16, 8))

    def build(self):
        header = tk.Frame(self.root, bg="#11151d", height=66)
        header.pack(fill="x")
        header.pack_propagate(False)

        brand = tk.Frame(header, bg="#11151d")
        brand.pack(side="left", padx=20)
        tk.Label(brand, text="FRAME", bg="#11151d", fg=TEXT,
                 font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(brand, text="FORGE", bg="#11151d", fg=ACCENT,
                 font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(brand, text="  0.2", bg="#11151d", fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 0))

        ttk.Button(header, text="Новый проект", command=self.new).pack(
            side="left", padx=(24, 5), pady=14)
        ttk.Button(header, text="Открыть", command=self.open).pack(
            side="left", padx=5, pady=14)
        ttk.Button(header, text="Сохранить", command=self.save).pack(
            side="left", padx=5, pady=14)
        ttk.Button(header, text="PNG", command=self.png).pack(
            side="left", padx=(18, 5), pady=14)
        ttk.Button(header, text="GIF", command=self.gif).pack(
            side="left", padx=5, pady=14)
        tk.Label(header, text="2D ANIMATION WORKSPACE", bg="#11151d",
                 fg="#718096", font=("Segoe UI", 9, "bold")).pack(
                     side="right", padx=22)

        workspace = tk.Frame(self.root, bg=BG)
        workspace.pack(fill="both", expand=True, padx=10, pady=(10, 8))

        left = self.panel(workspace, 190)
        left.pack(side="left", fill="y")
        self.section(left, "Инструменты")
        for label, value in [("✎  Кисть", "brush"), ("▱  Ластик", "eraser")]:
            ttk.Radiobutton(left, text=label, value=value, variable=self.tool,
                            style="Tool.TRadiobutton").pack(fill="x", padx=8, pady=2)

        self.section(left, "Параметры кисти")
        color_row = tk.Frame(left, bg=PANEL)
        color_row.pack(fill="x", padx=14, pady=(2, 12))
        tk.Label(color_row, text="Цвет", bg=PANEL, fg=MUTED).pack(side="left")
        self.color_swatch = tk.Button(color_row, bg=self.color, activebackground=self.color,
                                      width=5, relief="flat", bd=0, command=self.pick)
        self.color_swatch.pack(side="right", ipady=7)
        tk.Label(left, text="Размер", bg=PANEL, fg=MUTED).pack(anchor="w", padx=14)
        self.size_value = tk.Label(left, text="8 px", bg=PANEL, fg=TEXT,
                                   font=("Segoe UI", 10, "bold"))
        self.size_value.pack(anchor="e", padx=14)
        ttk.Scale(left, from_=1, to=60, orient="horizontal", variable=self.size,
                  command=self.change_size).pack(fill="x", padx=14, pady=(3, 12))
        ttk.Checkbutton(left, text="Луковая шелуха", variable=self.onion,
                        command=self.render).pack(anchor="w", padx=14, pady=8)

        center = tk.Frame(workspace, bg=BG)
        center.pack(side="left", fill="both", expand=True, padx=10)
        canvas_head = tk.Frame(center, bg=PANEL, height=42)
        canvas_head.pack(fill="x")
        canvas_head.pack_propagate(False)
        tk.Label(canvas_head, text="ХОЛСТ", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=14)
        self.canvas_info = tk.Label(canvas_head, text="1280 × 720",
                                    bg=PANEL, fg=MUTED)
        self.canvas_info.pack(side="right", padx=14)
        canvas_shell = tk.Frame(center, bg="#11151d", padx=12, pady=12)
        canvas_shell.pack(fill="both", expand=True, pady=(6, 0))
        self.canvas = tk.Canvas(canvas_shell, bg="#171c25", highlightthickness=0,
                                cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda event: self.render())
        self.canvas.bind("<Button-1>", self.start)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", lambda event: setattr(self, "last", None))

        right = self.panel(workspace, 220)
        right.pack(side="right", fill="y")
        self.section(right, "Анимация")
        tk.Label(right, text="Кадров в секунду", bg=PANEL, fg=MUTED).pack(
            anchor="w", padx=14)
        fps_row = tk.Frame(right, bg=PANEL)
        fps_row.pack(fill="x", padx=14, pady=(6, 12))
        ttk.Spinbox(fps_row, from_=1, to=60, textvariable=self.fps,
                    width=7).pack(side="left")
        tk.Label(fps_row, text="FPS", bg=PANEL, fg=MUTED).pack(side="left", padx=8)

        self.playbtn = ttk.Button(right, text="▶  Воспроизвести",
                                  style="Accent.TButton", command=self.play)
        self.playbtn.pack(fill="x", padx=12, pady=(4, 12))
        self.section(right, "Кадры")
        for label, fn in [("+  Добавить кадр", self.add),
                          ("▣  Дублировать", self.duplicate),
                          ("−  Удалить кадр", self.delete)]:
            ttk.Button(right, text=label, command=fn).pack(
                fill="x", padx=12, pady=3)
        ttk.Separator(right).pack(fill="x", padx=12, pady=14)
        nav = tk.Frame(right, bg=PANEL)
        nav.pack(fill="x", padx=12)
        ttk.Button(nav, text="←", command=lambda: self.select(self.index - 1),
                   width=5).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(nav, text="→", command=lambda: self.select(self.index + 1),
                   width=5).pack(side="left", expand=True, fill="x", padx=(3, 0))
        self.counter = tk.Label(right, text="КАДР 1 / 1", bg=PANEL, fg=TEXT,
                                font=("Segoe UI", 11, "bold"))
        self.counter.pack(pady=(14, 4))
        tk.Label(right, text="Предпросмотр циклический", bg=PANEL,
                 fg=MUTED, font=("Segoe UI", 8)).pack()

        timeline = self.panel(self.root)
        timeline.pack(fill="x", padx=10, pady=(0, 8))
        timeline_head = tk.Frame(timeline, bg=PANEL)
        timeline_head.pack(fill="x")
        tk.Label(timeline_head, text="ТАЙМЛАЙН", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=14, pady=10)
        self.timeline_hint = tk.Label(timeline_head, text="Выберите кадр для редактирования",
                                      bg=PANEL, fg=MUTED)
        self.timeline_hint.pack(side="right", padx=14)
        self.timeline = tk.Frame(timeline, bg="#1a202b")
        self.timeline.pack(fill="x", padx=8, pady=(0, 8))

        footer = tk.Frame(self.root, bg="#11151d", height=27)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(footer, textvariable=self.status, bg="#11151d", fg=MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=12)
        tk.Label(footer, text="FRAMEFORGE  •  THELUCASSDEN",
                 bg="#11151d", fg="#65748a", font=("Segoe UI", 8)).pack(
                     side="right", padx=12)

    def bind_shortcuts(self):
        self.root.bind("<Control-n>", lambda event: self.new())
        self.root.bind("<Control-o>", lambda event: self.open())
        self.root.bind("<Control-s>", lambda event: self.save())
        self.root.bind("<space>", lambda event: self.play())

    def change_size(self, value):
        self.size.set(int(float(value)))
        self.size_value.config(text=f"{self.size.get()} px")

    def geometry(self):
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        scale = min((cw - 30) / self.w, (ch - 30) / self.h)
        return scale, (cw - self.w * scale) / 2, (ch - self.h * scale) / 2

    def render(self):
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        scale, x, y = self.geometry()
        width, height = max(1, int(self.w * scale)), max(1, int(self.h * scale))
        tile = max(8, int(16 * scale))
        for yy in range(0, height, tile):
            for xx in range(0, width, tile):
                shade = "#dce1e8" if ((xx // tile) + (yy // tile)) % 2 == 0 else "#c7ced8"
                self.canvas.create_rectangle(x + xx, y + yy,
                    x + min(width, xx + tile), y + min(height, yy + tile),
                    fill=shade, outline=shade)

        image = self.frames[self.index].copy()
        if self.onion.get() and self.index > 0:
            previous = self.frames[self.index - 1]
            tinted = Image.new("RGBA", previous.size, (255, 75, 95, 0))
            tinted.putalpha(previous.getchannel("A").point(lambda a: int(a * 0.25)))
            tinted.alpha_composite(image)
            image = tinted

        self.photo = ImageTk.PhotoImage(image.resize(
            (width, height), Image.Resampling.LANCZOS))
        self.canvas.create_image(x, y, image=self.photo, anchor="nw")
        self.canvas.create_rectangle(x, y, x + width, y + height,
                                     outline="#718096", width=1)
        self.origin = (x, y, scale)

    def coords(self, event):
        x, y, scale = self.origin
        return (max(0, min(self.w - 1, int((event.x - x) / scale))),
                max(0, min(self.h - 1, int((event.y - y) / scale))))

    def start(self, event):
        if not self.playing:
            self.last = self.coords(event)
            self.draw(event)

    def draw(self, event):
        if self.last is None or self.playing:
            return
        point = self.coords(event)
        draw = ImageDraw.Draw(self.frames[self.index])
        radius = max(1, self.size.get() // 2)
        color = self.color if self.tool.get() == "brush" else (0, 0, 0, 0)
        draw.line([self.last, point], fill=color, width=self.size.get())
        draw.ellipse((point[0] - radius, point[1] - radius,
                      point[0] + radius, point[1] + radius), fill=color)
        self.last = point
        self.render()

    def pick(self):
        selected = colorchooser.askcolor(self.color, title="Цвет кисти")[1]
        if selected:
            self.color = selected
            self.color_swatch.configure(bg=selected, activebackground=selected)

    def refresh(self):
        for widget in self.timeline.winfo_children():
            widget.destroy()
        self.frame_buttons = []
        for i in range(len(self.frames)):
            selected = i == self.index
            button = tk.Button(
                self.timeline, text=f"КАДР\n{i + 1}",
                command=lambda n=i: self.select(n),
                bg="#284d75" if selected else "#252d3b",
                fg="#ffffff" if selected else "#b9c5d5",
                activebackground="#37699b", activeforeground="#ffffff",
                relief="flat", bd=0, width=9, height=3,
                font=("Segoe UI", 9, "bold"),
                highlightthickness=1,
                highlightbackground=ACCENT if selected else BORDER)
            button.pack(side="left", padx=4, pady=7)
            self.frame_buttons.append(button)
        self.counter.config(text=f"КАДР  {self.index + 1} / {len(self.frames)}")
        self.timeline_hint.config(text=f"{len(self.frames)} кадр(ов)  •  {self.fps.get()} FPS")

    def select(self, number):
        self.index = max(0, min(len(self.frames) - 1, number))
        self.refresh()
        self.render()
        self.status.set(f"Выбран кадр {self.index + 1}")

    def add(self):
        self.frames.insert(self.index + 1, Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0)))
        self.select(self.index + 1)
        self.status.set("Добавлен пустой кадр")

    def duplicate(self):
        self.frames.insert(self.index + 1, self.frames[self.index].copy())
        self.select(self.index + 1)
        self.status.set("Кадр дублирован")

    def delete(self):
        if len(self.frames) == 1:
            self.frames[0] = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        else:
            self.frames.pop(self.index)
            self.index = min(self.index, len(self.frames) - 1)
        self.refresh()
        self.render()
        self.status.set("Кадр удалён")

    def play(self):
        self.playing = not self.playing
        self.playbtn.configure(text="■  Остановить" if self.playing else "▶  Воспроизвести")
        self.status.set("Предпросмотр анимации" if self.playing else "Предпросмотр остановлен")
        if self.playing:
            self.tick()

    def tick(self):
        if not self.playing:
            return
        self.index = (self.index + 1) % len(self.frames)
        self.refresh()
        self.render()
        self.root.after(max(1, int(1000 / max(1, self.fps.get()))), self.tick)

    def new(self):
        if messagebox.askyesno(APP_NAME, "Создать новый проект? Несохранённые изменения будут потеряны."):
            self.playing = False
            self.playbtn.configure(text="▶  Воспроизвести")
            self.frames = [Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))]
            self.index = 0
            self.project = None
            self.refresh()
            self.render()
            self.status.set("Создан новый проект")

    def save(self):
        path = self.project or filedialog.asksaveasfilename(
            defaultextension=".ffg",
            filetypes=[("FRAMEFORGE project", "*.ffg")],
            title="Сохранить проект")
        if not path:
            return
        folder = path + ".frames"
        os.makedirs(folder, exist_ok=True)
        names = []
        for i, frame in enumerate(self.frames):
            name = f"frame_{i:05d}.png"
            frame.save(os.path.join(folder, name))
            names.append(name)
        with open(path, "w", encoding="utf-8") as file:
            json.dump({"width": self.w, "height": self.h, "fps": self.fps.get(),
                       "folder": os.path.basename(folder), "frames": names},
                      file, indent=2)
        self.project = path
        self.status.set(f"Проект сохранён: {os.path.basename(path)}")
        messagebox.showinfo(APP_NAME, "Проект успешно сохранён.")

    def open(self):
        path = filedialog.askopenfilename(
            filetypes=[("FRAMEFORGE project", "*.ffg")],
            title="Открыть проект")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(file)
            folder = os.path.join(os.path.dirname(path), data["folder"])
            loaded = [Image.open(os.path.join(folder, name)).convert("RGBA")
                      for name in data["frames"]]
            self.frames = loaded
            self.w, self.h = data["width"], data["height"]
            self.fps.set(data.get("fps", 12))
            self.index = 0
            self.project = path
            self.canvas_info.config(text=f"{self.w} × {self.h}")
            self.refresh()
            self.render()
            self.status.set(f"Открыт проект: {os.path.basename(path)}")
        except Exception as error:
            messagebox.showerror(APP_NAME, f"Не удалось открыть проект:\n{error}")

    def png(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG image", "*.png")],
            title="Экспорт кадра в PNG")
        if path:
            self.frames[self.index].save(path)
            self.status.set("Кадр экспортирован в PNG")

    def gif(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".gif", filetypes=[("GIF animation", "*.gif")],
            title="Экспорт анимации в GIF")
        if path:
            images = [frame.convert("RGBA") for frame in self.frames]
            images[0].save(path, save_all=True, append_images=images[1:],
                           duration=max(1, int(1000 / max(1, self.fps.get()))),
                           loop=0, disposal=2)
            self.status.set("Анимация экспортирована в GIF")


if __name__ == "__main__":
    root = tk.Tk()
    FrameForge(root)
    root.mainloop()
