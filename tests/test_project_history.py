import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lucas_animator"))
from project_io import read_project, write_project
from app import FrameForge

class ProjectTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"Проект # 1.ffg"
            im=Image.new("RGBA",(8,8),(12,34,56,78))
            frames=[[dict(name="Фон",visible=False,opacity=45,image=im),dict(name="Рисунок",visible=True,image=im.copy())] for _ in range(3)]
            write_project(p,8,8,24,frames,2,1,{"onion":False})
            data,out=read_project(p)
            self.assertEqual((data["fps"],data["active_frame"],data["settings"]),(24,2,{"onion":False}))
            self.assertEqual(len(out),3)
            for frame in out:
                self.assertEqual(len(frame),2)
                self.assertEqual((frame[0]["name"],frame[0]["visible"],frame[0]["opacity"]),("Фон",False,45))
                self.assertEqual(frame[1]["image"].tobytes(),im.tobytes())
            old=p.read_bytes()
            with patch("project_io.os.replace",side_effect=OSError("failure")):
                with self.assertRaises(OSError):write_project(p,8,8,12,frames,0,0,{})
            self.assertEqual(p.read_bytes(),old)
            write_project(p,8,8,12,frames,0,0,{})
            self.assertEqual(read_project(p)[0]["fps"],12)
    def test_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.ffg";p.write_bytes(b"bad")
            with self.assertRaises(ValueError):read_project(p)

class HistoryTests(unittest.TestCase):
    def test_history(self):
        a=FrameForge.__new__(FrameForge)
        a.w=a.h=8;a.index=a.active_layer=0;a.selection_box=None;a.last=None
        a.layer_frames=[[dict(name="layer",visible=True,image=Image.new("RGBA",(8,8)))]]
        a.frames=[None];a.undo_stack=[];a.redo_stack=[]
        a.refresh=a.render=lambda:None
        a.status=type("Status",(),{"set":lambda self,x:None})()
        for n in (1,2,3):
            a.snapshot();a.active_image().putpixel((0,0),(n,0,0,255))
        a.zoom=2
        a.undo();self.assertEqual(a.active_image().getpixel((0,0))[0],2)
        a.undo();self.assertEqual(a.active_image().getpixel((0,0))[0],1)
        a.redo();self.assertEqual(a.active_image().getpixel((0,0))[0],2)
        a.snapshot();self.assertFalse(a.redo_stack)
        a.snapshot(True);a.layer_frames.append(a.layer_frames[0]);a.frames.append(None)
        a.undo();self.assertEqual(len(a.layer_frames),1)
        a.redo();self.assertEqual(len(a.layer_frames),2)
