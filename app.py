from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps
from rembg import new_session, remove

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    DND_FILES = None
    TkinterDnD = None

APP_TITLE = "人物切り抜きツール"
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
MODELS = {
    "人物優先（おすすめ）": "u2net_human_seg",
    "一般被写体": "u2net",
    "高速・軽量": "u2netp",
}

@dataclass
class FileItem:
    path: Path
    status: str = "待機"
    output: Path | None = None
    error: str = ""

class PersonCutoutApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("920x680")
        self.root.minsize(760, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.items: list[FileItem] = []
        self.processing = False
        self.cancel_requested = False
        self.events: queue.Queue = queue.Queue()
        self.output_dir = tk.StringVar(value=str(Path.home() / "Pictures" / "BackgroundRemoved"))
        self.model_label = tk.StringVar(value="人物優先（おすすめ）")
        self.alpha_matting = tk.BooleanVar(value=False)
        self.status_text = tk.StringVar(value="画像を追加してください")
        self.count_text = tk.StringVar(value="0件")

        self._build_style()
        self._build_ui()
        self.root.after(100, self._poll_events)

    def _build_style(self):
        style = ttk.Style()
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("Title.TLabel", font=("TkDefaultFont", 20, "bold"))
        style.configure("Sub.TLabel", foreground="#526173")
        style.configure("Accent.TButton", font=("TkDefaultFont", 11, "bold"), padding=(16, 10))
        style.configure("Treeview", rowheight=28)

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        ttk.Label(outer, text=APP_TITLE, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(outer, text="複数画像から人物・主要被写体を切り抜き、透過PNGで保存します。", style="Sub.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 14))

        self.drop_frame = tk.Frame(outer, bg="#eef6fa", highlightbackground="#38a3c7", highlightthickness=2, height=110, cursor="hand2")
        self.drop_frame.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        self.drop_frame.grid_propagate(False)
        self.drop_frame.columnconfigure(0, weight=1)
        tk.Label(self.drop_frame, text="画像をここにドラッグ＆ドロップ", bg="#eef6fa", fg="#164e63", font=("TkDefaultFont", 14, "bold")).grid(row=0, column=0, pady=(24, 4))
        tk.Label(self.drop_frame, text="またはクリックして複数選択", bg="#eef6fa", fg="#4b6472").grid(row=1, column=0)
        self.drop_frame.bind("<Button-1>", lambda _e: self.select_files())
        for child in self.drop_frame.winfo_children(): child.bind("<Button-1>", lambda _e: self.select_files())
        if DND_AVAILABLE:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)

        list_frame = ttk.Frame(outer)
        list_frame.grid(row=3, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(list_frame, columns=("name", "status", "detail"), show="headings", selectmode="extended")
        self.tree.heading("name", text="ファイル名")
        self.tree.heading("status", text="状態")
        self.tree.heading("detail", text="出力先 / エラー")
        self.tree.column("name", width=280, anchor="w")
        self.tree.column("status", width=90, anchor="center")
        self.tree.column("detail", width=400, anchor="w")
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        tools = ttk.Frame(outer)
        tools.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(tools, text="画像追加", command=self.select_files).pack(side="left")
        ttk.Button(tools, text="選択削除", command=self.remove_selected).pack(side="left", padx=6)
        ttk.Button(tools, text="全削除", command=self.clear_files).pack(side="left")
        ttk.Label(tools, textvariable=self.count_text).pack(side="right")

        settings = ttk.LabelFrame(outer, text="処理設定", padding=12)
        settings.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="出力先").grid(row=0, column=0, sticky="w")
        ttk.Entry(settings, textvariable=self.output_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(settings, text="参照", command=self.select_output).grid(row=0, column=2)
        ttk.Label(settings, text="モデル").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(settings, textvariable=self.model_label, values=list(MODELS), state="readonly", width=24).grid(row=1, column=1, sticky="w", padx=8, pady=(10, 0))
        ttk.Checkbutton(settings, text="境界を精密化（遅くなります）", variable=self.alpha_matting).grid(row=1, column=2, sticky="e", pady=(10, 0))

        bottom = ttk.Frame(outer)
        bottom.grid(row=6, column=0, sticky="ew", pady=(14, 0))
        bottom.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        ttk.Label(bottom, textvariable=self.status_text).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.start_button = ttk.Button(bottom, text="背景除去を開始", style="Accent.TButton", command=self.start_processing)
        self.start_button.grid(row=0, column=1, rowspan=2, sticky="e")
        self.cancel_button = ttk.Button(bottom, text="中止", command=self.request_cancel, state="disabled")
        self.cancel_button.grid(row=0, column=2, rowspan=2, padx=(8, 0))
        ttk.Button(bottom, text="出力先を開く", command=self.open_output).grid(row=0, column=3, rowspan=2, padx=(8, 0))

    def _on_drop(self, event):
        paths = [Path(p) for p in self.root.tk.splitlist(event.data)]
        self.add_paths(paths)

    def select_files(self):
        if self.processing: return
        paths = filedialog.askopenfilenames(title="画像を選択", filetypes=[("画像", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("すべて", "*.*")])
        self.add_paths(Path(p) for p in paths)

    def add_paths(self, paths):
        existing = {str(x.path.resolve()) for x in self.items}
        added = 0
        for path in paths:
            if path.is_dir():
                candidates = sorted(p for p in path.rglob("*") if p.suffix.lower() in SUPPORTED)
            else: candidates = [path]
            for p in candidates:
                if p.exists() and p.suffix.lower() in SUPPORTED and str(p.resolve()) not in existing:
                    self.items.append(FileItem(p.resolve()))
                    existing.add(str(p.resolve())); added += 1
        self._refresh_tree()
        self.status_text.set(f"{added}件追加しました" if added else "追加可能な新しい画像がありません")

    def remove_selected(self):
        if self.processing: return
        indices = sorted((int(i) for i in self.tree.selection()), reverse=True)
        for i in indices:
            if 0 <= i < len(self.items): self.items.pop(i)
        self._refresh_tree()

    def clear_files(self):
        if self.processing: return
        self.items.clear(); self.progress["value"] = 0; self._refresh_tree(); self.status_text.set("画像を追加してください")

    def select_output(self):
        path = filedialog.askdirectory(title="出力先を選択", initialdir=self.output_dir.get())
        if path: self.output_dir.set(path)

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, item in enumerate(self.items):
            detail = item.error or (str(item.output) if item.output else str(item.path.parent))
            self.tree.insert("", "end", iid=str(i), values=(item.path.name, item.status, detail))
        done = sum(x.status == "完了" for x in self.items)
        errors = sum(x.status == "エラー" for x in self.items)
        self.count_text.set(f"合計 {len(self.items)}件 / 完了 {done}件 / エラー {errors}件")

    def start_processing(self):
        if self.processing or not self.items:
            if not self.items: messagebox.showinfo(APP_TITLE, "画像を追加してください。")
            return
        out = Path(self.output_dir.get()).expanduser()
        try: out.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"出力先を作成できません。\n{e}"); return
        self.processing = True; self.cancel_requested = False
        self.start_button.configure(state="disabled"); self.cancel_button.configure(state="normal")
        self.progress["value"] = 0; self.status_text.set("AIモデルを準備しています。初回はダウンロードに時間がかかります…")
        model = MODELS[self.model_label.get()]
        alpha_matting = self.alpha_matting.get()
        threading.Thread(target=self._worker, args=(out, model, alpha_matting), daemon=True).start()

    def _worker(self, out_dir: Path, model: str, alpha_matting: bool):
        try:
            session = new_session(model)
            pending = [x for x in self.items if x.status != "完了"]
            total = len(pending)
            for number, item in enumerate(pending, 1):
                if self.cancel_requested: break
                self.events.put(("processing", item, number, total))
                try:
                    with Image.open(item.path) as opened:
                        image = ImageOps.exif_transpose(opened).convert("RGBA")
                    result = remove(
                        image,
                        session=session,
                        alpha_matting=alpha_matting,
                        alpha_matting_foreground_threshold=240,
                        alpha_matting_background_threshold=10,
                        alpha_matting_erode_size=10,
                    )
                    destination = self._unique_output(out_dir, f"{item.path.stem}_transparent.png")
                    result.save(destination, "PNG", optimize=True)
                    self.events.put(("done", item, destination, number, total))
                except Exception as e:
                    self.events.put(("error", item, f"{type(e).__name__}: {e}", number, total))
            self.events.put(("finished", self.cancel_requested))
        except Exception as e:
            self.events.put(("fatal", f"{type(e).__name__}: {e}"))

    @staticmethod
    def _unique_output(folder: Path, filename: str) -> Path:
        path = folder / filename
        if not path.exists(): return path
        stem, suffix = path.stem, path.suffix
        n = 2
        while True:
            candidate = folder / f"{stem}_{n}{suffix}"
            if not candidate.exists(): return candidate
            n += 1

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait(); kind = event[0]
                if kind == "processing":
                    _, item, n, total = event; item.status = "処理中"; item.error = ""
                    self.status_text.set(f"{n}/{total}: {item.path.name} を処理中")
                elif kind == "done":
                    _, item, destination, n, total = event; item.status = "完了"; item.output = destination
                    self.progress["value"] = n / total * 100
                elif kind == "error":
                    _, item, error, n, total = event; item.status = "エラー"; item.error = error
                    self.progress["value"] = n / total * 100
                elif kind == "finished":
                    self._finish(cancelled=event[1])
                elif kind == "fatal":
                    messagebox.showerror(APP_TITLE, "処理を開始できませんでした。\n\n" + event[1]); self._finish(False, failed=True)
                self._refresh_tree()
        except queue.Empty: pass
        self.root.after(100, self._poll_events)

    def _finish(self, cancelled=False, failed=False):
        self.processing = False; self.start_button.configure(state="normal"); self.cancel_button.configure(state="disabled")
        if failed: self.status_text.set("処理を開始できませんでした")
        elif cancelled: self.status_text.set("処理を中止しました")
        else:
            done = sum(x.status == "完了" for x in self.items); errors = sum(x.status == "エラー" for x in self.items)
            self.status_text.set(f"完了: {done}件 / エラー: {errors}件")
            if done: messagebox.showinfo(APP_TITLE, f"処理が完了しました。\n完了: {done}件\nエラー: {errors}件")

    def request_cancel(self):
        self.cancel_requested = True; self.cancel_button.configure(state="disabled"); self.status_text.set("現在の1枚が終わったら中止します…")

    def open_output(self):
        path = Path(self.output_dir.get()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32": os.startfile(path)
            elif sys.platform == "darwin": subprocess.Popen(["open", str(path)])
            else: subprocess.Popen(["xdg-open", str(path)])
        except Exception as e: messagebox.showerror(APP_TITLE, str(e))

    def on_close(self):
        if self.processing and not messagebox.askyesno(APP_TITLE, "処理中です。終了しますか？"): return
        self.cancel_requested = True; self.root.destroy()

def main():
    if DND_AVAILABLE: root = TkinterDnD.Tk()
    else: root = tk.Tk()
    PersonCutoutApp(root)
    root.mainloop()

if __name__ == "__main__": main()
