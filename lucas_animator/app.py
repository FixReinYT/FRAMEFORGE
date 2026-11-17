import json, os, tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageDraw, ImageTk

APP_NAME = "FRAMEFORGE"
VERSION = "0.1.0"

class FrameForge:
    def __init__(self, root):
        self.root=root
        root.title(f"{APP_NAME} {VERSION}")
        root.geometry("1280x820")
        self.w,self.h=1280,720
        self.frames=[Image.new("RGBA",(self.w,self.h),(0,0,0,0))]
        self.index=0
        self.fps=tk.IntVar(value=12)
        self.size=tk.IntVar(value=8)
        self.color="#171717"
        self.tool=tk.StringVar(value="brush")
        self.onion=tk.BooleanVar(value=True)
        self.playing=False
        self.project=None
        self.last=None
        self.photo=None
        self.build()
        self.refresh()
        self.render()

    def build(self):
        self.root.configure(bg="#24272d")
        top=tk.Frame(self.root,bg="#1b1e23"); top.pack(fill="x")
        tk.Label(top,text="FRAMEFORGE",bg="#1b1e23",fg="white",font=("Segoe UI",14,"bold")).pack(side="left",padx=14,pady=10)
        for name,fn in [("Новый",self.new),("Открыть",self.open),("Сохранить",self.save),("Экспорт PNG",self.png),("Экспорт GIF",self.gif)]:
            tk.Button(top,text=name,command=fn).pack(side="left",padx=3,pady=6)
        body=tk.Frame(self.root,bg="#24272d"); body.pack(fill="both",expand=True,padx=8,pady=8)
        left=tk.Frame(body,bg="#30343c",width=160); left.pack(side="left",fill="y"); left.pack_propagate(False)
        tk.Label(left,text="ИНСТРУМЕНТЫ",bg="#30343c",fg="white").pack(pady=12)
        for label,val in [("Кисть","brush"),("Ластик","eraser")]:
            tk.Radiobutton(left,text=label,value=val,variable=self.tool,bg="#30343c",fg="white",selectcolor="#46505d").pack(anchor="w",padx=12)
        tk.Button(left,text="Цвет кисти",command=self.pick).pack(fill="x",padx=10,pady=12)
        tk.Label(left,text="Размер кисти",bg="#30343c",fg="white").pack()
        tk.Scale(left,from_=1,to=60,orient="horizontal",variable=self.size,bg="#30343c",fg="white").pack(fill="x")
        ttk.Checkbutton(left,text="Луковая шелуха",variable=self.onion,command=self.render).pack(pady=12)
        center=tk.Frame(body,bg="#24272d"); center.pack(side="left",fill="both",expand=True,padx=8)
        self.canvas=tk.Canvas(center,bg="#17191d",highlightthickness=0,cursor="crosshair"); self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",lambda e:self.render())
        self.canvas.bind("<Button-1>",self.start); self.canvas.bind("<B1-Motion>",self.draw); self.canvas.bind("<ButtonRelease-1>",lambda e:setattr(self,"last",None))
        right=tk.Frame(body,bg="#30343c",width=180); right.pack(side="right",fill="y"); right.pack_propagate(False)
        tk.Label(right,text="АНИМАЦИЯ",bg="#30343c",fg="white").pack(pady=12)
        tk.Label(right,text="FPS",bg="#30343c",fg="white").pack()
        tk.Spinbox(right,from_=1,to=60,textvariable=self.fps,width=6).pack(pady=5)
        for label,fn in [("＋ Добавить кадр",self.add),("⧉ Дублировать",self.duplicate),("− Удалить",self.delete),("◀ Назад",lambda:self.select(self.index-1)),("Вперёд ▶",lambda:self.select(self.index+1))]:
            tk.Button(right,text=label,command=fn).pack(fill="x",padx=8,pady=4)
        self.playbtn=tk.Button(right,text="▶ Воспроизвести",command=self.play); self.playbtn.pack(fill="x",padx=8,pady=15)
        self.counter=tk.Label(right,text="1 / 1",bg="#30343c",fg="white",font=("Segoe UI",14,"bold")); self.counter.pack()
        bottom=tk.Frame(self.root,bg="#1b1e23"); bottom.pack(fill="x",padx=8,pady=(0,8))
        tk.Label(bottom,text="ТАЙМЛАЙН",bg="#1b1e23",fg="#aeb8c5").pack(anchor="w",padx=8,pady=5)
        self.timeline=tk.Frame(bottom,bg="#252a31"); self.timeline.pack(fill="x",padx=4,pady=4)

    def geometry(self):
        cw,ch=max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())
        s=min((cw-30)/self.w,(ch-30)/self.h)
        return s,(cw-self.w*s)/2,(ch-self.h*s)/2

    def render(self):
        if not hasattr(self,"canvas"): return
        self.canvas.delete("all")
        s,x,y=self.geometry(); w,h=int(self.w*s),int(self.h*s)
        self.canvas.create_rectangle(x,y,x+w,y+h,fill="white",outline="#9aa2ad")
        im=self.frames[self.index].copy()
        if self.onion.get() and self.index>0:
            prev=self.frames[self.index-1]
            tint=Image.new("RGBA",prev.size,(255,70,70,0))
            tint.putalpha(prev.getchannel("A").point(lambda a:int(a*.25)))
            tint.alpha_composite(im); im=tint
        self.photo=ImageTk.PhotoImage(im.resize((max(1,w),max(1,h)),Image.Resampling.LANCZOS))
        self.canvas.create_image(x,y,image=self.photo,anchor="nw")
        self.canvas.create_rectangle(x,y,x+w,y+h,outline="#9aa2ad")
        self.origin=(x,y,s)

    def coords(self,e):
        x,y,s=self.origin
        return max(0,min(self.w-1,int((e.x-x)/s))),max(0,min(self.h-1,int((e.y-y)/s)))

    def start(self,e):
        if not self.playing:
            self.last=self.coords(e); self.draw(e)

    def draw(self,e):
        if self.last is None or self.playing:return
        p=self.coords(e); d=ImageDraw.Draw(self.frames[self.index]); r=self.size.get()/2
        c=self.color if self.tool.get()=="brush" else (0,0,0,0)
        d.line([self.last,p],fill=c,width=self.size.get())
        d.ellipse((p[0]-r,p[1]-r,p[0]+r,p[1]+r),fill=c)
        self.last=p; self.render()

    def pick(self):
        c=colorchooser.askcolor(self.color)[1]
        if c:self.color=c

    def refresh(self):
        for x in self.timeline.winfo_children():x.destroy()
        for i in range(len(self.frames)):
            tk.Button(self.timeline,text=f"Кадр {i+1}",bg="#416d9e" if i==self.index else "#3a414b",fg="white",command=lambda n=i:self.select(n)).pack(side="left",padx=3,pady=6)
        self.counter.config(text=f"{self.index+1} / {len(self.frames)}")

    def select(self,n):
        self.index=max(0,min(len(self.frames)-1,n)); self.refresh(); self.render()
    def add(self):
        self.frames.insert(self.index+1,Image.new("RGBA",(self.w,self.h),(0,0,0,0))); self.select(self.index+1)
    def duplicate(self):
        self.frames.insert(self.index+1,self.frames[self.index].copy()); self.select(self.index+1)
    def delete(self):
        if len(self.frames)==1:self.frames[0]=Image.new("RGBA",(self.w,self.h),(0,0,0,0))
        else:self.frames.pop(self.index); self.index=min(self.index,len(self.frames)-1)
        self.refresh(); self.render()
    def play(self):
        self.playing=not self.playing; self.playbtn.config(text="■ Стоп" if self.playing else "▶ Воспроизвести")
        if self.playing:self.tick()
    def tick(self):
        if not self.playing:return
        self.index=(self.index+1)%len(self.frames); self.refresh(); self.render()
        self.root.after(max(1,int(1000/max(1,self.fps.get()))),self.tick)
    def new(self):
        if messagebox.askyesno(APP_NAME,"Создать новый проект?"):
            self.frames=[Image.new("RGBA",(self.w,self.h),(0,0,0,0))];self.index=0;self.project=None;self.refresh();self.render()
    def save(self):
        path=self.project or filedialog.asksaveasfilename(defaultextension=".ffg",filetypes=[("FRAMEFORGE project","*.ffg")])
        if not path:return
        folder=path+".frames";os.makedirs(folder,exist_ok=True); names=[]
        for i,im in enumerate(self.frames):
            n=f"frame_{i:05d}.png";im.save(os.path.join(folder,n));names.append(n)
        with open(path,"w",encoding="utf-8") as f:json.dump({"width":self.w,"height":self.h,"fps":self.fps.get(),"folder":os.path.basename(folder),"frames":names},f,indent=2)
        self.project=path;messagebox.showinfo(APP_NAME,"Проект сохранён.")
    def open(self):
        path=filedialog.askopenfilename(filetypes=[("FRAMEFORGE project","*.ffg")])
        if not path:return
        try:
            with open(path,encoding="utf-8") as f:data=json.load(f)
            folder=os.path.join(os.path.dirname(path),data["folder"])
            self.frames=[Image.open(os.path.join(folder,n)).convert("RGBA") for n in data["frames"]]
            self.w,self.h=data["width"],data["height"];self.fps.set(data.get("fps",12));self.index=0;self.project=path;self.refresh();self.render()
        except Exception as e:messagebox.showerror(APP_NAME,str(e))
    def png(self):
        p=filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG","*.png")])
        if p:self.frames[self.index].save(p)
    def gif(self):
        p=filedialog.asksaveasfilename(defaultextension=".gif",filetypes=[("GIF","*.gif")])
        if p:
            ims=[f.convert("RGBA") for f in self.frames];ims[0].save(p,save_all=True,append_images=ims[1:],duration=max(1,int(1000/max(1,self.fps.get()))),loop=0,disposal=2)

if __name__=="__main__":
    root=tk.Tk();FrameForge(root);root.mainloop()
