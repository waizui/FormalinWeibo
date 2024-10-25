import io
import os
import platform
import subprocess
import threading
import tkinter as tk
import urllib.request
import uuid
from html.parser import HTMLParser
from tkinter import ttk
import sqlite3

from PIL import Image

class WeiboDB(object):
    def __init__(self, path="./weibodata.db"):
        self.dbpath = path
        self.con: sqlite3.Connection

    def open(self):
        con = sqlite3.connect(self.dbpath)
        con.row_factory = sqlite3.Row
        self.con = con

    def close(self):
        if self.con:
            self.con.close()

    def get_users(self, count=100):
        cur = self.con.cursor()
        res = cur.execute("SELECT * FROM user LIMIT ?", (count,))
        return res.fetchall()

    def get_user_info(self, id) -> dict:
        """
        id varchar(64) NOT NULL
        ,nick_name varchar(64) NOT NULL
        ,gender varchar(6)
        ,follower_count integer
        ,follow_count integer
        ,birthday varchar(10)
        ,location varchar(32)
        ,edu varchar(32)
        ,company varchar(32)
        ,reg_date DATETIME
        ,main_page_url text
        ,avatar_url text
        ,bio text
        ,PRIMARY KEY (id)
        """
        cur = self.con.cursor()
        res = cur.execute("SELECT * FROM user WHERE id=? ", (id,))
        user = res.fetchone()
        return user

    def get_user_weibo(self, user_id, count=10, offset=0):
        """
        weibo
        id varchar(20) NOT NULL
        ,bid varchar(12) NOT NULL
        ,user_id varchar(20)
        ,screen_name varchar(30)
        ,text varchar(2000)
        ,article_url varchar(100)
        ,topics varchar(200)
        ,at_users varchar(1000)
        ,pics varchar(3000)
        ,video_url varchar(1000)
        ,location varchar(100)
        ,created_at DATETIME
        ,source varchar(30)
        ,attitudes_count INT
        ,comments_count INT
        ,reposts_count INT
        ,retweet_id varchar(20)
        ,PRIMARY KEY (id)
        """
        cur = self.con.cursor()
        res = cur.execute(
            "SELECT * FROM weibo WHERE user_id=? LIMIT ? OFFSET ?",
            (user_id, count, offset),
        )
        user = res.fetchall()
        return user

    def get_weibo(self, wid):
        cur = self.con.cursor()
        res = cur.execute(
            "SELECT * FROM weibo WHERE id=?",
            (wid,),
        )
        return res.fetchone()

    def get_comments(self, wid):
        """
          id varchar(20) NOT NULL
        ,bid varchar(20) NOT NULL
        ,weibo_id varchar(32) NOT NULL
        ,root_id varchar(20)
        ,user_id varchar(20) NOT NULL
        ,created_at varchar(20)
        ,user_screen_name varchar(64) NOT NULL
        ,user_avatar_url text
        ,text varchar(1000)
        ,pic_url text
        ,like_count integer
        ,PRIMARY KEY (id)
        """
        cur = self.con.cursor()
        res = cur.execute(
            "SELECT * FROM  comments WHERE weibo_id=?",
            (wid,),
        )
        return res.fetchall()

    def get_bins(self, weibo_id):
        """
        bins
        id integer PRIMARY KEY AUTOINCREMENT
        ,ext varchar(10) NOT NULL /*file extension*/
        ,data blob NOT NULL
        ,weibo_id varchar(20)
        ,comment_id varchar(20)
        ,path text
        ,url text
        """
        cur = self.con.cursor()
        res = cur.execute("SELECT * FROM bins WHERE weibo_id=?", (weibo_id,))
        bin = res.fetchall()
        return bin

class CommentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.data = []

    def handle_starttag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        pass

    def handle_data(self, data):
        """Handles text between tags."""
        if data.strip():  # Skip empty text
            self.data.append(data.strip())


class TKWindow:
    H = 800
    W = 500
    SCROLL_OFFSET = 30

    def __init__(self) -> None:
        self.db = WeiboDB()
        self.imgcache = []
        self.cur_uid = 0
        self.tk = self.create_window()

    def create_window(self):
        win = tk.Tk()
        win.title("FormalinWeibo")
        # center the window
        screen_width = win.winfo_screenwidth()
        screen_height = win.winfo_screenheight()
        x = (screen_width // 2) - (self.W // 2)
        y = (screen_height // 2) - (self.H // 2)
        win.geometry(f"{self.W+self.SCROLL_OFFSET}x{self.H}+{x}+{y}")
        return win

    def show(self):
        self.db.open()
        self.show_users()
        self.tk.mainloop()
        self.db.close()

    def create_scoll(self, tkwin):
        # create scorllable
        canvas = tk.Canvas(tkwin)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(tkwin, command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        items_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=items_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # different accroding to os
        wheel = 1 if platform.system() == "Darwin" else 120
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / wheel)), "units"),
        )
        items_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        return items_frame

    def clear_window(self, tkwin):
        for widget in tkwin.winfo_children():
            widget.destroy()
        return self.create_scoll(tkwin)

    def show_users(self):
        items_frame = self.clear_window(self.tk)
        db = self.db
        users = db.get_users()
        for user in users:
            uid = user["id"]
            info = db.get_user_info(uid)
            btn = tk.Button(
                items_frame,
                text=info["nick_name"],
                command=lambda uid=uid: self.show_weibos(uid),
            )
            btn.pack()

            text = [
                f'bio:{info["bio"]}',
                f'性别:{ "男" if info["gender"]=="m" else "女"} 关注数:{info["follow_count"]} 粉丝数:{info["follower_count"]}',
                f'生日:{info["birthday"]} 地区:{info["location"]} 教育:{info["edu"]} 公司:{info["company"]} 注册日期:{info["reg_date"]}',
            ]
            label = tk.Label(
                items_frame,
                text="\n".join(text),
                justify="left",
                wraplength=self.W,
            )
            label.pack()
            ttk.Separator(items_frame, orient="horizontal").pack(fill="x", pady=10)

    def stringify_row(self, row):
        return "\n".join([key + ":" + str(value) for key, value in dict(row).items()])

    def show_weibos(self, uid, count_limit=10, offset=0):
        items_frame = self.clear_window(self.tk)
        self.weibo_offset = offset
        self.cur_uid = uid
        self.imgcache.clear()
        db = self.db
        weibos = db.get_user_weibo(uid, count_limit, offset)
        for weibo in weibos:
            self.add_weibo_item(items_frame, weibo)
            ttk.Separator(items_frame, orient="horizontal").pack(fill="x", pady=10)
        weibo_count = len(weibos)
        if weibo_count == 0:
            self.add_label(items_frame, "没有微博了")
            return

        nextoffset = weibo_count + offset
        btn = tk.Button(
            items_frame,
            text="下一页",
            command=lambda: self.show_weibos(uid, count_limit, nextoffset),
        )
        btn.pack()

    def openvideo(self, path):
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", path])
        elif platform.system() == "Linux":
            subprocess.run(["vlc", path])
        else:
            print("Unsupported platform")

    def add_weibo_item(self, items_frame, weibo):
        if not weibo:
            return
        db = self.db

        self.add_label(
            items_frame,
            f'{weibo["screen_name"]} {weibo["created_at"]} {weibo["source"]}',
        )

        text = weibo["text"]
        self.add_label(items_frame, f"{text}")

        reid = weibo["retweet_id"]
        if reid:
            self.add_label(items_frame, "转发@")
            ret = db.get_weibo(reid)
            self.add_weibo_item(items_frame, ret)

        bins = db.get_bins(weibo["id"])
        if bins:
            self.add_bins(items_frame, bins)

        self.add_label(
            items_frame,
            f'赞:{weibo["attitudes_count"]} 评论:{weibo["comments_count"]} 转发:{weibo["reposts_count"]}',
        ).bind("<Button-1>", lambda e: self.open_comments(weibo))

    def open_comments(self, weibo):
        if weibo["comments_count"] == 0:
            return

        items_frame = self.create_scoll(self.create_window())
        comments = self.db.get_comments(weibo["id"])
        text = []
        for comment in comments:
            parser = CommentParser()
            parser.feed(comment["text"])
            text.append(f'{comment["user_screen_name"]}:{"".join(parser.data)}')
        text.reverse()
        l = tk.Label(
            items_frame,
            text="\n".join(text),
            justify="left",
            wraplength=self.W,
        )
        l.pack(anchor="w")

    def get_web_img(self, url):
        id = str(uuid.uuid3(uuid.NAMESPACE_DNS, url))
        path = id + ".png"
        has, cachepath = self.cache_path(path)
        if not has:
            threading.Thread(
                target=lambda u, p: urllib.request.urlretrieve(u, p), args=(url, path)
            ).start()
        else:
            tk_image = tk.PhotoImage(file=cachepath)
            return tk_image

    def add_label(self, items_frame, text, **kwargs):
        l = tk.Label(
            items_frame,
            text=text,
            justify="left",
            wraplength=self.W,
        )
        l.pack(anchor="w")
        return l

    def add_bins(self, items_frame, bins):
        for bin in bins:
            ext = bin["ext"]
            if ext == ".jpg":
                image = self.bin_to_image(bin)
                # preventing GC
                self.imgcache.append(image)
                w, h = self.fit_size(image.width(), image.height())
                label = tk.Label(items_frame, image=image, width=w, height=h)
                label.pack()
                continue
            if ext == ".mp4":
                videopath = self.bin_to_video(bin)
                btn = tk.Button(
                    items_frame,
                    text="播放",
                    command=lambda: self.openvideo(videopath),
                )
                btn.pack()
                continue

    def fit_size(self, originW, originH):
        if originW <= self.W and originH <= self.H:
            return (originW, originH)

        rw, rh = self.W / originW, self.H / originH
        ratio = min(rw, rh)
        return (int(originW * ratio), int(originH * ratio))

    def cache_path(self, filename) -> tuple[bool, str]:
        cachepath = os.path.join("cache", str(self.cur_uid), filename)
        if not os.path.exists(cachepath):
            dir = os.path.dirname(cachepath)
            if not os.path.exists(dir):
                os.makedirs(dir)
            return False, cachepath
        return True, cachepath

    def bin_to_image(self, bin):
        data = bin["data"]
        bid = bin["id"]
        ext = ".png"
        has, cachepath = self.cache_path(str(bid) + ext)
        if not has:
            img = Image.open(io.BytesIO(data))
            size = self.fit_size(img.size[0], img.size[1])
            img = img.resize(size)
            img.save(cachepath, format="PNG")

        tk_image = tk.PhotoImage(file=cachepath)
        return tk_image

    def bin_to_video(self, bin):
        data = bin["data"]
        bid = bin["id"]
        ext = ".mp4"
        has, cachepath = self.cache_path(str(bid) + ext)
        if not has:
            buf = io.BytesIO(data)
            with open(cachepath, "wb") as f:
                buf.seek(0)
                f.write(buf.read())
        return cachepath


win = TKWindow()
win.show()
