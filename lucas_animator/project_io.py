import io, json, os, tempfile, zipfile
from PIL import Image

def read_project(path):
    def decode(source, size):
        with Image.open(source) as im:
            if im.size != size: raise ValueError("Размер слоя не соответствует холсту")
            return im.convert("RGBA")
    def validate(data):
        w,h=data["width"],data["height"]
        if type(w)!=int or type(h)!=int or not (1<=w<=16384 and 1<=h<=16384): raise ValueError("Некорректный размер холста")
        if not isinstance(data["frames"],list) or not data["frames"]: raise ValueError("Нет кадров")
        fps=data.get("fps",12)
        if type(fps)!=int or not 1<=fps<=60: raise ValueError("Некорректный FPS")
        for key in ("active_frame","active_layer"): int(data.get(key,0))
        if not isinstance(data.get("settings",{}),dict): raise ValueError("Некорректные настройки")
        return w,h
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            if z.testzip() is not None: raise ValueError("Ошибка CRC архива")
            data=json.loads(z.read("project.json"))
            size=validate(data)
            if data.get("format","FRAMEFORGE")!="FRAMEFORGE": raise ValueError("Неизвестный формат")
            frames=[]
            for frame in data["frames"]:
                if isinstance(frame,str):
                    frames.append([dict(name="Рисунок",visible=True,opacity=100,image=decode(io.BytesIO(z.read(frame)),size))])
                    continue
                layers=[]
                for l in frame["layers"]:
                    opacity=l.get("opacity",100)
                    if not isinstance(opacity,(int,float)) or not 0<=opacity<=100: raise ValueError("Некорректная прозрачность")
                    if not isinstance(l["name"],str): raise ValueError("Некорректное имя слоя")
                    layers.append(dict(name=l["name"],visible=bool(l.get("visible",True)),opacity=opacity,image=decode(io.BytesIO(z.read(l["file"])),size)))
                if not layers: raise ValueError("Пустой кадр")
                frames.append(layers)
            return data,frames
    if not str(path).lower().endswith(".json"): raise ValueError("Повреждённый архив FFG")
    with open(path,encoding="utf-8") as f: data=json.load(f)
    size=validate(data)
    folder=os.path.join(os.path.dirname(path),data["folder"])
    return data,[[dict(name="Рисунок (старый проект)",visible=True,opacity=100,image=decode(os.path.join(folder,n),size))] for n in data["frames"]]

def write_project(path,w,h,fps,frames,index,active,settings):
    path=os.path.abspath(path)
    fd,tmp=tempfile.mkstemp(prefix=".frameforge-",suffix=".ffg",dir=os.path.dirname(path))
    os.close(fd)
    try:
        manifest=dict(format="FRAMEFORGE",version="0.10.1",width=w,height=h,fps=fps,active_frame=index,active_layer=active,settings=settings,frames=[])
        with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED) as z:
            for fi,frame in enumerate(frames):
                entry=dict(layers=[])
                for li,l in enumerate(frame):
                    name=f"frames/{fi:05d}/layer_{li:03d}.png"
                    buf=io.BytesIO()
                    l["image"].save(buf,format="PNG")
                    z.writestr(name,buf.getvalue())
                    entry["layers"].append(dict(name=l["name"],visible=l["visible"],opacity=l.get("opacity",100),file=name))
                manifest["frames"].append(entry)
            z.writestr("project.json",json.dumps(manifest,ensure_ascii=False))
        read_project(tmp)
        with open(tmp,"rb+") as f: os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
