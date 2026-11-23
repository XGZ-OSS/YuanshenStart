# -*- coding: utf-8 -*-
"""沅神启动 | Python 3.14 + tkinter/ttk clam | 单文件、纯标准库。

可选：把原图以「logo.png」放到本文件同目录。
默认保存到 %LocalAppData%/沅神启动/积分数据.json；与 DeepSeek v3.4 共用目录。
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import json
import os
import sys
import ssl
import hashlib
import base64
import urllib.request
import urllib.parse
import threading
import queue
import subprocess
import re
import shutil
import copy
import time
from datetime import datetime
from pathlib import Path

APP = "沅神启动"
APP_VERSION = "4.2"
BG = "#F2F9F1"
CARD = "#FFFFFF"
INK = "#365C45"
TEXT = "#456850"
MUTED = "#7E9B85"
PRIMARY = "#78B995"
PRIMARY_HOVER = "#65A982"
PRIMARY_DARK = "#4D966D"
LIGHT = "#DFF1E3"
BORDER = "#D9E9DC"
ALT = "#F7FBF7"
HEAD = "#EAF5EA"
DANGER = "#C84C4C"
DANGER_LIGHT = "#FFF0F0"
LEADER = "#EEF7D9"
DISABLED = "#A2B3A5"
FONT = "Microsoft YaHei UI"
FONT_SIZES = {"brand": 16, "title": 20, "stat": 21, "group": 14,
              "body": 11, "table": 10, "small": 10, "tiny": 9}
GEAR_COORDINATES = (
    18.49, 12.96, 19.48, 9.55, 24.52, 9.55, 25.51, 12.96,
    25.91, 13.12, 29.02, 11.41, 32.59, 14.98, 30.88, 18.09,
    31.04, 18.49, 34.45, 19.48, 34.45, 24.52, 31.04, 25.51,
    30.88, 25.91, 32.59, 29.02, 29.02, 32.59, 25.91, 30.88,
    25.51, 31.04, 24.52, 34.45, 19.48, 34.45, 18.49, 31.04,
    18.09, 30.88, 14.98, 32.59, 11.41, 29.02, 13.12, 25.91,
    12.96, 25.51, 9.55, 24.52, 9.55, 19.48, 12.96, 18.49,
    13.12, 18.09, 11.41, 14.98, 14.98, 11.41, 18.09, 13.12
)
DATA_NAME = "积分数据.json"
UPDATE_FILENAME = "update_url.txt"

SECTIONS = ("成员", "礼物", "玩法", "收支记录", "积分统计")
DEFAULT_SETTINGS = {"museum_rate": 1.2, "exhibit_rate": 1.2, "normal_rate": 1.0, "session_start": ""}
FIELDS = {
    "成员": [("name", "成员名字", 150), ("base", "基础积分", 110),
             ("gift", "礼物积分", 110), ("spent", "玩法花费", 110),
             ("total", "当前积分", 120)],
    "礼物": [("name", "礼物名字", 130), ("value", "价值积分", 95),
             ("museum", "展馆礼物", 85), ("status", "状态", 80),
             ("single", "单个计分", 105), ("count", "累计个数", 100),
             ("total", "累计积分", 110)],
    "玩法": [("name", "玩法名字", 190), ("cost", "花费积分", 140),
             ("count", "累计次数", 140), ("total", "累计花费", 140)],
    "积分统计": [("rank", "排名", 60), ("name", "名字", 145),
                 ("base", "基础积分", 110), ("gift", "礼物积分", 110),
                 ("spent", "玩法花费", 110), ("total", "总积分", 125)],
}
RECORD_FIELDS = [("time", "时间", 115), ("member", "成员", 95),
                 ("item", "项目", 100), ("count", "数量", 60),
                 ("points", "积分", 85)]


def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def empty_data():
    return {"format_version": 2, "settings": copy.deepcopy(DEFAULT_SETTINGS),
            "next_id": 1, "members": [], "gifts": [], "gameplays": [],
            "gift_records": [], "play_records": []}


def number(tenths):
    """积分内部以十分之一分为单位，避免 float 累积误差。"""
    sign = "-" if tenths < 0 else ""
    n = abs(int(tenths))
    whole, frac = divmod(n, 10)
    return f"{sign}{whole:,}" + (f".{frac}" if frac else "")


def signed(tenths):
    return ("+" if tenths > 0 else "") + number(tenths)


def rate_tenths(rate):
    return int(round(float(rate) * 10))


def parse_rate(value):
    """仅允许 0.1～9.9；小数最多一位。"""
    s = str(value).strip()
    pieces = s.split(".")
    if len(pieces) > 2 or not pieces[0].isdigit():
        raise ValueError("请输入 0.1～9.9，最多一位小数")
    if len(pieces) == 2 and (len(pieces[1]) != 1 or not pieces[1].isdigit()):
        raise ValueError("倍率最多保留一位小数")
    tenths = int(pieces[0]) * 10
    if len(pieces) == 2:
        tenths += int(pieces[1])
    if not 1 <= tenths <= 99:
        raise ValueError("倍率必须在 0.1～9.9 之间")
    return tenths / 10


def normalize_data(raw):
    """兼容本程序 v2 及 DeepSeek v3.4 数据格式，保留额外字段。

    仅在内存中适配，绝不直接改写被导入的原始文件。
    """
    if not isinstance(raw, dict) or raw.get("format_version", 2) != 2:
        raise ValueError("不是支持的 v2 数据文件")
    d = copy.deepcopy(raw)  # 保留顶层未知字段
    defaults = empty_data()
    for key in ("members", "gifts", "gameplays", "gift_records", "play_records"):
        rows = d.get(key, [])
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise ValueError(f"数据字段 {key} 无效")
        d[key] = rows

    settings = d.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("settings 字段无效")
    # DeepSeek 原文件使用 exhibit_rate，本程序保留双字段，改倍率时同步更新。
    museum = settings.get("museum_rate", settings.get("exhibit_rate", 1.2))
    settings["museum_rate"] = parse_rate(museum)
    settings["exhibit_rate"] = settings["museum_rate"]
    settings["normal_rate"] = parse_rate(settings.get("normal_rate", 1.0))
    settings.setdefault("session_start", "")
    if not isinstance(settings["session_start"], str):
        raise ValueError("session_start 无效")
    d["settings"] = settings

    seen = set()
    for field in ("members", "gifts", "gameplays", "gift_records", "play_records"):
        for row in d[field]:
            ident = row.get("id")
            if type(ident) is not int or ident <= 0 or ident in seen:
                raise ValueError(f"{field} 中存在重复或无效 id")
            seen.add(ident)
            if field in ("members", "gifts", "gameplays"):
                if not isinstance(row.get("name"), str) or not row["name"].strip():
                    raise ValueError(f"{field} 存在无效名称")
            if field == "members":
                row["base"] = row.get("base", 0)
                if type(row["base"]) not in (int, float):
                    raise ValueError("基础积分无效")
            if field == "gifts":
                if type(row.get("value")) not in (int, float):
                    raise ValueError("礼物价值无效")
                # is_exhibit 是 v3.4 原始语义，统一为 is_museum，保存时同步
                mark = bool(row.get("is_museum", row.get("is_exhibit", False)))
                row["is_museum"] = mark
                row["is_exhibit"] = mark
                row["blocked"] = bool(row.get("blocked", False))
            if field == "gameplays":
                if type(row.get("cost")) not in (int, float):
                    raise ValueError("玩法花费无效")
            if field == "gift_records":
                if any(type(row.get(k)) is not int for k in ("member_id", "gift_id", "count")):
                    raise ValueError("收礼记录 id 或数量无效")
                if row["count"] < 0:
                    raise ValueError("收礼数量无效")
            if field == "play_records":
                if any(type(row.get(k)) is not int for k in ("member_id", "gameplay_id", "times")):
                    raise ValueError("玩法记录 id 或次数无效")
                if row["times"] < 0:
                    raise ValueError("玩法次数无效")
            if field in ("gift_records", "play_records"):
                if not isinstance(row.get("time"), str):
                    raise ValueError(f"{field} 中 ID {row['id']} 的记录时间无效：{row.get('time')!r}")
                row.setdefault("scene", "默认场次")
                if not isinstance(row["scene"], str):
                    raise ValueError("记录场次无效")

    scenes = d.get("scenes", [])
    if not isinstance(scenes, list) or not all(isinstance(n, str) for n in scenes):
        raise ValueError("场次列表无效")
    from_records = [r["scene"] for r in d["gift_records"] + d["play_records"]]
    d["scenes"] = list(dict.fromkeys(["默认场次"] + scenes + from_records))
    active = d.get("active_scene", "默认场次")
    d["active_scene"] = active if active in d["scenes"] else "默认场次"
    next_id = d.get("next_id", 1)
    if type(next_id) is not int:
        raise ValueError("next_id 无效")
    d["next_id"] = max(next_id, max(seen, default=0) + 1)
    d["format_version"] = 2
    return d


def normalize_deepseek_legacy(raw):
    """Import-only DeepSeek converter; never changes the selected source JSON.

    Do not invent dates for missing/invalid timestamps: tell the user the exact row.
    Ordinary v4.1 file loading still uses the strict normalize_data validator.
    """
    if not isinstance(raw, dict):
        raise ValueError("旧版文件根节点必须是 JSON 对象")
    converted = copy.deepcopy(raw)
    changes = []
    for table, title in (("gift_records", "收礼记录"), ("play_records", "玩法记录")):
        records = converted.get(table, [])
        if not isinstance(records, list):
            raise ValueError(f"{title}不是列表")
        for index, record in enumerate(records, 1):
            if not isinstance(record, dict):
                raise ValueError(f"{title}第 {index} 条不是对象")
            value = record.get("time")
            label = f"{title}第 {index} 条（ID {record.get('id', '未知')}）"
            if isinstance(value, str):
                v = value.strip()
                if not v:
                    raise ValueError(f"{label}缺少记录时间；请核对原始文件，未自动编造时间")
                v = v.replace("年", "-").replace("月", "-").replace("日", " ")
                v = v.replace("/", "-").replace("T", " ")
                try:
                    # Support ISO-8601 offsets and fractional seconds.
                    parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError(f"{label}的时间无法识别：{value!r}") from exc
            elif type(value) in (int, float):
                try:
                    seconds = value / 1000 if abs(value) >= 100_000_000_000 else value
                    parsed = datetime.fromtimestamp(seconds)
                except (ValueError, OverflowError, OSError) as exc:
                    raise ValueError(f"{label}的时间戳无效：{value!r}") from exc
            else:
                raise ValueError(f"{label}的时间无效：{value!r}；请核对原始记录")
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone()
            canonical = parsed.strftime("%Y-%m-%d %H:%M:%S")
            if canonical != value:
                changes.append(f"{label}：{value!r} -> {canonical}")
            record["time"] = canonical
    result = normalize_data(converted)
    return result, changes


class YuanshenApp(ttk.Frame):
    def __init__(self, root):
        self.root = root
        self.root.title(APP)
        self.root.geometry("1180x760")
        self.root.minsize(1040, 660)
        self.root.configure(bg=BG)
        self._init_style()
        super().__init__(root, style="App.TFrame")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        self.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.base_dir = (Path(sys.executable).resolve().parent
                         if getattr(sys, "frozen", False)
                         else Path(__file__).resolve().parent)
        self.data_dir = self._locate_data_dir()
        self.data_path = self.data_dir / DATA_NAME
        self.fixed_backup = self.data_dir / "积分数据.备份.json"
        self.data = empty_data()
        self.last_saved_text = None
        self.autosave_job = None
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo = 20
        self.dirty = False
        self.load_message = ""
        self.active_section = "成员"
        self.member_var = tk.StringVar()
        self.quantity_var = tk.IntVar(value=1)
        self.status_var = tk.StringVar(value="欢迎使用沅神启动")
        self.search_vars = {}
        self.tab_buttons = {}
        self.tables = {}
        self.stat_values = {}
        self.empty_labels = {}
        self.record_tables = {}
        self.quick_window = None
        self.welcome = None
        self.logo = None
        self._load_logo()
        self._load_at_startup()
        self.update_events = queue.Queue()
        self.update_busy = False

        self._build_topbar()
        self._build_tabs()
        self._build_content()
        self._build_statusbar()
        self._refresh_all()
        if self.load_message:
            self._status(self.load_message)
        self._show_welcome()

        root.bind("<Control-z>", self._undo)
        root.bind("<Control-y>", self._redo)
        root.bind("<Control-s>", self._save_shortcut)
        root.bind("<F5>", self._reload_current_file)
        root.protocol("WM_DELETE_WINDOW", self._close)
        root.after(200, self._poll_updates)
        if self._get_update_url():
            root.after(1500, lambda: self._check_updates(False))

    def _init_style(self):
        """所有 ttk.Style 的 configure/map/主题设置仅在本方法。"""
        s = ttk.Style(self.root)
        s.theme_use("clam")
        small = (FONT, FONT_SIZES["small"])
        body = (FONT, FONT_SIZES["body"])
        s.configure("App.TFrame", background=BG)
        s.configure("Card.TFrame", background=CARD)
        s.configure("Soft.TFrame", background=BG)
        s.configure("Metric.TFrame", background=CARD, borderwidth=1,
                    relief="solid", bordercolor=BORDER)
        s.configure("TableCard.TFrame", background=CARD, borderwidth=1,
                    relief="solid", bordercolor=BORDER)
        s.configure("PageTitle.TLabel", background=BG, foreground=INK,
                    font=(FONT, FONT_SIZES["title"], "bold"))
        s.configure("PageMuted.TLabel", background=BG, foreground=MUTED,
                    font=(FONT, FONT_SIZES["small"]))
        s.configure("MetricCaption.TLabel", background=CARD, foreground=MUTED,
                    font=(FONT, FONT_SIZES["small"]))
        s.configure("MetricValue.TLabel", background=CARD, foreground=PRIMARY_DARK,
                    font=(FONT, FONT_SIZES["stat"] + 3, "bold"))
        s.configure("App.TLabel", background=BG, foreground=INK, font=body)
        s.configure("Card.TLabel", background=CARD, foreground=TEXT, font=body)
        s.configure("Title.TLabel", background=BG, foreground=INK,
                    font=(FONT, FONT_SIZES["title"], "bold"))
        s.configure("Brand.TLabel", background=BG, foreground=INK,
                    font=(FONT, FONT_SIZES["brand"], "bold"))
        s.configure("Group.TLabel", background=CARD, foreground=INK,
                    font=(FONT, FONT_SIZES["group"], "bold"))
        s.configure("Muted.TLabel", background=BG, foreground=MUTED, font=small)
        s.configure("CardMuted.TLabel", background=CARD, foreground=MUTED, font=small)
        s.configure("Stat.TLabel", background=CARD, foreground=INK,
                    font=(FONT, FONT_SIZES["stat"], "bold"))
        s.configure("Status.TLabel", background=BG, foreground=MUTED, font=small)
        s.configure("Primary.TButton", background=PRIMARY, foreground=CARD,
                    bordercolor=PRIMARY, lightcolor=PRIMARY, darkcolor=PRIMARY,
                    relief="flat", padding=(14, 9), font=(FONT, FONT_SIZES["body"], "bold"))
        s.map("Primary.TButton",
              background=[("disabled", BORDER), ("pressed", PRIMARY_DARK),
                          ("active", PRIMARY_HOVER)],
              foreground=[("disabled", DISABLED), ("active", CARD)])
        s.configure("Secondary.TButton", background=CARD, foreground=INK,
                    bordercolor=BORDER, relief="solid", borderwidth=1,
                    padding=(12, 8), font=body)
        s.map("Secondary.TButton",
              background=[("pressed", LIGHT), ("active", BG)],
              bordercolor=[("active", PRIMARY)])
        s.configure("Danger.TButton", background=CARD, foreground=DANGER,
                    bordercolor=BORDER, relief="solid", padding=(12, 8), font=body)
        s.map("Danger.TButton", background=[("active", DANGER_LIGHT),
                                           ("pressed", "#F9DADA")],
              foreground=[("active", DANGER)])
        s.configure("Tab.TButton", background=CARD, foreground=MUTED,
                    bordercolor=BORDER, padding=(18, 10), font=body)
        s.map("Tab.TButton", background=[("active", BG), ("pressed", LIGHT)],
              foreground=[("active", INK)])
        s.configure("TabActive.TButton", background=LIGHT, foreground=INK,
                    bordercolor=PRIMARY, padding=(18, 10),
                    font=(FONT, FONT_SIZES["body"], "bold"))
        s.map("TabActive.TButton", background=[("active", LIGHT)])
        s.configure("Compact.TButton", background=CARD, foreground=TEXT,
                    bordercolor=BORDER, padding=(7, 5), font=small)
        s.map("Compact.TButton", background=[("active", LIGHT)],
              bordercolor=[("active", PRIMARY)])
        s.configure("Data.Treeview", background=CARD, fieldbackground=CARD,
                    foreground=TEXT, borderwidth=0, rowheight=43,
                    font=(FONT, FONT_SIZES["table"]))
        s.map("Data.Treeview", background=[("selected", LIGHT)],
              foreground=[("selected", INK)])
        s.configure("Data.Treeview.Heading", background=HEAD, foreground=INK,
                    bordercolor=BORDER, relief="flat", padding=(7, 8),
                    font=(FONT, FONT_SIZES["table"], "bold"))
        s.map("Data.Treeview.Heading", background=[("active", LIGHT)])
        s.configure("Mint.TEntry", fieldbackground=CARD, foreground=INK,
                    bordercolor=BORDER, padding=6, font=body)
        s.map("Mint.TEntry", bordercolor=[("focus", PRIMARY)])
        s.configure("Mint.TCombobox", fieldbackground=CARD, background=CARD,
                    foreground=INK, bordercolor=BORDER, padding=5, font=body)
        s.map("Mint.TCombobox", bordercolor=[("focus", PRIMARY)],
              fieldbackground=[("readonly", CARD)],
              selectbackground=[("readonly", CARD)],
              selectforeground=[("readonly", INK)])
        s.configure("Mint.TCheckbutton", background=CARD, foreground=TEXT,
                    padding=3, font=body)
        s.map("Mint.TCheckbutton", background=[("active", CARD)])
        s.configure("Mint.Vertical.TScrollbar", background=BORDER,
                    troughcolor=BG, bordercolor=BG, arrowcolor=TEXT)
        s.map("Mint.Vertical.TScrollbar", background=[("active", PRIMARY)])
        s.configure("Mint.TSeparator", background=BORDER)

    def _locate_data_dir(self):
        """DeepSeek v3.4 compatible per-Windows-user storage.

        A new release never uses its EXE directory for live data. Older portable
        data is picked up only if no current user data exists.
        """
        local = os.environ.get("LOCALAPPDATA")
        if local:
            directory = Path(local) / "沅神启动"
        else:
            # Non-Windows development fallback; Windows always has LOCALAPPDATA.
            directory = Path.home() / "AppData" / "Local" / "沅神启动"
        directory.mkdir(parents=True, exist_ok=True)
        return directory.resolve()

    def _load_logo(self):
        path = self.base_dir / "logo.png"
        if not path.is_file() and getattr(sys, "frozen", False):
            path = Path(getattr(sys, "_MEIPASS", self.base_dir)) / "logo.png"
        if path.is_file():
            try:
                img = tk.PhotoImage(file=str(path))
                self.root.iconphoto(True, img)
                factor = max(1, (img.width() + 63) // 64)
                self.logo = img.subsample(factor) if factor > 1 else img
            except tk.TclError:
                self.logo = None

    def _read_json(self, path):
        with path.open("r", encoding="utf-8-sig") as handle:
            return normalize_data(json.load(handle))

    def _history_paths(self):
        return sorted(self.data_dir.glob("积分数据.备份-*.json"),
                      key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)

    def _legacy_data_candidates(self):
        """只在当前无数据时查找可能的旧版本文件，不进行递归全盘扫描。

        兼容旧包的 release/data、发布/data、data，以及 DeepSeek 的 LocalAppData。
        按修改时间优先使用最近编辑过的数据；旧版文件永不修改。
        """
        found = {}
        target = self.data_path.resolve()

        def register(path):
            try:
                if path.is_file():
                    resolved = path.resolve()
                    if resolved != target:
                        found[str(resolved).lower()] = resolved
            except OSError:
                pass

        # v4.0/v4.1 live in EXE-neighbor data; include current folder as well.
        register(self.base_dir / "data" / DATA_NAME)
        register(self.base_dir / "release" / "data" / DATA_NAME)
        for folder in (self.base_dir.parent, self.base_dir.parent.parent):
            for sub in ("data", "release/data", "发布/data"):
                register(folder / sub / DATA_NAME)
            try:
                entries = list(folder.iterdir())
            except OSError:
                continue
            for entry in entries[:250]:
                if not entry.is_dir() or entry.resolve() == self.base_dir.resolve():
                    continue
                # 候选必须处于应用发布目录或名称包含应用标记的文件夹中。
                tagged = ("沅神" in entry.name or "yuanshen" in entry.name.lower()
                          or entry.name.lower() in ("release", "dist", "发布"))
                if not tagged:
                    continue
                for sub in ("data", "release/data", "发布/data", "dist/data"):
                    register(entry / sub / DATA_NAME)

        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            for app_dir in ("沅神启动", "积分统计程序"):
                register(Path(local) / app_dir / DATA_NAME)

        return sorted(found.values(), key=lambda x: x.stat().st_mtime_ns, reverse=True)

    def _inherit_previous_data(self):
        """仅当新版数据文件不存在且没有可恢复备份时自动继承。

        导入前保留字节原样的迁移副本，且不覆盖旧版原文件。
        """
        had_candidates = False
        for previous in self._legacy_data_candidates():
            had_candidates = True
            try:
                inherited = self._read_json(previous)
                backup = self.data_dir / "积分数据.迁移来源.json"
                temp_backup = self.data_dir / "积分数据.迁移来源.json.tmp"
                if not backup.exists():
                    try:
                        shutil.copy2(previous, temp_backup)
                        os.replace(temp_backup, backup)
                    finally:
                        if temp_backup.exists():
                            temp_backup.unlink()
                self.data = inherited
                self._atomic_write(self._json_text(), backup=False)
                self.load_message = (
                    "已自动继承旧版数据：" + str(previous.parent)
                )
                return True
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        if had_candidates:
            self.load_message = "发现旧数据但未找到可读取的文件，可在文件面板手动导入"
        return False

    def _load_at_startup(self):
        if not self.data_path.exists():
            # 新版自身的备份优先于其他版本，防止使用过时数据。
            candidates = self._history_paths() + ([self.fixed_backup] if self.fixed_backup.exists() else [])
            for path in candidates:
                try:
                    self.data = self._read_json(path)
                    self._atomic_write(self._json_text(), backup=False)
                    self.load_message = "已从本版本备份恢复"
                    return
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
            if self._inherit_previous_data():
                return
            if not self.load_message:
                self.load_message = "首次使用：添加成员即可开始"
            return
        try:
            self.data = self._read_json(self.data_path)
            self.last_saved_text = self._json_text()
            return
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

        candidates = self._history_paths()
        if self.fixed_backup.exists():
            candidates.append(self.fixed_backup)
        for path in candidates:
            try:
                self.data = self._read_json(path)
                self._atomic_write(self._json_text(), backup=False)
                self.load_message = "已从备份恢复"
                return
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        self.data = empty_data()
        self.load_message = "主数据损坏且无有效备份：请通过备份管理恢复，或检查数据文件"
        self._startup_unrecoverable = True

    def _json_text(self):
        return json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def _backup_current(self):
        """保存旧版快照，固定备份+带时间戳历史（至多10份）。"""
        if not self.data_path.exists():
            return
        # 不从已损坏的内容生成新备份。
        self._read_json(self.data_path)
        shutil.copy2(self.data_path, self.fixed_backup)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = self.data_dir / f"积分数据.备份-{stamp}.json"
        if dest.exists():
            # 同秒内多次保存不覆盖此前历史；添加秒后缀并保持可排序。
            suffix = 1
            while dest.exists():
                dest = self.data_dir / f"积分数据.备份-{stamp}-{suffix:02d}.json"
                suffix += 1
        shutil.copy2(self.data_path, dest)
        for old in self._history_paths()[10:]:
            old.unlink()

    def _atomic_write(self, text, backup=True):
        tmp = self.data_dir / "积分数据.json.tmp"
        try:
            if backup and self.data_path.exists():
                self._backup_current()
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.data_path)
            self.last_saved_text = text
            self.dirty = False
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    def _save_now(self):
        if self.autosave_job is not None:
            self.after_cancel(self.autosave_job)
            self.autosave_job = None
        text = self._json_text()
        if text == self.last_saved_text:
            self.dirty = False
            return True
        try:
            # 数据相同但进程重启时，也避免无意义覆盖。
            if self.data_path.exists():
                try:
                    if self.data_path.read_text(encoding="utf-8-sig") == text:
                        self.last_saved_text = text
                        self.dirty = False
                        return True
                except (OSError, UnicodeError):
                    pass
            self._atomic_write(text)
            self._status("已自动保存 " + datetime.now().strftime("%H:%M:%S"))
            return True
        except (OSError, ValueError, TypeError) as exc:
            self.dirty = True
            self._status(f"保存失败：{exc}")
            return False

    def _schedule_save(self):
        self.dirty = True
        if self.autosave_job is not None:
            self.after_cancel(self.autosave_job)
        self.autosave_job = self.after(300, self._save_now)

    def _snapshot(self):
        return copy.deepcopy(self.data)

    def _remember(self):
        self.undo_stack.append(self._snapshot())
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _changed(self, text="数据已更新"):
        self._refresh_all()
        self._schedule_save()
        self._status(text)

    def _undo(self, event=None):
        if not self.undo_stack:
            self._status("没有可撤销的操作")
            return
        self.redo_stack.append(self._snapshot())
        self.data = self.undo_stack.pop()
        self._changed("已撤销")

    def _redo(self, event=None):
        if not self.redo_stack:
            self._status("没有可重做的操作")
            return
        self.undo_stack.append(self._snapshot())
        self.data = self.redo_stack.pop()
        self._changed("已重做")

    def _save_shortcut(self, event=None):
        self._save_now()

    def _status(self, message):
        self.status_var.set(message)

    def _new_id(self):
        ident = self.data["next_id"]
        self.data["next_id"] += 1
        return ident

    def _lookup(self, category):
        return {row["id"]: row for row in self.data[category]}

    def _filtered(self, records):
        # Always show all records: no sessions, scene filters, or hidden points.
        return records

    def _valid_records(self, type_name, filtered=True):
        field = "gift_records" if type_name == "gift" else "play_records"
        item_key = "gift_id" if type_name == "gift" else "gameplay_id"
        item_type = "gifts" if type_name == "gift" else "gameplays"
        members, items = self._lookup("members"), self._lookup(item_type)
        records = self._filtered(self.data[field]) if filtered else self.data[field]
        valid = []
        orphans = 0
        for record in records:
            if record["member_id"] not in members or record[item_key] not in items:
                orphans += 1
            else:
                valid.append((record, members[record["member_id"]],
                              items[record[item_key]]))
        return valid, orphans

    def _gift_points(self, record, gift):
        rate = (self.data["settings"]["museum_rate"] if gift["is_museum"]
                else self.data["settings"]["normal_rate"])
        return int(round(gift["value"] * rate_tenths(rate) * record["count"]))

    def _game_points(self, record, game):
        return int(round(game["cost"] * 10 * record["times"]))

    def _calculate(self):
        totals = {
            m["id"]: {"base": int(round(m["base"] * 10)), "gift": 0, "spent": 0}
            for m in self.data["members"]
        }
        gift_counts = {}
        gift_points = {}
        game_counts = {}
        game_points = {}
        good_gifts, g_orphan = self._valid_records("gift")
        good_plays, p_orphan = self._valid_records("play")
        for r, member, gift in good_gifts:
            points = self._gift_points(r, gift)
            totals[member["id"]]["gift"] += points
            ident = gift["id"]
            gift_counts[ident] = gift_counts.get(ident, 0) + r["count"]
            gift_points[ident] = gift_points.get(ident, 0) + points
        for r, member, game in good_plays:
            points = self._game_points(r, game)
            totals[member["id"]]["spent"] += points
            ident = game["id"]
            game_counts[ident] = game_counts.get(ident, 0) + r["times"]
            game_points[ident] = game_points.get(ident, 0) + points
        for value in totals.values():
            value["total"] = value["base"] + value["gift"] - value["spent"]
        return totals, gift_counts, gift_points, game_counts, game_points, g_orphan + p_orphan

    def _dialog_parent(self):
        """优先选当前模态窗口作为父窗口；否则用主窗口。"""
        grabbed = self.root.grab_current()
        if grabbed is not None:
            top = grabbed.winfo_toplevel()
            if top.winfo_exists():
                return top
        return self.root

    def _center_dialog(self, win, width, height, parent=None, modal=True):
        """将对话框居中于上级窗口；自动防止超出屏幕。"""
        owner = parent if parent is not None else self._dialog_parent()
        owner.update_idletasks()
        win.withdraw()
        win.transient(owner)
        win.geometry(f"{width}x{height}")
        win.update_idletasks()
        # centering relative to parent (not entire screen)
        cx = owner.winfo_rootx() + owner.winfo_width() // 2
        cy = owner.winfo_rooty() + owner.winfo_height() // 2
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = min(max(0, cx - width // 2), max(0, screen_w - width))
        y = min(max(0, cy - height // 2), max(0, screen_h - height))
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.deiconify()
        win.lift(owner)
        if modal:
            win.grab_set()
        win.focus_set()
        return win

    def _build_topbar(self):
        bar = ttk.Frame(self, style="App.TFrame", padding=(30, 12))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        branding = ttk.Frame(bar, style="App.TFrame")
        branding.grid(row=0, column=0, sticky="w")
        if self.logo:
            ttk.Label(branding, image=self.logo, style="App.TLabel").pack(side="left", padx=(0, 9))
        else:
            ttk.Label(branding, text="YS", style="Brand.TLabel").pack(side="left", padx=(0, 10))
        ttk.Label(branding, text=APP, style="Brand.TLabel").pack(side="left")
        right = ttk.Frame(bar, style="App.TFrame")
        right.grid(row=0, column=2, sticky="e")
        for icon, action in (
            ("plus", self._open_quick),
            ("home", self._show_welcome),
            ("folder", lambda: self._open_panel("文件")),
            ("settings", lambda: self._open_panel("设置")),
            ("help", lambda: self._open_panel("帮助")),
        ):
            self._circle_icon(right, icon, action)

    def _circle_icon(self, parent, kind, action):
        """统一五个图标：44px 圆形按钮、20px 线描，Canvas 原生绘制。"""
        size, center = 44, 22
        c = tk.Canvas(
            parent, width=size, height=size, bg=BG,
            highlightthickness=0, bd=0, takefocus=1, cursor="hand2",
        )
        c.pack(side="left", padx=4)
        ring = c.create_oval(1.5, 1.5, 42.5, 42.5, fill=CARD,
                            outline=BORDER, width=1.2)
        fg = PRIMARY_DARK
        stroke = 1.9

        if kind == "plus":
            c.create_line(15, 22, 29, 22, fill=fg, width=2.25, capstyle=tk.ROUND)
            c.create_line(22, 15, 22, 29, fill=fg, width=2.25, capstyle=tk.ROUND)
        elif kind == "home":
            # 完整房屋剪影：屋顶、墙体、门和细小烟囱。
            c.create_line(12.5, 21.2, 22, 13.7, 31.5, 21.2,
                          fill=fg, width=stroke, capstyle=tk.ROUND,
                          joinstyle=tk.ROUND)
            c.create_line(15.7, 19.2, 15.7, 30.5, 28.3, 30.5, 28.3, 19.2,
                          fill=fg, width=stroke, capstyle=tk.ROUND,
                          joinstyle=tk.ROUND)
            c.create_line(20, 30.5, 20, 24.9, 24, 24.9, 24, 30.5,
                          fill=fg, width=1.5, joinstyle=tk.ROUND)
            c.create_line(27.3, 14.5, 27.3, 17.7,
                          fill=fg, width=1.6, capstyle=tk.ROUND)
        elif kind == "folder":
            # 文件夹的折角、标签及前面板，不是普通方框。
            c.create_polygon(
                12, 16.5, 18.5, 16.5, 21, 19, 30.7, 19,
                31, 29.3, 12, 29.3,
                fill=CARD, outline=fg, width=stroke, joinstyle=tk.ROUND,
            )
            c.create_line(12, 21.2, 31, 21.2,
                          fill=fg, width=1.35, capstyle=tk.ROUND)
        elif kind == "settings":
            # 八个真正凸起的齿，内圈留白；不是放射状太阳线。
            c.create_polygon(
                GEAR_COORDINATES,
                fill=fg, outline=fg, width=0.7, joinstyle=tk.ROUND,
            )
            c.create_oval(17.55, 17.55, 26.45, 26.45,
                          fill=CARD, outline=CARD, width=1)
            c.create_oval(19.2, 19.2, 24.8, 24.8,
                          fill=CARD, outline=fg, width=1.2)
        else:
            # 不依赖系统 emoji，使用同字体的可识别问号。
            c.create_text(22, 21.8, text="?", fill=fg,
                          font=(FONT, 19, "bold"), anchor="center")

        def hover(inside):
            c.itemconfigure(ring,
                            fill=LIGHT if inside else CARD,
                            outline=PRIMARY if inside else BORDER)
            # Center hole stays white as part of the gear drawing.
        c.bind("<Enter>", lambda event: hover(True))
        c.bind("<Leave>", lambda event: hover(False))
        c.bind("<Button-1>", lambda event: action())
        c.bind("<Return>", lambda event: action())
        c.bind("<space>", lambda event: action())
        return c

    def _build_tabs(self):
        tabs = ttk.Frame(self, style="App.TFrame", padding=(26, 0, 26, 13))
        tabs.grid(row=1, column=0, sticky="ew")
        for i, name in enumerate(SECTIONS):
            tabs.columnconfigure(i, weight=1, uniform="tabs")
            button = ttk.Button(tabs, text=name, style="Tab.TButton",
                                command=lambda n=name: self._switch(n))
            button.grid(row=0, column=i, sticky="ew", padx=4)
            self.tab_buttons[name] = button

    def _build_content(self):
        self.content = ttk.Frame(self, style="Soft.TFrame", padding=(0, 4, 0, 0))
        self.content.grid(row=2, column=0, sticky="nsew",
                          padx=30, pady=(0, 8))
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)
        self.pages = {}
        for section in SECTIONS:
            page = ttk.Frame(self.content, style="Soft.TFrame")
            page.grid(row=0, column=0, sticky="nsew")
            page.columnconfigure(0, weight=1)
            page.rowconfigure(2, weight=1)
            self.pages[section] = page
        for section in SECTIONS:
            if section == "收支记录":
                self._build_records_page()
            else:
                self._build_data_page(section)
        self._switch("成员")

    def _build_statusbar(self):
        bar = ttk.Frame(self, style="App.TFrame", padding=(30, 1, 30, 7))
        bar.grid(row=3, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)
        ttk.Label(bar, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Label(bar, text="Ctrl+Z 撤销  |  Ctrl+Y 重做  |  Ctrl+S 保存",
                  style="Status.TLabel").grid(row=0, column=1, sticky="e")

    def _make_tree(self, parent, columns, row, column=0):
        container = ttk.Frame(parent, style="Card.TFrame")
        container.grid(row=row, column=column, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        tree = ttk.Treeview(container, columns=[c[0] for c in columns],
                            show="headings", selectmode="browse", style="Data.Treeview")
        for key, label, width in columns:
            align = "w" if key in ("name", "member", "item", "time", "museum", "status") else "e"
            tree.heading(key, text=label)
            tree.column(key, width=width, minwidth=54, anchor=align, stretch=True)
        tree.tag_configure("even", background=CARD, foreground=TEXT)
        tree.tag_configure("odd", background=ALT, foreground=TEXT)
        tree.tag_configure("leader", background=LEADER, foreground=INK)
        tree.tag_configure("negative", foreground=DANGER)
        tree.tag_configure("blocked", foreground=DISABLED)
        scroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview,
                               style="Mint.Vertical.TScrollbar")
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        return tree

    def _build_data_page(self, section):
        page = self.pages[section]
        title = {"成员": "成员管理", "礼物": "礼物管理", "玩法": "玩法管理",
                 "积分统计": "积分排行榜"}[section]
        subtitles = {"成员": "管理大家的小积分", "礼物": "礼物价值、倍率和累计记录",
                     "玩法": "玩法参与与累计消耗", "积分统计": "查看全部历史积分与排行"}
        header = ttk.Frame(page, style="Soft.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        left = ttk.Frame(header, style="Soft.TFrame")
        left.grid(row=0, column=0, sticky="w")
        ttk.Label(left, text=title, style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(left, text=subtitles[section], style="PageMuted.TLabel").pack(
            anchor="w", pady=(4, 0))
        ops = ttk.Frame(header, style="Soft.TFrame")
        ops.grid(row=0, column=1, sticky="e")
        if section == "积分统计":
            ttk.Button(ops, text="导出 CSV", style="Primary.TButton",
                       command=self._export_csv).pack(side="left")
        else:
            ttk.Button(ops, text="+ 添加" + section, style="Primary.TButton",
                       command=lambda s=section: self._item_dialog(s)).pack(side="left", padx=3)
            ttk.Button(ops, text="编辑", style="Secondary.TButton",
                       command=lambda s=section: self._edit_selected(s)).pack(side="left", padx=3)
            ttk.Button(ops, text="删除", style="Danger.TButton",
                       command=lambda s=section: self._delete_selected(s)).pack(side="left", padx=3)
        stats = ttk.Frame(page, style="Soft.TFrame")
        stats.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        names = {
            "成员": ("成员总数", "当前总积分", "礼物积分"),
            "礼物": ("礼物种类", "累计个数", "累计积分"),
            "玩法": ("玩法种类", "累计次数", "累计花费"),
            "积分统计": ("上榜成员", "最高积分", "全员总积分"),
        }[section]
        labels = []
        for i, name in enumerate(names):
            stats.columnconfigure(i, weight=1, uniform="stats")
            block = ttk.Frame(stats, style="Metric.TFrame", padding=(17, 12))
            block.grid(row=0, column=i, sticky="ew", padx=5)
            ttk.Label(block, text=name, style="MetricCaption.TLabel").pack(anchor="w")
            lab = ttk.Label(block, text="--", style="MetricValue.TLabel")
            lab.pack(anchor="w", pady=(4, 0))
            labels.append(lab)
        self.stat_values[section] = labels
        table_box = ttk.Frame(page, style="TableCard.TFrame", padding=(12, 12))
        table_box.grid(row=2, column=0, sticky="nsew")
        table_box.rowconfigure(2, weight=1)
        table_box.columnconfigure(0, weight=1)
        controls = ttk.Frame(table_box, style="Card.TFrame")
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        controls.columnconfigure(0, weight=1)
        ttk.Label(controls, text="数据列表", style="Group.TLabel").grid(
            row=0, column=0, sticky="w")
        search = tk.StringVar()
        self.search_vars[section] = search
        ttk.Entry(controls, textvariable=search, width=20,
                  style="Mint.TEntry").grid(row=0, column=1, padx=5)
        search.trace_add("write", lambda *args, s=section: self._refresh_page(s))
        if section == "礼物":
            ttk.Button(controls, text="倍率设置", style="Compact.TButton",
                       command=lambda: self._open_panel("设置")).grid(row=0, column=2, padx=5)
        note = ttk.Label(table_box, text="", style="CardMuted.TLabel")
        note.grid(row=1, column=0, sticky="w", pady=(0, 4))
        self.empty_labels[section] = note
        tree = self._make_tree(table_box, FIELDS[section], 2)
        self.tables[section] = tree
        if section != "积分统计":
            tree.bind("<Double-1>", lambda event, s=section: self._edit_selected(s))

    def _build_records_page(self):
        page = self.pages["收支记录"]
        bar = ttk.Frame(page, style="Soft.TFrame")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        bar.columnconfigure(0, weight=1)
        ttk.Label(bar, text="收支记录", style="PageTitle.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Button(bar, text="撤销", style="Secondary.TButton",
                   command=self._undo).grid(row=0, column=1, padx=3)
        ttk.Button(bar, text="重做", style="Secondary.TButton",
                   command=self._redo).grid(row=0, column=2, padx=3)
        ttk.Button(bar, text="删除选中记录", style="Danger.TButton",
                   command=self._delete_record).grid(row=0, column=3, padx=3)
        ttk.Label(page, text="收礼 / 玩法消耗分栏查看，各自独立滚动",
                  style="PageMuted.TLabel").grid(row=1, column=0, sticky="w",
                                                  pady=(0, 8))
        pair = ttk.Frame(page, style="Soft.TFrame")
        pair.grid(row=2, column=0, sticky="nsew")
        for i, (key, title) in enumerate((("gift", "收礼记录"), ("play", "玩法消耗"))):
            pair.columnconfigure(i, weight=1, uniform="records")
            block = ttk.Frame(pair, style="TableCard.TFrame", padding=10)
            block.grid(row=0, column=i, sticky="nsew", padx=7)
            block.columnconfigure(0, weight=1)
            block.rowconfigure(2, weight=1)
            ttk.Label(block, text=title, style="Group.TLabel").grid(
                row=0, column=0, sticky="w", pady=(0, 7))
            empty = ttk.Label(block, text="", style="CardMuted.TLabel")
            empty.grid(row=1, column=0, sticky="w", pady=(0, 4))
            self.empty_labels["record_" + key] = empty
            self.record_tables[key] = self._make_tree(block, RECORD_FIELDS, 2)
        pair.rowconfigure(0, weight=1)

    def _switch(self, section):
        self.active_section = section
        self.pages[section].tkraise()
        for name, button in self.tab_buttons.items():
            button.configure(style="TabActive.TButton" if name == section else "Tab.TButton")
        self._refresh_page(section)

    def _refresh_all(self):
        calculated = self._calculate()
        for section in SECTIONS:
            self._refresh_page(section, calculated)
        orphans = calculated[-1]
        if orphans:
            self._status(f"提示：已跳过 {orphans} 条对象不存在的孤儿记录")

    def _refresh_page(self, section, calc=None):
        calc = calc if calc is not None else self._calculate()
        totals, gift_counts, gift_points, game_counts, game_points, _ = calc
        if section == "收支记录":
            self._refresh_records()
            return
        tree = self.tables.get(section)
        if tree is None:
            return
        tree.delete(*tree.get_children())
        rows = []
        values = []
        if section == "成员":
            for m in self.data["members"]:
                t = totals[m["id"]]
                rows.append((m["id"], (m["name"], number(t["base"]),
                       signed(t["gift"]), number(t["spent"]), number(t["total"])),
                       t["total"] < 0, False))
            values = [f"{len(rows)} 人", number(sum(x["total"] for x in totals.values())),
                      signed(sum(x["gift"] for x in totals.values()))]
        elif section == "礼物":
            for g in self.data["gifts"]:
                rate = self.data["settings"]["museum_rate" if g["is_museum"] else "normal_rate"]
                rows.append((g["id"], (g["name"], number(round(g["value"] * 10)),
                    "是" if g["is_museum"] else "否",
                    "已屏蔽" if g["blocked"] else "正常",
                    number(round(g["value"] * rate_tenths(rate))),
                    str(gift_counts.get(g["id"], 0)),
                    number(gift_points.get(g["id"], 0))), False, g["blocked"]))
            values = [f"{len(rows)} 种", f"{sum(gift_counts.values()):,}",
                      number(sum(gift_points.values()))]
        elif section == "玩法":
            for g in self.data["gameplays"]:
                rows.append((g["id"], (g["name"], number(round(g["cost"] * 10)),
                    str(game_counts.get(g["id"], 0)),
                    number(game_points.get(g["id"], 0))), False, False))
            values = [f"{len(rows)} 种", f"{sum(game_counts.values()):,}",
                      number(sum(game_points.values()))]
        else:
            members = self._lookup("members")
            ranking = sorted(totals.items(),
                             key=lambda x: (-x[1]["total"], members[x[0]]["name"]))
            for rank, (mid, t) in enumerate(ranking, 1):
                rows.append((mid, (str(rank), members[mid]["name"], number(t["base"]),
                    signed(t["gift"]), number(t["spent"]), number(t["total"])),
                    t["total"] < 0, False))
            values = [f"{len(rows)} 人",
                      number(max((x["total"] for x in totals.values()), default=0)),
                      number(sum(x["total"] for x in totals.values()))]
        for lab, text in zip(self.stat_values[section], values):
            lab.configure(text=text)
        query = self.search_vars[section].get().strip().lower()
        shown = 0
        for index, (ident, display, negative, blocked) in enumerate(rows):
            if query and query not in " ".join(map(str, display)).lower():
                continue
            tags = ["even" if shown % 2 == 0 else "odd"]
            if section == "积分统计" and display[0] == "1":
                tags.append("leader")
            if negative:
                tags.append("negative")
            if blocked:
                tags.append("blocked")
            tree.insert("", "end", iid=str(ident), values=display, tags=tags)
            shown += 1
        hints = {"成员": "还没有成员，点右上角「+ 添加成员」",
                 "礼物": "还没有礼物，点右上角「+ 添加礼物」",
                 "玩法": "还没有玩法，点右上角「+ 添加玩法」",
                 "积分统计": "还没有成员，先去成员页面添加"}
        self.empty_labels[section].configure(
            text=(hints[section] if not rows else
                  "没有匹配的结果，请调整搜索词" if not shown else ""))

    def _refresh_records(self):
        for key, table in self.record_tables.items():
            table.delete(*table.get_children())
            valid, _ = self._valid_records(key)
            for i, (r, member, item) in enumerate(reversed(valid)):
                if key == "gift":
                    count, points = r["count"], self._gift_points(r, item)
                else:
                    count, points = r["times"], -self._game_points(r, item)
                table.insert("", "end", iid=str(r["id"]), values=(
                    r["time"][5:16], member["name"], item["name"],
                    str(count), signed(points)),
                    tags=("even" if i % 2 == 0 else "odd",
                          "negative" if points < 0 else "even"))
            self.empty_labels["record_" + key].configure(
                text="暂无记录，可点击顶部「+」快速登记" if not valid else "")

    def _selected_id(self, section):
        selected = self.tables[section].selection()
        return int(selected[0]) if selected else None

    def _edit_selected(self, section):
        ident = self._selected_id(section)
        if ident is None:
            messagebox.showinfo("提示", "请先选中一行", parent=self._dialog_parent())
            return
        self._item_dialog(section, ident)

    def _item_dialog(self, section, ident=None):
        field = {"成员": "members", "礼物": "gifts", "玩法": "gameplays"}[section]
        current = self._lookup(field).get(ident)
        dlg = tk.Toplevel(self.root)
        dlg.title(("编辑" if current else "添加") + section)
        dlg.configure(bg=CARD)
        self._center_dialog(dlg, 420, 430)
        form = ttk.Frame(dlg, style="Card.TFrame", padding=22)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=("编辑" if current else "添加") + section,
                  style="Group.TLabel").pack(anchor="w", pady=(0, 14))
        specs = {
            "成员": [("name", "成员名字", "str"), ("base", "基础积分", "int")],
            "礼物": [("name", "礼物名字", "str"), ("value", "价值积分", "float"),
                   ("is_museum", "展馆礼物", "bool"), ("blocked", "已屏蔽", "bool")],
            "玩法": [("name", "玩法名字", "str"), ("cost", "花费积分", "int")],
        }[section]
        variables = {}
        for key, label, kind in specs:
            ttk.Label(form, text=label, style="Card.TLabel").pack(anchor="w", pady=(5, 2))
            val = current.get(key) if current else None
            if kind == "bool":
                var = tk.BooleanVar(value=bool(val))
                ttk.Checkbutton(form, variable=var, text="是",
                                style="Mint.TCheckbutton").pack(anchor="w")
            else:
                var = tk.StringVar(value=str(val) if val is not None else (
                    "0" if kind == "int" else ""))
                ttk.Entry(form, textvariable=var, style="Mint.TEntry").pack(fill="x")
            variables[key] = var

        def commit():
            values = {}
            for key, label, kind in specs:
                raw = variables[key].get()
                if kind == "str":
                    value = str(raw).strip()
                    if not value:
                        messagebox.showwarning("输入错误", f"{label}不能为空", parent=dlg)
                        return
                elif kind in ("int", "float"):
                    try:
                        value = float(raw) if kind == "float" else int(raw)
                        if kind == "float" and (not 0 <= value <= 100000000 or
                                                round(value * 10) != value * 10):
                            raise ValueError("礼物价值最多一位小数")
                    except ValueError:
                        messagebox.showwarning("输入错误", f"{label}格式无效；礼物价值最多一位小数", parent=dlg)
                        return
                    if value < 0 and key != "base":
                        messagebox.showwarning("输入错误", f"{label}不能为负", parent=dlg)
                        return
                else:
                    value = bool(raw)
                values[key] = value
            if any(x["name"] == values["name"] and x["id"] != ident for x in self.data[field]):
                messagebox.showwarning("名称重复", "名称已存在", parent=dlg)
                return
            if current and all(current.get(k) == v for k, v in values.items()):
                dlg.destroy()
                return
            self._remember()
            if field == "gifts":
                values["is_exhibit"] = values["is_museum"]
            if current:
                current.update(values)
            else:
                values["id"] = self._new_id()
                self.data[field].append(values)
            dlg.destroy()
            self._changed(section + "已保存")

        actions = ttk.Frame(form, style="Card.TFrame")
        actions.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Button(actions, text="取消", style="Secondary.TButton",
                   command=dlg.destroy).pack(side="right", padx=5)
        ttk.Button(actions, text="保存", style="Primary.TButton",
                   command=commit).pack(side="right")

    def _delete_selected(self, section):
        ident = self._selected_id(section)
        if ident is None:
            messagebox.showinfo("提示", "请先选中一行", parent=self._dialog_parent())
            return
        field = {"成员": "members", "礼物": "gifts", "玩法": "gameplays"}[section]
        item = self._lookup(field).get(ident)
        if not item:
            return
        # 保留历史记录：删除实体后相关记录变成孤儿，会被统计跳过。
        if not messagebox.askyesno("确认删除",
                                    f"确定删除「{item['name']}」吗？\n相关历史记录会保留但不参与统计。",
                                    parent=self._dialog_parent()):
            return
        self._remember()
        self.data[field] = [x for x in self.data[field] if x["id"] != ident]
        self._changed("已删除：" + item["name"])

    def _delete_record(self):
        ids = set()
        for table in self.record_tables.values():
            ids.update(int(x) for x in table.selection())
        if not ids:
            messagebox.showinfo("提示", "请先选择记录", parent=self._dialog_parent())
            return
        if not messagebox.askyesno("删除记录", "确定删除所选记录吗？", parent=self._dialog_parent()):
            return
        self._remember()
        for key in ("gift_records", "play_records"):
            self.data[key] = [r for r in self.data[key] if r["id"] not in ids]
        self._changed("记录已删除")

    def _record(self, kind, member_id, item_id, count):
        self._remember()
        base = {"id": self._new_id(), "member_id": member_id,
                "time": timestamp()}
        if kind == "gift":
            base.update(gift_id=item_id, count=count)
            self.data["gift_records"].append(base)
        else:
            base.update(gameplay_id=item_id, times=count)
            self.data["play_records"].append(base)
        self._changed("登记成功")

    def _open_quick(self):
        if self.quick_window and self.quick_window.winfo_exists():
            self.quick_window.lift()
            self.quick_window.focus_force()
            return
        if not self.data["members"]:
            self._status("还没有成员，请先添加成员")
            self._switch("成员")
            return
        win = tk.Toplevel(self.root)
        self.quick_window = win
        win.title("快速登记")
        win.minsize(370, 430)
        win.configure(bg=CARD)
        self._center_dialog(win, 420, 570)
        body = ttk.Frame(win, style="Card.TFrame", padding=18)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="快速登记", style="Group.TLabel").pack(anchor="w")
        ttk.Label(body, text="成员", style="Card.TLabel").pack(anchor="w")
        member_ids = {m["name"]: m["id"] for m in self.data["members"]}
        names = list(member_ids)
        combo = ttk.Combobox(body, textvariable=self.member_var, values=names,
                             state="readonly", style="Mint.TCombobox")
        combo.pack(fill="x", pady=(3, 13))
        if self.member_var.get() not in member_ids:
            self.member_var.set(names[0])
        ttk.Label(body, text="数量", style="Card.TLabel").pack(anchor="w")
        qty_box = ttk.Frame(body, style="Card.TFrame")
        qty_box.pack(fill="x", pady=(5, 12))
        qty_buttons = {}
        def set_qty(n):
            self.quantity_var.set(n)
            for k, b in qty_buttons.items():
                b.configure(style="TabActive.TButton" if k == n else "Tab.TButton")
        for n in (1, 5, 10, 50):
            btn = ttk.Button(qty_box, text=f"x{n}", style="Tab.TButton",
                             command=lambda q=n: set_qty(q))
            btn.pack(side="left", fill="x", expand=True, padx=2)
            qty_buttons[n] = btn
        set_qty(1)
        ttk.Label(body, text="礼物快捷键 1～9（Enter / Esc 关闭）",
                  style="CardMuted.TLabel").pack(anchor="w", pady=(2, 7))
        listbox = ttk.Frame(body, style="Card.TFrame")
        listbox.pack(fill="both", expand=True)
        counts = {}
        for r, _, gift in self._valid_records("gift", filtered=False)[0]:
            counts[gift["id"]] = counts.get(gift["id"], 0) + r["count"]
        ordered = sorted((g for g in self.data["gifts"] if not g["blocked"]),
                         key=lambda g: (-counts.get(g["id"], 0), g["id"]))
        quick_gifts = ordered[:9]
        for col in (0, 1, 2):
            listbox.columnconfigure(col, weight=1, uniform="quick")
        def register(gift):
            member_id = member_ids.get(self.member_var.get())
            if member_id is None:
                self._status("请先选择成员")
                return
            self._record("gift", member_id, gift["id"], self.quantity_var.get())
            set_qty(1)
            # 快捷键可以连续登记；按钮列表按打开时的排序固定
            self._status("收礼登记成功：" + gift["name"])
        for i, gift in enumerate(quick_gifts):
            rate = self.data["settings"]["museum_rate" if gift["is_museum"] else "normal_rate"]
            unit = number(round(gift["value"] * rate_tenths(rate)))
            ttk.Button(listbox, text=f"{i+1}. {gift['name']}\n{unit} 分/个",
                       style="Secondary.TButton", command=lambda g=gift: register(gift)).grid(
                           row=i//3, column=i%3, sticky="ew", padx=3, pady=4)
        if not quick_gifts:
            ttk.Label(listbox, text="暂无可登记礼物", style="CardMuted.TLabel").grid(
                row=0, column=0, columnspan=3)
        if len(ordered) > 9:
            def other_gifts():
                chooser = tk.Toplevel(win)
                chooser.title("其他礼物")
                chooser.configure(bg=CARD)
                self._center_dialog(chooser, 350, 190, parent=win)
                frame = ttk.Frame(chooser, style="Card.TFrame", padding=16)
                frame.pack(fill="both", expand=True)
                extras = ordered[9:]
                named = {f"{x['name']} (ID {x['id']})": x for x in extras}
                selection = tk.StringVar(value=next(iter(named)))
                ttk.Label(frame, text="选择其他礼物", style="Group.TLabel").pack(anchor="w")
                ttk.Combobox(frame, values=list(named), textvariable=selection,
                             state="readonly", style="Mint.TCombobox").pack(fill="x", pady=12)
                def choose_other():
                    gift = named.get(selection.get())
                    if gift:
                        register(gift)
                    chooser.destroy()
                ttk.Button(frame, text="登记", style="Primary.TButton",
                           command=choose_other).pack(fill="x")
            ttk.Button(body, text="更多礼物…", style="Compact.TButton",
                       command=other_gifts).pack(fill="x", pady=(5, 0))
        ttk.Button(body, text="登记玩法消耗", style="Secondary.TButton",
                   command=lambda: self._quick_play(member_ids)).pack(fill="x", pady=(10, 5))
        ttk.Button(body, text="关闭", style="Compact.TButton",
                   command=win.destroy).pack(fill="x")
        # 局部绑定，不给每个按钮绑定悬停事件；不影响主窗口 Ctrl+Z/Y。
        for i, gift in enumerate(quick_gifts, 1):
            win.bind(str(i), lambda event, g=gift: register(g))
        win.bind("<Return>", lambda event: win.destroy())
        win.bind("<Escape>", lambda event: win.destroy())
        win.after(50, win.focus_force)

    def _quick_play(self, member_ids):
        if not self.data["gameplays"]:
            self._status("暂无玩法，请先添加玩法")
            return
        win = tk.Toplevel(self.root)
        win.title("选择玩法")
        win.configure(bg=CARD)
        self._center_dialog(win, 360, 210)
        body = ttk.Frame(win, style="Card.TFrame", padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="玩法", style="Group.TLabel").pack(anchor="w", pady=(0, 8))
        names = [g["name"] for g in self.data["gameplays"]]
        var = tk.StringVar(value=names[0])
        ttk.Combobox(body, values=names, textvariable=var, state="readonly",
                     style="Mint.TCombobox").pack(fill="x")
        def ok():
            mid = member_ids.get(self.member_var.get())
            gameplay = next((g for g in self.data["gameplays"] if g["name"] == var.get()), None)
            if mid is not None and gameplay:
                self._record("play", mid, gameplay["id"], self.quantity_var.get())
                self.quantity_var.set(1)
                win.destroy()
        ttk.Button(body, text="确认扣分", style="Primary.TButton",
                   command=ok).pack(fill="x", pady=18)

    def _settings_editor(self, parent):
        ttk.Label(parent, text="礼物倍率", style="Group.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Label(parent, text="修改后，全部历史礼物积分与排行榜立即按新倍率重算。",
                  style="CardMuted.TLabel").pack(anchor="w", pady=(0, 13))
        vals = {}
        for key, title in (("museum_rate", "展馆礼物倍率"),
                           ("normal_rate", "普通礼物倍率")):
            ttk.Label(parent, text=title, style="Card.TLabel").pack(anchor="w", pady=(4, 2))
            var = tk.StringVar(value=f"{self.data['settings'][key]:.1f}")
            ttk.Entry(parent, textvariable=var, style="Mint.TEntry",
                      width=12).pack(anchor="w")
            vals[key] = var
        def save():
            try:
                changes = {key: parse_rate(var.get()) for key, var in vals.items()}
            except ValueError as exc:
                messagebox.showwarning("倍率无效", str(exc), parent=parent.winfo_toplevel())
                return
            if all(self.data["settings"][k] == v for k, v in changes.items()):
                self._status("倍率未变化")
                return
            self._remember()
            self.data["settings"].update(changes)
            self.data["settings"]["exhibit_rate"] = changes["museum_rate"]
            self._changed("倍率已更新，全部统计已重新计算")
        ttk.Button(parent, text="保存倍率", style="Primary.TButton",
                   command=save).pack(anchor="w", pady=(18, 0))

    def _open_panel(self, category):
        win = tk.Toplevel(self.root)
        win.title(f"{APP} - {category}")
        win.minsize(700, 430)
        win.configure(bg=BG)
        self._center_dialog(win, 760, 480)
        outer = ttk.Frame(win, style="Card.TFrame", padding=20)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(1, weight=1)
        ttk.Label(outer, text=category + "管理" if category != "帮助" else "帮助中心",
                  style="Group.TLabel").grid(row=0, column=0, columnspan=2,
                                             sticky="w", pady=(0, 15))
        nav = ttk.Frame(outer, style="Soft.TFrame", padding=10)
        nav.grid(row=1, column=0, sticky="nsw", padx=(0, 15))
        detail = ttk.Frame(outer, style="Card.TFrame", padding=14)
        detail.grid(row=1, column=1, sticky="nsew")
        choices = {
            "文件": [("导入 DeepSeek 旧版数据…", "自动转换旧版字段和时间；导入前预览并备份现有数据。", self._import_deepseek),
                   ("打开数据文件…", "从外部 JSON 文件导入完整数据。", self._open_json_file),
                   ("打开数据文件夹", "打开自动保存的数据目录。", self._open_data_folder),
                   ("备份管理…", "查看历史备份、恢复备份。", self._backup_manager),
                   ("导出排行 CSV…", "导出全部积分排行榜。", self._export_csv)],
            "设置": [("礼物倍率", "", None),
                   ("在线更新", "检查服务器上的新版本并选择是否升级。", self._check_updates),
                   ("更新地址", "设置可信 HTTPS 更新源。", self._edit_update_url),
                   ("保存说明", "数据变更 300ms 内自动保存；最多保留 10 份历史备份。", None)],
            "帮助": [("版本信息", f"当前程序版本：v{APP_VERSION}，可在设置中检查更新。", None),
                   ("快速登记", "顶部「+」打开；数字键 1～9 登记对应礼物。", None),
                   ("积分规则", "礼物价值 × 礼物倍率 × 数量；玩法花费 × 次数。", None),
                   ("键盘快捷键", "Ctrl+Z 撤销；Ctrl+Y 重做；Ctrl+S 立即保存。", None),
                   ("数据位置", "与 DeepSeek 一致：%LocalAppData%\\沅神启动\\积分数据.json", None)],
        }[category]
        def choose(index):
            for child in detail.winfo_children():
                child.destroy()
            label, description, action = choices[index]
            if category == "设置" and index == 0:
                self._settings_editor(detail)
                return
            ttk.Label(detail, text=label, style="Group.TLabel").pack(
                anchor="w", pady=(0, 14))
            ttk.Label(detail, text=description, style="Card.TLabel",
                      wraplength=360, justify="left").pack(anchor="w")
            if action:
                ttk.Button(detail, text="执行操作", style="Primary.TButton",
                           command=action).pack(anchor="w", pady=(24, 0))
        for i, (title, _, _) in enumerate(choices):
            ttk.Button(nav, text=title, style="Secondary.TButton", width=18,
                       command=lambda j=i: choose(j)).pack(fill="x", pady=4)
        choose(0)
        footer = ttk.Frame(outer, style="Card.TFrame")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(15, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Button(footer, text="返回", style="Secondary.TButton",
                   command=win.destroy).grid(row=0, column=1, padx=5)
        def home():
            win.destroy()
            self._show_welcome()
        ttk.Button(footer, text="返回开始页", style="Secondary.TButton",
                   command=home).grid(row=0, column=2)

    # 在线更新（仅 Python 标准库，网络操作在工作线程中进行）
    def _get_update_url(self):
        try:
            return next((x.strip() for x in
                (self.base_dir / UPDATE_FILENAME).read_text(encoding="utf-8-sig").splitlines()
                if x.strip() and not x.lstrip().startswith("#")), "")
        except (OSError, UnicodeError):
            return ""

    @staticmethod
    def _https_url(value):
        parts = urllib.parse.urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname or parts.username
                or parts.password or any(c in value for c in ("\\r", "\\n", "\\t"))):
            raise ValueError("更新地址必须使用 HTTPS，不能包含账号密码")
        return value

    @staticmethod
    def _version(value):
        v = str(value).lstrip("vV").strip()
        if not re.fullmatch(r"\d+(?:\.\d+){1,3}", v):
            raise ValueError("版本号格式不正确")
        pieces = [int(n) for n in v.split(".")]
        return tuple((pieces + [0, 0, 0, 0])[:4])

    def _edit_update_url(self):
        parent = self._dialog_parent()
        dialog = tk.Toplevel(parent)
        dialog.title("在线更新设置")
        dialog.configure(bg=CARD)
        self._center_dialog(dialog, 555, 260, parent=parent)
        frame = ttk.Frame(dialog, style="Card.TFrame", padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="在线更新地址", style="Group.TLabel").pack(anchor="w")
        ttk.Label(frame, text="填写可信发布者提供的 HTTPS latest.json 地址。留空则关闭联网检查。",
                  style="Card.TLabel", wraplength=500).pack(anchor="w", pady=(10, 9))
        value = tk.StringVar(value=self._get_update_url())
        ttk.Entry(frame, textvariable=value, style="Mint.TEntry").pack(fill="x")
        ttk.Label(frame, text="新版本只在你确认后才会下载、安装。",
                  style="CardMuted.TLabel").pack(anchor="w", pady=(12, 0))
        actions = ttk.Frame(frame, style="Card.TFrame")
        actions.pack(side="bottom", fill="x")
        def save_url():
            url = value.get().strip()
            try:
                if url:
                    self._https_url(url)
                cfg = self.base_dir / UPDATE_FILENAME
                tmp = cfg.with_suffix(".tmp")
                tmp.write_text(url + "\n", encoding="utf-8")
                os.replace(tmp, cfg)
            except (OSError, ValueError) as exc:
                messagebox.showerror("保存失败", str(exc), parent=dialog)
                return
            dialog.destroy()
            self._status("更新地址已保存" if url else "已关闭自动检查更新")
        ttk.Button(actions, text="取消", style="Secondary.TButton",
                   command=dialog.destroy).pack(side="right", padx=(7, 0))
        ttk.Button(actions, text="保存", style="Primary.TButton",
                   command=save_url).pack(side="right")

    def _check_updates(self, manual=True):
        if self.update_busy:
            self._status("正在执行更新检查")
            return
        url = self._get_update_url()
        if not url:
            if manual:
                self._edit_update_url()
            return
        try:
            self._https_url(url)
        except ValueError as exc:
            if manual:
                messagebox.showerror("更新地址无效", str(exc), parent=self._dialog_parent())
            return
        self.update_busy = True
        self._status("正在检查在线更新…")
        def work():
            try:
                request = urllib.request.Request(url, headers={"User-Agent":"YuanshenStart/"+APP_VERSION})
                with urllib.request.urlopen(request, timeout=12, context=ssl.create_default_context()) as response:
                    self._https_url(response.geturl())
                    raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError("版本清单超过 64 KB")
                info = json.loads(raw.decode("utf-8-sig"))
                if not isinstance(info, dict):
                    raise ValueError("版本清单不是 JSON 对象")
                version = str(info["version"])
                self._version(version)
                self._https_url(str(info["exe_url"]))
                sha = str(info["sha256"]).lower()
                if not re.fullmatch(r"[0-9a-f]{64}", sha):
                    raise ValueError("无效的 SHA-256 校验值")
                info["version"] = version
                info["sha256"] = sha
                info["notes"] = str(info.get("notes", ""))[:1200]
                self.update_events.put(("checked", info, manual))
            except Exception as exc:
                self.update_events.put(("error", str(exc), manual))
        threading.Thread(target=work, daemon=True).start()

    def _download_update(self, info):
        if not getattr(sys, "frozen", False) or os.name != "nt":
            self.update_busy = False
            messagebox.showinfo("更新提示",
                "当前运行的是 Python 源码；联网安装仅支持已打包的 Windows EXE。",
                parent=self._dialog_parent())
            return
        exe = Path(sys.executable).resolve()
        stage = exe.with_name(exe.name + ".new")
        temp = exe.with_name(exe.name + ".part")
        self._status("正在下载 v" + info["version"])
        def work():
            try:
                digest = hashlib.sha256()
                size = 0
                with urllib.request.urlopen(
                    urllib.request.Request(info["exe_url"], headers={"User-Agent":"YuanshenStart/"+APP_VERSION}),
                    timeout=25, context=ssl.create_default_context()
                ) as response:
                    self._https_url(response.geturl())
                    if int(response.headers.get("Content-Length", "0")) > 300 * 1024 * 1024:
                        raise ValueError("更新文件过大")
                    with temp.open("wb") as target:
                        while chunk := response.read(256 * 1024):
                            size += len(chunk)
                            if size > 300 * 1024 * 1024:
                                raise ValueError("更新文件过大")
                            target.write(chunk)
                            digest.update(chunk)
                        target.flush()
                        os.fsync(target.fileno())
                if size < 10000 or temp.open("rb").read(2) != b"MZ":
                    raise ValueError("下载文件不是 Windows EXE")
                if digest.hexdigest() != info["sha256"]:
                    raise ValueError("SHA-256 校验失败，已取消安装")
                os.replace(temp, stage)
                self.update_events.put(("ready", str(stage), info))
            except Exception as exc:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass
                self.update_events.put(("download_error", str(exc), None))
        threading.Thread(target=work, daemon=True).start()

    def _start_installer(self, stage):
        """Windows PowerShell 等本进程关闭后原子换版，并保留 previous.exe。"""
        exe = Path(sys.executable).resolve()
        staged = Path(stage).resolve()
        if staged.parent != exe.parent or not staged.is_file():
            raise OSError("下载文件位置不正确")
        def quote(p):
            return "'" + str(p).replace("'", "''") + "'"
        previous = exe.with_name(exe.stem + ".previous.exe")
        script = ("$ErrorActionPreference='Stop'\n"
                  f"$old={quote(exe)}\n$new={quote(staged)}\n"
                  f"$backup={quote(previous)}\n$folder={quote(exe.parent)}\n"
                  f"try {{ Wait-Process -Id {os.getpid()} -Timeout 90 -ErrorAction SilentlyContinue }} catch {{}}\n"
                  "for ($i=0; $i -lt 60; $i++) {\n"
                  " try {\n"
                  "  [System.IO.File]::Replace($new,$old,$backup,$true)\n"
                  "  Start-Process -FilePath $old -WorkingDirectory $folder\n"
                  "  exit 0\n"
                  " } catch { Start-Sleep -Milliseconds 800 }\n"
                  "}\n")
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
             "-EncodedCommand", encoded],
            cwd=str(exe.parent),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _poll_updates(self):
        try:
            while True:
                event, data, extra = self.update_events.get_nowait()
                if event == "checked":
                    self.update_busy = False
                    if self._version(data["version"]) <= self._version(APP_VERSION):
                        self._status(f"已是最新版 v{APP_VERSION}")
                        if extra:
                            messagebox.showinfo("检查更新", f"当前已是最新版 v{APP_VERSION}",
                                                parent=self._dialog_parent())
                    elif messagebox.askyesno(
                        "发现新版本", f"当前 v{APP_VERSION} → 最新 v{data['version']}\n\n"
                        + data["notes"] + "\n\n确认下载并安装吗？",
                        parent=self._dialog_parent(),
                    ):
                        self.update_busy = True
                        self._download_update(data)
                elif event in ("error", "download_error"):
                    self.update_busy = False
                    self._status("联网更新失败：" + str(data)[:90])
                    if event == "download_error" or extra:
                        messagebox.showerror("在线更新失败", str(data),
                                             parent=self._dialog_parent())
                elif event == "ready":
                    self.update_busy = False
                    if not self._save_now():
                        messagebox.showerror("无法更新", "积分数据未能保存，已取消替换程序。",
                                             parent=self._dialog_parent())
                        continue
                    try:
                        self._start_installer(data)
                    except (OSError, ValueError) as exc:
                        messagebox.showerror("无法启动安装", str(exc),
                                             parent=self._dialog_parent())
                    else:
                        self.root.destroy()
                        return
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(200, self._poll_updates)

    def _reload_current_file(self, event=None):
        if self.dirty and not messagebox.askyesno(
            "重新载入",
            "当前有尚未保存的改动。重新载入将放弃这些改动。继续吗？",
            parent=self._dialog_parent(),
        ):
            return
        try:
            reloaded = self._read_json(self.data_path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            messagebox.showerror("重新载入失败", str(exc), parent=self._dialog_parent())
            return
        if reloaded == self.data:
            self._status("数据已是最新")
            return
        if self.autosave_job is not None:
            self.after_cancel(self.autosave_job)
            self.autosave_job = None
        self._remember()
        self.data = reloaded
        self.last_saved_text = self._json_text()
        self.dirty = False
        self._refresh_all()
        self._status("已从磁盘重新载入数据")

    def _open_data_folder(self):
        # Windows Explorer 原生命令，不引入 subprocess。
        try:
            os.startfile(str(self.data_dir))
        except (OSError, AttributeError) as exc:
            messagebox.showinfo("数据目录", f"{self.data_dir}\n{exc}", parent=self._dialog_parent())

    def _backup_manager(self):
        win = tk.Toplevel(self.root)
        win.title("备份管理")
        win.configure(bg=CARD)
        self._center_dialog(win, 780, 420)
        frame = ttk.Frame(win, style="Card.TFrame", padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        ttk.Label(frame, text="备份历史（最多保留 10 份）",
                  style="Group.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        cols = (("time", "时间", 165), ("count", "记录数", 85),
                ("size", "文件大小", 90), ("name", "文件名", 320))
        tree = self._make_tree(frame, cols, 1)
        paths = {}
        def refill():
            tree.delete(*tree.get_children())
            paths.clear()
            for i, path in enumerate(self._history_paths()):
                try:
                    data = self._read_json(path)
                    count = len(data["gift_records"]) + len(data["play_records"])
                    size = f"{path.stat().st_size / 1024:.1f} KB"
                    mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                except (OSError, ValueError, TypeError):
                    count, size, mtime = "损坏", "?", "未知"
                iid = str(i)
                tree.insert("", "end", iid=iid,
                            values=(mtime, count, size, path.name),
                            tags=("odd" if i % 2 else "even",))
                paths[iid] = path
        refill()
        commands = ttk.Frame(frame, style="Card.TFrame")
        commands.grid(row=2, column=0, sticky="e", pady=(12, 0))
        def restore():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("提示", "请选择一份备份", parent=win)
                return
            chosen = paths[selected[0]]
            try:
                restored = self._read_json(chosen)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                messagebox.showerror("备份不可用", str(exc), parent=win)
                return
            if not messagebox.askyesno(
                "恢复备份",
                "将先保存当前数据为「积分数据.恢复前.json」，"
                "再恢复选中的备份。此操作支持 Ctrl+Z 撤销。\n确定吗？",
                parent=win,
            ):
                return
            # 先把当前尚未落盘的改动写到独立文件，再覆盖主文件。
            before_path = self.data_dir / "积分数据.恢复前.json"
            try:
                temp_before = self.data_dir / "积分数据.恢复前.json.tmp"
                with temp_before.open("w", encoding="utf-8") as f:
                    f.write(self._json_text())
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_before, before_path)
                incoming = json.dumps(restored, ensure_ascii=False,
                                      indent=2, sort_keys=True) + "\n"
                # 恢复时同样先生成旧主文件备份。
                self._atomic_write(incoming, backup=True)
            except (OSError, ValueError, TypeError) as exc:
                messagebox.showerror("恢复失败", str(exc), parent=win)
                return
            self._remember()
            self.data = restored
            self.last_saved_text = incoming
            self.dirty = False
            if self.autosave_job is not None:
                self.after_cancel(self.autosave_job)
                self.autosave_job = None
                self._refresh_all()
            self._status("备份已恢复；恢复前数据已保留")
            refill()
        ttk.Button(commands, text="打开数据文件夹", style="Secondary.TButton",
                   command=self._open_data_folder).pack(side="left", padx=5)
        ttk.Button(commands, text="恢复选中备份", style="Primary.TButton",
                   command=restore).pack(side="left", padx=5)
        ttk.Button(commands, text="关闭", style="Secondary.TButton",
                   command=win.destroy).pack(side="left", padx=5)

    def _import_deepseek(self):
        """一次性导入旧版数据，不改写或删除 DeepSeek 原文件。"""
        local = os.environ.get("LOCALAPPDATA", "")
        candidate = Path(local) / "沅神启动" / DATA_NAME if local else None
        if candidate and candidate.is_file():
            if not messagebox.askyesno(
                "继承 DeepSeek v3.4",
                "找到旧版数据：\\n" + str(candidate) +
                "\\n\\n是否导入？旧数据文件保持原样。"
                "\\n若不是这份文件，点「否」可手动选择 JSON。",
                parent=self._dialog_parent(),
            ):
                candidate = None
        else:
            candidate = None
        if candidate is None:
            selected = filedialog.askopenfilename(
                title="选择 DeepSeek v3.4 的积分数据.json",
                filetypes=[("JSON 文件", "*.json")],
                parent=self._dialog_parent(),
            )
            if not selected:
                return
            candidate = Path(selected)
        self._import_legacy_path(candidate)

    def _import_legacy_path(self, path):
        try:
            with Path(path).open("r", encoding="utf-8-sig") as handle:
                incoming, conversions = normalize_deepseek_legacy(json.load(handle))
            # 检查对象关联但保留无效对象供后续核对
            member_ids = {x["id"] for x in incoming["members"]}
            gift_ids = {x["id"] for x in incoming["gifts"]}
            play_ids = {x["id"] for x in incoming["gameplays"]}
            orphans = sum(
                r["member_id"] not in member_ids or r["gift_id"] not in gift_ids
                for r in incoming["gift_records"]
            ) + sum(
                r["member_id"] not in member_ids or r["gameplay_id"] not in play_ids
                for r in incoming["play_records"]
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            messagebox.showerror("导入失败", str(exc), parent=self._dialog_parent())
            return
        if not messagebox.askyesno(
            "确认导入",
            f"识别到 {len(incoming['members'])} 位成员、"
            f"{len(incoming['gifts'])} 种礼物、"
            f"{len(incoming['gameplays'])} 种玩法，"
            f"{len(incoming['gift_records']) + len(incoming['play_records'])} 条收支记录。"
            + (f"\\n其中 {orphans} 条记录关联对象缺失，统计时将跳过。" if orphans else "")
            + (f"\\n已规范化 {len(conversions)} 条记录时间。" if conversions else "")
            + f"\\n来源：{path}"
            + "\\n\\n将替换当前新版数据。会先单独备份当前积分和所选旧文件。继续吗？",
            parent=self._dialog_parent(),
        ):
            return
        # Every import gets a unique pre-import snapshot: no old backup overwritten.
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        pre = self.data_dir / f"积分数据.导入前-{stamp}.json"
        legacy_backup = self.data_dir / f"积分数据.DeepSeek来源-{stamp}.json"
        try:
            with pre.open("x", encoding="utf-8") as f:
                f.write(self._json_text())
                f.flush()
                os.fsync(f.fileno())
            shutil.copy2(path, legacy_backup)
        except OSError as exc:
            messagebox.showerror("无法创建导入前备份", str(exc), parent=self._dialog_parent())
            return
        self._remember()
        self.data = incoming
        self._changed("已继承旧版数据，正在自动保存")
        messagebox.showinfo(
            "导入完成",
            "DeepSeek 原始文件未修改。\\n新版数据将在 300ms 内自动保存。"
            f"\\n导入前备份：{pre.name}"
            f"\\n旧版来源备份：{legacy_backup.name}",
            parent=self._dialog_parent(),
        )

    def _open_json_file(self):
        path = filedialog.askopenfilename(
            title="打开 JSON 数据文件",
            filetypes=[("JSON 文件", "*.json")],
            parent=self._dialog_parent(),
        )
        if not path:
            return
        try:
            incoming = self._read_json(Path(path))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            messagebox.showerror("打开失败", str(exc), parent=self._dialog_parent())
            return
        if not messagebox.askyesno(
            "导入数据",
            "即将使用所选文件替换当前内存数据，并自动保存至固定数据目录。\n"
            "当前数据可通过撤销恢复。是否继续？",
            parent=self._dialog_parent(),
        ):
            return
        self._remember()
        self.data = incoming
        self._changed("已导入 JSON 数据，正在自动保存")

    def _import_csv(self):
        path = filedialog.askopenfilename(title="导入成员 CSV",
                                          filetypes=[("CSV 文件", "*.csv")],
                                          parent=self._dialog_parent())
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                source_rows = list(csv.reader(f))
            pending = {}
            for index, line in enumerate(source_rows):
                if not line or not line[0].strip():
                    continue
                name = line[0].strip()
                base_str = line[1].strip() if len(line) > 1 else ""
                # 首行常见表头自动跳过。
                if index == 0 and (
                    name.lower() in ("name", "member", "成员", "成员名字", "名字", "姓名")
                    or base_str.lower() in ("base", "基础积分", "积分")
                ):
                    continue
                base = int(base_str) if base_str else 0
                pending[name] = base
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            messagebox.showerror("导入失败", f"CSV 格式或积分数值无效：\n{exc}",
                                 parent=self._dialog_parent())
            return
        existing = {m["name"]: m for m in self.data["members"]}
        add = sum(1 for name in pending if name not in existing)
        update = sum(1 for name in pending if name in existing)
        if not pending:
            messagebox.showinfo("导入结果", "没有可导入的成员", parent=self._dialog_parent())
            return
        if any(name not in existing or existing[name]["base"] != base
               for name, base in pending.items()):
            self._remember()
            for name, base in pending.items():
                if name in existing:
                    existing[name]["base"] = base
                else:
                    self.data["members"].append(
                        {"id": self._new_id(), "name": name, "base": base})
            self._changed(f"CSV 导入完成：新增 {add} 人 / 更新 {update} 人")
        messagebox.showinfo("导入成功", f"新增 {add} 人 / 更新 {update} 人",
                            parent=self._dialog_parent())

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            title="导出排行榜", defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")], parent=self._dialog_parent())
        if not path:
            return
        totals = self._calculate()[0]
        people = self._lookup("members")
        ranking = sorted(totals.items(),
                         key=lambda p: (-p[1]["total"], people[p[0]]["name"]))
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                out = csv.writer(f)
                out.writerow(["排名", "名字", "基础积分", "礼物积分", "玩法花费", "总积分"])
                for i, (mid, t) in enumerate(ranking, 1):
                    out.writerow([i, people[mid]["name"], number(t["base"]),
                                  number(t["gift"]), number(t["spent"]),
                                  number(t["total"])])
            self._status("CSV 已导出：" + str(path))
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self._dialog_parent())

    def _show_welcome(self):
        if self.welcome is not None and self.welcome.winfo_exists():
            self.welcome.lift()
            return
        self.welcome = ttk.Frame(self, style="App.TFrame")
        self.welcome.place(x=0, y=0, relwidth=1, relheight=1)
        central = ttk.Frame(self.welcome, style="App.TFrame")
        central.place(relx=.5, rely=.47, anchor="center")
        if self.logo:
            ttk.Label(central, image=self.logo, style="App.TLabel").pack(pady=(0, 15))
        else:
            ttk.Label(central, text="YS", style="Title.TLabel").pack(pady=(0, 15))
        ttk.Label(central, text=APP, style="Title.TLabel").pack()
        ttk.Label(central, text="直播 · 聚会积分管理",
                  style="Muted.TLabel").pack(pady=(5, 26))
        buttons = [
            ("开始使用", self._enter_main, "Primary.TButton"),
            ("文件管理", lambda: self._open_panel("文件"), "Secondary.TButton"),
            ("设置", lambda: self._open_panel("设置"), "Secondary.TButton"),
            ("帮助", lambda: self._open_panel("帮助"), "Secondary.TButton"),
        ]
        for label, action, sty in buttons:
            ttk.Button(central, text=label, width=30, style=sty,
                       command=action).pack(fill="x", pady=5)
        ttk.Label(central, text="让每一份快乐都有迹可循",
                  style="Muted.TLabel").pack(pady=(22, 0))

    def _enter_main(self):
        if self.welcome is not None and self.welcome.winfo_exists():
            self.welcome.destroy()
            self.welcome = None
        self._switch("成员")

    def _close(self):
        if not self._save_now():
            messagebox.showerror("无法安全退出",
                                 "自动保存失败，程序将继续保持打开。\n"
                                 "请检查数据文件夹权限或磁盘空间。",
                                 parent=self._dialog_parent())
            return
        self.root.destroy()


def main():
    root = tk.Tk()
    YuanshenApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
