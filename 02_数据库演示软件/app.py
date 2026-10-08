"""刷益乐题目难度数据库：可离线运行的课程演示桌面界面。

此程序只操作 DemoStore 管理的匿名 SQLite 工作副本，不连接微信云环境。
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from model import DemoStore


NAVY = "#0E2B44"
NAVY_2 = "#173A55"
TEAL = "#087B7C"
TEAL_LIGHT = "#E6F5F2"
BG = "#F4F8FA"
WHITE = "#FFFFFF"
TEXT = "#17324D"
MUTED = "#607588"
BORDER = "#DEE8ED"
WARN = "#B44F57"
FONT = "Microsoft YaHei UI"

# SQL 查询结果同时显示中文含义和数据库原字段名，方便演示时先讲业务含义，
# 再对应到实际表结构。未列出的字段继续显示原字段名。
SQL_COLUMN_LABELS = {
    "question_id": "题目编号",
    "question_no": "题号",
    "event_id": "作答记录编号",
    "display_name": "学习者昵称",
    "book_title": "习题册名称",
    "chapter_no": "章节编号",
    "chapter_title": "章节名称",
    "event_type": "作答类型",
    "self_marked_result": "自评结果",
    "answered_at": "作答时间",
    "distinct_user_count": "首次作答人数",
    "first_correct_count": "首次自评会人数",
    "difficulty_coefficient": "题目难度系数",
    "user_id": "学习者编号",
    "completed_question_count": "已完成题数",
    "attempt_count": "作答次数",
    "correct_attempt_count": "自评会次数",
    "personal_accuracy": "个人自评比例",
    "sample_question_count": "样本题数",
    "chapter_question_count": "章节题目数",
    "first_answer_count": "首次作答总人数",
    "chapter_difficulty_coefficient": "章节难度系数",
    "personal_status": "个人最新状态",
    "guidance": "练习建议",
}

SQL_LIST_TITLES = {
    1: "单表查询：章节题号",
    2: "多表连接：作答时间线",
    3: "分组排序：难题排名",
    4: "个人统计：完成与自评",
    5: "章节统计：加权难度",
    6: "条件筛选：推荐题目",
}


def sql_column_title(column: Any) -> str:
    """Return a readable SQL result heading while retaining the raw field name."""
    raw = str(column)
    friendly = SQL_COLUMN_LABELS.get(raw)
    return f"{friendly} / {raw}" if friendly else raw


def get(row: Any, *keys: str, default: Any = None) -> Any:
    """Read a display field while tolerating SQLite Row and dict values."""
    if row is None:
        return default
    for key in keys:
        try:
            value = row[key]
        except (KeyError, IndexError, TypeError):
            continue
        if value is not None:
            return value
    return default


def coefficient(value: Any) -> str:
    if value is None or value == "":
        return "暂无样本"
    try:
        return f"{float(value):.4f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def result_text(value: Any) -> str:
    if str(value) == "1":
        return "会"
    if str(value) == "2":
        return "不会"
    if str(value) == "0" or value is None:
        return "未作答"
    return str(value)


def timestamp(value: Any) -> str:
    return str(value or "—").replace("T", " ").replace("Z", "")


def card(parent: tk.Misc, *, padding: int = 18) -> tk.Frame:
    outer = tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
    inner = tk.Frame(outer, bg=WHITE, padx=padding, pady=padding)
    inner.pack(fill="both", expand=True)
    outer.content = inner  # type: ignore[attr-defined]
    return outer


def label(parent: tk.Misc, text: str, *, size: int = 10, weight: str = "normal",
          color: str = TEXT, bg: str = WHITE, **kwargs: Any) -> tk.Label:
    return tk.Label(parent, text=text, font=(FONT, size, weight), fg=color,
                    bg=bg, anchor="w", **kwargs)


def button(parent: tk.Misc, text: str, command: Any, *, primary: bool = False,
           small: bool = False, danger: bool = False) -> tk.Button:
    background = WARN if danger else (TEAL if primary else TEAL_LIGHT)
    foreground = WHITE if (primary or danger) else TEAL
    hover = "#096769" if primary else ("#9D414A" if danger else "#D8EFEB")
    item = tk.Button(
        parent, text=text, command=command, bg=background, fg=foreground,
        activebackground=hover, activeforeground=foreground, relief="flat",
        cursor="hand2", borderwidth=0, padx=13 if small else 18,
        pady=6 if small else 9, font=(FONT, 9 if small else 10, "bold"),
    )
    item.bind("<Enter>", lambda _event: item.configure(bg=hover))
    item.bind("<Leave>", lambda _event: item.configure(bg=background))
    return item


class DesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.store = DemoStore()
        self.root.title("刷益乐 · 题目难度数据库演示")
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(1240, max(1100, screen_width - 90))
        height = min(760, max(700, screen_height - 100))
        self.root.geometry(f"{width}x{height}+{max(0, (screen_width-width)//2)}+25")
        self.root.minsize(1100, 700)
        self.root.configure(bg=BG)
        self._style()

        self.pages = [
            ("overview", "总览"),
            ("difficulty", "题目难度分析"),
            ("progress", "学习进度"),
            ("sql", "SQL 数据查询"),
            ("evidence", "并发与备份恢复"),
            ("about", "数据说明"),
        ]
        self.active_page = "overview"
        self.nav_buttons: dict[str, tk.Button] = {}
        self.book_ids: dict[str, str | None] = {}
        self.chapter_ids: dict[str, int | None] = {}
        self.user_ids: dict[str, str] = {}
        self.query_ids: dict[str, int] = {}
        self.question_rows: dict[str, dict[str, Any]] = {}
        self.current_question_id: str | None = None

        self._shell()
        self.show_page("overview")

    def _style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("App.Treeview", background=WHITE, fieldbackground=WHITE,
                        foreground=TEXT, rowheight=36, borderwidth=0,
                        font=(FONT, 10))
        style.configure("App.Treeview.Heading", background="#EAF1F4",
                        foreground=TEXT, relief="flat", font=(FONT, 9, "bold"),
                        padding=(7, 9))
        style.map("App.Treeview", background=[("selected", TEAL_LIGHT)],
                  foreground=[("selected", NAVY)])
        style.map("App.Treeview.Heading", background=[("active", "#E1EDF0")])
        style.configure("App.TCombobox", fieldbackground=WHITE, background=WHITE,
                        foreground=TEXT, bordercolor=BORDER, arrowsize=15,
                        padding=(8, 6), font=(FONT, 9))
        style.map("App.TCombobox", fieldbackground=[("readonly", WHITE)],
                  selectbackground=[("readonly", WHITE)],
                  selectforeground=[("readonly", TEXT)])
        style.configure("App.Vertical.TScrollbar", background="#CBD9DF",
                        troughcolor=WHITE, bordercolor=WHITE, arrowcolor=TEXT)

    def _shell(self) -> None:
        self.sidebar = tk.Frame(self.root, bg=NAVY, width=222)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=NAVY, padx=22, pady=26)
        brand.pack(fill="x")
        label(brand, "刷益乐", size=21, weight="bold", color=WHITE,
              bg=NAVY).pack(fill="x")
        label(brand, "数据库课程演示", size=10, color="#A9C5D3",
              bg=NAVY).pack(fill="x", pady=(2, 0))
        tk.Frame(self.sidebar, bg="#355369", height=1).pack(fill="x", padx=20, pady=(0, 20))

        nav = tk.Frame(self.sidebar, bg=NAVY)
        nav.pack(fill="x", padx=12)
        for key, title in self.pages:
            item = tk.Button(
                nav, text="  " + title, command=lambda page=key: self.show_page(page),
                anchor="w", bg=NAVY, fg="#C5D8E3", activebackground=NAVY_2,
                activeforeground=WHITE, relief="flat", borderwidth=0,
                padx=14, pady=12, cursor="hand2", font=(FONT, 10),
            )
            item.pack(fill="x", pady=2)
            self.nav_buttons[key] = item

        tk.Frame(self.sidebar, bg=NAVY).pack(fill="both", expand=True)
        label(self.sidebar, "离线匿名样例", size=9, color="#A9C5D3",
              bg=NAVY).pack(fill="x", padx=26)
        label(self.sidebar, "SQLite · 不连接微信云端", size=8,
              color="#819EAE", bg=NAVY).pack(fill="x", padx=26, pady=(0, 24))

        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        self.header = tk.Frame(self.main, bg=BG, padx=30, pady=22)
        self.header.pack(fill="x")
        self.header_title = label(self.header, "", size=21, weight="bold", bg=BG)
        self.header_title.pack(fill="x")
        self.header_desc = label(self.header, "", size=9, color=MUTED, bg=BG)
        self.header_desc.pack(fill="x", pady=(4, 0))
        self.body = tk.Frame(self.main, bg=BG, padx=30, pady=0)
        self.body.pack(fill="both", expand=True)

        footer = tk.Frame(self.main, bg=BG, padx=30, pady=10)
        footer.pack(fill="x")
        label(footer, "离线样例数据 · 只用于课程演示 · 作答结果是学习者的“会 / 不会”自评。",
              size=8, color=MUTED, bg=BG).pack(side="left")

    def _clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def show_page(self, page: str) -> None:
        self.active_page = page
        for key, item in self.nav_buttons.items():
            active = key == page
            item.configure(bg=NAVY_2 if active else NAVY,
                           fg=WHITE if active else "#C5D8E3",
                           font=(FONT, 10, "bold" if active else "normal"))
        self._clear()
        titles = {
            "overview": ("学习者逐题作答总览", "按学习者和题目查看首次自评、当前状态与作答次数"),
            "difficulty": ("题目难度分析", "每人每题只统计第一次作答，重复练习仍保留在记录中"),
            "progress": ("学习进度", "选择学习者，查看最新状态，以及根据群体数据生成的练习建议"),
            "sql": ("SQL 数据查询", "查看数据库查询语句、执行结果，以及每类查询解决的问题"),
            "evidence": ("并发与备份恢复", "演示两条作答并发提交和单条记录的备份恢复"),
            "about": ("数据说明", "了解数据来源、统计规则、表结构和与微信小程序的关系"),
        }
        title, desc = titles[page]
        self.header_title.configure(text=title)
        self.header_desc.configure(text=desc)
        try:
            getattr(self, f"_page_{page}")()
        except Exception as exc:
            self._page_error(exc)

    def _page_error(self, exc: Exception) -> None:
        panel = card(self.body)
        panel.pack(fill="x")
        label(panel.content, "页面暂时无法加载", size=15, weight="bold",
              color=WARN).pack(fill="x")
        label(panel.content, str(exc), size=10, color=MUTED,
              wraplength=750, justify="left").pack(fill="x", pady=12)
        button(panel.content, "重试", lambda: self.show_page(self.active_page),
               primary=True).pack(anchor="w")

    def _metric(self, parent: tk.Misc, title: str, value: str,
                caption: str = "") -> tk.Frame:
        panel = card(parent, padding=15)
        label(panel.content, title, size=9, color=MUTED).pack(fill="x")
        label(panel.content, value, size=23, weight="bold").pack(fill="x", pady=(4, 2))
        label(panel.content, caption, size=8, color=MUTED).pack(fill="x")
        return panel

    def _page_overview(self) -> None:
        overview = self.store.overview()
        counts = get(overview, "counts", default={}) or {}
        users = get(overview, "user_count", default=get(counts, "users", default=0))
        questions = get(overview, "question_count", default=get(counts, "questions", default=0))
        events = get(overview, "answer_event_count", default=get(counts, "answer_events", default=0))
        firsts = get(overview, "first_answer_count", default=0)

        metrics = tk.Frame(self.body, bg=BG)
        metrics.pack(fill="x")
        for col in range(4):
            metrics.grid_columnconfigure(col, weight=1, uniform="metric")
        for idx, (title, value) in enumerate([
            ("学习者", users),
            ("题目", questions),
            ("作答记录", events),
            ("首次作答", firsts),
        ]):
            tile = card(metrics, padding=9)
            label(tile.content, title, size=9, color=MUTED).pack(side="left")
            label(tile.content, str(value), size=19, weight="bold").pack(side="right")
            tile.grid(
                row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 6,
                                                        0 if idx == 3 else 6))

        controls = card(self.body, padding=9)
        controls.pack(fill="x", pady=(8, 8))
        row = tk.Frame(controls.content, bg=WHITE)
        row.pack(fill="x")
        label(row, "逐题作答明细", size=12, weight="bold").pack(side="left")
        button(row, "添加学习者", self._add_user, primary=True,
               small=True).pack(side="right")
        self.simulation_count_var = tk.StringVar(value="10")
        button(row, "随机生成模拟作答", self._generate_simulated_answers,
               primary=True, small=True).pack(side="right", padx=(0, 8))
        ttk.Combobox(row, textvariable=self.simulation_count_var,
                     values=["10", "30", "100"], state="readonly",
                     style="App.TCombobox", width=5).pack(side="right", padx=(0, 8))
        label(row, "条数", size=8, color=MUTED).pack(side="right", padx=(0, 6))

        filters = tk.Frame(controls.content, bg=WHITE)
        filters.pack(fill="x", pady=(7, 0))
        self.home_book_ids = {"全部习题册": None}
        for book in self.store.books():
            book_id = str(get(book, "book_id", default=""))
            title = str(get(book, "title", default=book_id))
            self.home_book_ids[f"{title} · {book_id}"] = book_id
        self.home_book_var = tk.StringVar(value="全部习题册")
        self.home_chapter_var = tk.StringVar(value="全部章节")
        self.home_chapter_ids: dict[str, int | None] = {"全部章节": None}
        self.home_user_var = tk.StringVar()
        self.home_user_ids: dict[str, str] = {}
        for user in self.store.users():
            user_id = str(get(user, "user_id", default=""))
            name = str(get(user, "display_name", default=user_id))
            self.home_user_ids[f"{name} · {user_id}"] = user_id
        self.home_user_var.set(next(iter(self.home_user_ids), ""))

        book_cell = tk.Frame(filters, bg=WHITE)
        book_cell.pack(side="left", padx=(0, 10))
        label(book_cell, "习题册", size=8, color=MUTED).pack(fill="x", pady=(0, 4))
        book_combo = ttk.Combobox(book_cell, textvariable=self.home_book_var,
                                  values=list(self.home_book_ids), state="readonly",
                                  style="App.TCombobox", width=20)
        book_combo.pack(fill="x")
        book_combo.bind("<<ComboboxSelected>>", self._home_book_changed)

        chapter_cell = tk.Frame(filters, bg=WHITE)
        chapter_cell.pack(side="left", padx=(0, 14))
        label(chapter_cell, "章节", size=8, color=MUTED).pack(fill="x", pady=(0, 4))
        self.home_chapter_combo = ttk.Combobox(chapter_cell,
                                               textvariable=self.home_chapter_var,
                                               values=["全部章节"], state="disabled",
                                               style="App.TCombobox", width=21)
        self.home_chapter_combo.pack(fill="x")
        self.home_chapter_combo.bind("<<ComboboxSelected>>",
                                     lambda _event: self._refresh_overview_matrix())

        delete_cell = tk.Frame(filters, bg=WHITE)
        delete_cell.pack(side="right")
        label(delete_cell, "删除指定学习者", size=8, color=MUTED).pack(fill="x", pady=(0, 4))
        delete_row = tk.Frame(delete_cell, bg=WHITE)
        delete_row.pack(fill="x")
        user_combo = ttk.Combobox(delete_row, textvariable=self.home_user_var,
                                  values=list(self.home_user_ids), state="readonly",
                                  style="App.TCombobox", width=21)
        user_combo.pack(side="left", padx=(0, 8))
        button(delete_row, "删除", self._delete_user, danger=True,
               small=True).pack(side="left")

        self.simulation_feedback = label(controls.content, "", size=8, color=TEAL)

        table_panel = card(self.body, padding=12)
        table_panel.pack(fill="both", expand=True, pady=(0, 10))
        title_row = tk.Frame(table_panel.content, bg=WHITE)
        title_row.pack(fill="x", pady=(0, 8))
        self.home_count_label = label(title_row, "", size=9, color=MUTED)
        self.home_count_label.pack(side="left")
        label(title_row, "向右滚动可看最近作答时间", size=8,
              color=MUTED).pack(side="right")
        self.home_tree = self._tree(table_panel.content, [
            ("user", "学习者", 150), ("book", "习题册", 150),
            ("chapter", "章节", 160), ("question", "题目编号", 120),
            ("first", "首次自评", 84), ("latest", "当前状态", 84),
            ("attempts", "作答次数", 84), ("time", "最近作答时间", 170),
        ], height=8)
        for column in self.home_tree["columns"]:
            self.home_tree.column(column, stretch=False)
        self.home_tree.tag_configure("know", background="#F1FAF7")
        self.home_tree.tag_configure("review", background="#FFF5F2")
        self._refresh_overview_matrix()

    def _home_book_changed(self, _event: Any = None) -> None:
        book_id = self.home_book_ids.get(self.home_book_var.get())
        self.home_chapter_ids = {"全部章节": None}
        if book_id is None:
            self.home_chapter_combo.configure(values=["全部章节"], state="disabled")
        else:
            for chapter in self.store.chapters(book_id=book_id):
                chapter_no = int(get(chapter, "chapter_no", default=0))
                title = str(get(chapter, "title", default=""))
                self.home_chapter_ids[f"第 {chapter_no} 章 · {title}"] = chapter_no
            self.home_chapter_combo.configure(values=list(self.home_chapter_ids),
                                              state="readonly")
        self.home_chapter_var.set("全部章节")
        self._refresh_overview_matrix()

    def _refresh_overview_matrix(self) -> None:
        book_id = self.home_book_ids.get(self.home_book_var.get())
        chapter_no = self.home_chapter_ids.get(self.home_chapter_var.get())
        rows = self.store.answer_matrix(book_id=book_id, chapter_no=chapter_no)
        self.home_tree.delete(*self.home_tree.get_children())
        for index, row in enumerate(rows):
            status = get(row, "status", default=0)
            tag = "know" if str(status) == "1" else "review" if str(status) == "2" else ""
            self.home_tree.insert("", "end", iid=str(index), tags=(tag,) if tag else (),
                                  values=(
                                      get(row, "display_name", default=""),
                                      get(row, "book_title", default=""),
                                      f"第 {get(row, 'chapter_no', default='')} 章 · "
                                      f"{get(row, 'chapter_title', default='')}",
                                      get(row, "question_id", default=""),
                                      result_text(get(row, "first_result")),
                                      result_text(status),
                                      get(row, "attempt_count", default=0),
                                      timestamp(get(row, "last_answered_at")),
                                  ))
        self.home_count_label.configure(
            text=(f"共 {len(rows)} 条学习者 × 题目记录" if self.home_user_ids
                  else "暂无学习者；点击上方“添加学习者”开始"))

    def _generate_simulated_answers(self) -> None:
        try:
            requested = int(self.simulation_count_var.get())
            selected_book = self.home_book_var.get()
            selected_chapter = self.home_chapter_var.get()
            result = self.store.generate_simulated_events(requested)
            inserted = get(result, "inserted_count", "inserted", "count", default=0)
            # A batch can create sample learners when the list is empty, so rebuild
            # the selector and metric cards as well as the matrix.
            self.show_page("overview")
            if selected_book in self.home_book_ids:
                self.home_book_var.set(selected_book)
                self._home_book_changed()
                if selected_chapter in self.home_chapter_ids:
                    self.home_chapter_var.set(selected_chapter)
                    self._refresh_overview_matrix()
            self.simulation_count_var.set(str(requested))
            practices = get(result, "practice_count", default=0)
            reviews = get(result, "review_count", default=0)
            created_users = get(result, "synthetic_user_count", default=0)
            self.simulation_feedback.configure(
                text=(f"本次已写入 {inserted} 条模拟作答（首次练习 {practices}、复习 {reviews}）"
                      + (f"，新增 {created_users} 名模拟学习者" if created_users else "")
                      + "。上方总数包含全部习题册和章节。"))
            self.simulation_feedback.pack(fill="x", pady=(5, 0))
        except Exception as exc:
            messagebox.showerror("生成模拟作答失败", str(exc), parent=self.root)

    def _delete_user(self, selected_user_id: str | None = None) -> None:
        user_id = selected_user_id
        if user_id is None and hasattr(self, "home_user_ids"):
            user_id = self.home_user_ids.get(self.home_user_var.get())
        if not user_id:
            messagebox.showwarning("请选择学习者", "先在下拉框中选择学习者。", parent=self.root)
            return
        user = next((item for item in self.store.users()
                     if str(get(item, "user_id", default="")) == user_id), None)
        if user is None:
            self.show_page(self.active_page)
            return
        name = str(get(user, "display_name", default=user_id))
        attempts = int(get(user, "attempt_count", default=0) or 0)
        completed = int(get(user, "completed_question_count", default=0) or 0)
        confirmed = messagebox.askyesno(
            "确认删除学习者",
            f"确定删除“{name}”（{user_id}）吗？\n\n"
            f"将同时删除其 {attempts} 条作答记录和 {completed} 条逐题进度。"
            "此操作会重新计算相关题目的首次作答统计。",
            icon="warning", parent=self.root,
        )
        if not confirmed:
            return
        try:
            self.store.delete_user(user_id)
            self.show_page(self.active_page)
        except Exception as exc:
            messagebox.showerror("删除学习者失败", str(exc), parent=self.root)

    def _tree(self, parent: tk.Misc, columns: list[tuple[str, str, int]],
              *, height: int = 12) -> ttk.Treeview:
        holder = tk.Frame(parent, bg=WHITE)
        holder.pack(fill="both", expand=True)
        names = [name for name, _title, _width in columns]
        tree = ttk.Treeview(holder, columns=names, show="headings", height=height,
                            style="App.Treeview", selectmode="browse")
        for name, title, width in columns:
            tree.heading(name, text=title)
            tree.column(name, width=width, minwidth=max(80, width // 2),
                        anchor="w", stretch=True)
        scroll_y = ttk.Scrollbar(holder, orient="vertical", command=tree.yview,
                                 style="App.Vertical.TScrollbar")
        scroll_x = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        holder.grid_rowconfigure(0, weight=1)
        holder.grid_columnconfigure(0, weight=1)
        return tree

    def _page_difficulty(self) -> None:
        filter_panel = card(self.body, padding=16)
        filter_panel.pack(fill="x")
        filters = filter_panel.content
        self.book_ids = {"全部习题册": None}
        for book in self.store.books():
            book_id = str(get(book, "book_id", default=""))
            title = str(get(book, "title", "book_title", default=book_id))
            self.book_ids[f"{title}  ·  {book_id}"] = book_id
        self.book_var = tk.StringVar(value="全部习题册")
        self.chapter_var = tk.StringVar(value="全部章节")
        self.search_var = tk.StringVar()
        self.min_sample_var = tk.StringVar(value="不限首次作答人数")

        for idx, (heading, widget) in enumerate([
            ("习题册", "book"), ("章节", "chapter"),
            ("题号或关键词", "search"), ("至少首次作答人数", "sample"),
        ]):
            cell = tk.Frame(filters, bg=WHITE)
            cell.pack(side="left", fill="x", expand=(idx in (0, 1)),
                      padx=(0, 12))
            label(cell, heading, size=8, color=MUTED).pack(fill="x", pady=(0, 5))
            if widget == "book":
                self.book_combo = ttk.Combobox(cell, textvariable=self.book_var,
                                               values=list(self.book_ids), state="readonly",
                                               style="App.TCombobox", width=26)
                self.book_combo.pack(fill="x")
                self.book_combo.bind("<<ComboboxSelected>>", self._book_changed)
            elif widget == "chapter":
                self.chapter_combo = ttk.Combobox(cell, textvariable=self.chapter_var,
                                                  values=["全部章节"], state="readonly",
                                                  style="App.TCombobox", width=24)
                self.chapter_combo.pack(fill="x")
            elif widget == "search":
                entry = tk.Entry(cell, textvariable=self.search_var,
                                 font=(FONT, 10), bg=WHITE, fg=TEXT,
                                 relief="solid", bd=1, highlightthickness=0,
                                 width=16)
                entry.pack(fill="x", ipady=6)
                entry.bind("<Return>", lambda _event: self._refresh_questions())
            else:
                combo = ttk.Combobox(cell, textvariable=self.min_sample_var,
                                     values=["不限首次作答人数", "至少 1 人", "至少 2 人", "至少 5 人"],
                                     state="readonly", style="App.TCombobox", width=13)
                combo.pack(fill="x")
        button(filters, "应用筛选", self._refresh_questions, primary=True,
               small=True).pack(side="right", pady=(15, 0))

        self.chapter_ids = {"全部章节": None}
        work = tk.Frame(self.body, bg=BG)
        work.pack(fill="both", expand=True, pady=(15, 3))
        work.grid_columnconfigure(0, weight=3)
        work.grid_columnconfigure(1, weight=2)
        work.grid_rowconfigure(0, weight=1)

        table_panel = card(work, padding=14)
        table_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        title_row = tk.Frame(table_panel.content, bg=WHITE)
        title_row.pack(fill="x", pady=(0, 12))
        label(title_row, "题目难度列表", size=12, weight="bold").pack(side="left")
        self.question_count_label = label(title_row, "", size=8, color=MUTED)
        self.question_count_label.pack(side="right")
        self.question_tree = self._tree(table_panel.content, [
            ("question", "题号", 135), ("chapter", "章节", 170),
            ("sample", "首次作答人数", 80), ("correct", "自评会人数", 55),
            ("ratio", "难度系数", 88),
        ])
        self.question_tree.bind("<<TreeviewSelect>>", self._question_selected)

        detail_panel = card(work, padding=18)
        detail_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.detail_canvas = tk.Canvas(detail_panel.content, bg=WHITE,
                                       borderwidth=0, highlightthickness=0)
        detail_scroll = ttk.Scrollbar(detail_panel.content, orient="vertical",
                                      command=self.detail_canvas.yview,
                                      style="App.Vertical.TScrollbar")
        detail_scroll.pack(side="right", fill="y")
        self.detail_canvas.pack(side="left", fill="both", expand=True)
        self.detail_canvas.configure(yscrollcommand=detail_scroll.set)
        self.detail_body = tk.Frame(self.detail_canvas, bg=WHITE)
        detail_window = self.detail_canvas.create_window((0, 0),
                                                          window=self.detail_body,
                                                          anchor="nw")
        self.detail_body.bind(
            "<Configure>",
            lambda _event: self.detail_canvas.configure(
                scrollregion=self.detail_canvas.bbox("all")),
        )
        self.detail_canvas.bind(
            "<Configure>",
            lambda event: self.detail_canvas.itemconfigure(detail_window,
                                                            width=event.width),
        )
        self.detail_canvas.bind("<MouseWheel>", self._scroll_detail)
        self._book_changed()

    def _scroll_detail(self, event: tk.Event) -> str:
        if event.delta:
            self.detail_canvas.yview_scroll(-3 if event.delta > 0 else 3, "units")
        return "break"

    def _bind_detail_scroll(self, widget: tk.Misc) -> None:
        # Mouse wheel events land on the label or frame under the pointer.
        if not isinstance(widget, ttk.Combobox):
            widget.bind("<MouseWheel>", self._scroll_detail, add="+")
        for child in widget.winfo_children():
            self._bind_detail_scroll(child)

    def _book_changed(self, _event: Any = None) -> None:
        book_id = self.book_ids.get(self.book_var.get())
        self.chapter_ids = {"全部章节": None}
        if book_id is None:
            self.chapter_combo.configure(values=["全部章节"], state="disabled")
        else:
            for chapter in self.store.chapters(book_id=book_id):
                chapter_no = int(get(chapter, "chapter_no", default=0))
                title = get(chapter, "title", "chapter_title", default=f"第 {chapter_no} 章")
                self.chapter_ids[f"第 {chapter_no} 章 · {title}"] = chapter_no
            self.chapter_combo.configure(values=list(self.chapter_ids), state="readonly")
        self.chapter_var.set("全部章节")
        self._refresh_questions()

    def _refresh_questions(self) -> None:
        book_id = self.book_ids.get(self.book_var.get())
        chapter_no = self.chapter_ids.get(self.chapter_var.get())
        sample_label = self.min_sample_var.get()
        min_sample = 0 if sample_label.startswith("不限") else int(sample_label.split()[1])
        rows = self.store.questions(book_id=book_id, chapter_no=chapter_no,
                                    search=self.search_var.get().strip(),
                                    min_sample=min_sample)
        self.question_rows = {}
        self.question_tree.delete(*self.question_tree.get_children())
        for row in rows:
            question_id = str(get(row, "question_id", default=""))
            self.question_rows[question_id] = dict(row)
            sample = get(row, "first_answer_count", "distinct_user_count", default=0)
            correct = get(row, "first_correct_count", default=0)
            self.question_tree.insert("", "end", iid=question_id,
                                      values=(question_id,
                                              get(row, "chapter_title", default=""),
                                              sample, correct,
                                              coefficient(get(row, "difficulty_coefficient"))))
        self.question_count_label.configure(text=f"共 {len(rows)} 道题")
        if rows:
            first = str(get(rows[0], "question_id"))
            self.question_tree.selection_set(first)
            self.question_tree.focus(first)
            self._show_question(first)
        else:
            self.current_question_id = None
            self._detail_empty("暂无符合条件的题目")

    def _question_selected(self, _event: Any = None) -> None:
        chosen = self.question_tree.selection()
        if chosen:
            self._show_question(chosen[0])

    def _detail_empty(self, text: str) -> None:
        for child in self.detail_body.winfo_children():
            child.destroy()
        label(self.detail_body, text, size=12, color=MUTED).pack(fill="x", pady=20)
        self.detail_canvas.yview_moveto(0)
        self._bind_detail_scroll(self.detail_body)

    def _show_question(self, question_id: str) -> None:
        self.current_question_id = question_id
        detail = self.store.question_detail(question_id)
        for child in self.detail_body.winfo_children():
            child.destroy()
        self.detail_canvas.yview_moveto(0)
        label(self.detail_body, "题目详情", size=12, weight="bold").pack(fill="x")
        label(self.detail_body, question_id, size=17, weight="bold",
              color=TEAL).pack(fill="x", pady=(8, 0))
        label(self.detail_body,
              f"{get(detail, 'book_title', default='')}  ·  {get(detail, 'chapter_title', default='')}",
              size=9, color=MUTED, wraplength=320, justify="left").pack(fill="x", pady=(4, 14))

        sample = int(get(detail, "first_answer_count", "distinct_user_count", default=0) or 0)
        correct = int(get(detail, "first_correct_count", default=0) or 0)
        ratio = coefficient(get(detail, "difficulty_coefficient"))
        strip = tk.Frame(self.detail_body, bg=TEAL_LIGHT, padx=12, pady=13)
        strip.pack(fill="x")
        label(strip, f"{correct} / {sample}", size=17, weight="bold",
              color=TEAL, bg=TEAL_LIGHT).pack(side="left")
        label(strip, f"难度系数  {ratio}", size=10, weight="bold",
              color=TEAL, bg=TEAL_LIGHT).pack(side="right")
        label(self.detail_body,
              "统计口径：每位学习者每道题只计第一次作答；重复练习不会改变题目难度。",
              size=8, color=MUTED, wraplength=330, justify="left").pack(fill="x", pady=(9, 15))

        label(self.detail_body, "记录本题作答", size=10,
              weight="bold").pack(fill="x")
        users = self.store.users()
        self.user_ids = {}
        for user in users:
            user_id = str(get(user, "user_id", default=""))
            caption = f"{get(user, 'display_name', default=user_id)}  ·  {user_id}"
            self.user_ids[caption] = user_id
        self.answer_user_var = tk.StringVar(value=next(iter(self.user_ids), ""))
        label(self.detail_body, "选择学习者（匿名）", size=8, color=MUTED).pack(
            fill="x", pady=(7, 0))
        user_combo = ttk.Combobox(self.detail_body, textvariable=self.answer_user_var,
                                  values=list(self.user_ids), state="readonly",
                                  style="App.TCombobox")
        user_combo.pack(fill="x", pady=(4, 8))
        action_row = tk.Frame(self.detail_body, bg=WHITE)
        action_row.pack(fill="x")
        button(action_row, "会做", lambda: self._record_answer(1),
               primary=True, small=True).pack(side="left", fill="x", expand=True, padx=(0, 4))
        button(action_row, "不会做", lambda: self._record_answer(2),
               small=True).pack(side="left", fill="x", expand=True, padx=(4, 0))

        label(self.detail_body, "首次作答记录", size=10,
              weight="bold").pack(fill="x", pady=(19, 5))
        first_answers = get(detail, "first_answers", default=[]) or []
        preview = tk.Frame(self.detail_body, bg=WHITE)
        preview.pack(fill="both", expand=True)
        if not first_answers:
            label(preview, "暂无首次作答记录。可在上方选择学习者进行演示。", size=9,
                  color=MUTED, wraplength=320).pack(fill="x", pady=8)
        else:
            for event in first_answers[:5]:
                line = tk.Frame(preview, bg=WHITE)
                line.pack(fill="x", pady=2)
                label(line, str(get(event, "display_name", "user_id", default="学习者")),
                      size=9).pack(side="left")
                label(line, result_text(get(event, "result")), size=9,
                      weight="bold", color=TEAL if str(get(event, "result")) == "1" else WARN
                      ).pack(side="right")
            if len(first_answers) > 5:
                label(preview, f"还有 {len(first_answers) - 5} 条首次作答记录",
                      size=8, color=MUTED).pack(fill="x", pady=(4, 0))
        all_events = get(detail, "events", default=[]) or []
        label(self.detail_body, f"全部作答记录：{len(all_events)} 次（含复习）",
              size=8, color=MUTED).pack(fill="x", pady=(10, 0))
        button(self.detail_body, "查看完整作答时间线",
               lambda: self._show_timeline(question_id, all_events),
               small=True).pack(anchor="w", pady=(8, 0))
        self._bind_detail_scroll(self.detail_body)

    def _show_timeline(self, question_id: str, events: list[dict]) -> None:
        window = tk.Toplevel(self.root)
        window.title(f"作答时间线 · {question_id}")
        window.geometry("790x470")
        window.minsize(670, 390)
        window.configure(bg=BG)
        area = tk.Frame(window, bg=BG, padx=20, pady=20)
        area.pack(fill="both", expand=True)
        label(area, f"{question_id} · 全部作答记录", size=15,
              weight="bold", bg=BG).pack(fill="x")
        label(area, "每位学习者的第一次作答会参与难度统计；后续重做记录也会保留。",
              size=9, color=MUTED, bg=BG).pack(fill="x", pady=(4, 15))
        panel = card(area, padding=12)
        panel.pack(fill="both", expand=True)
        tree = self._tree(panel.content, [
            ("user", "学习者", 125), ("result", "自评结果", 70),
            ("type", "作答类型", 95), ("first", "参与难度统计", 90),
            ("time", "作答时间", 190),
        ])
        for idx, event in enumerate(events):
            event_type = get(event, "event_type", default="")
            tree.insert("", "end", iid=str(idx), values=(
                get(event, "display_name", "user_id", default=""),
                result_text(get(event, "result")),
                "复习" if event_type == "review" else "练习",
                "是" if get(event, "is_first_answer", default=0) else "否",
                timestamp(get(event, "answered_at")),
            ))

    def _record_answer(self, result: int) -> None:
        question_id = self.current_question_id
        user_id = self.user_ids.get(self.answer_user_var.get())
        if not question_id or not user_id:
            messagebox.showwarning("请选择学习者", "先选择一个匿名学习者。", parent=self.root)
            return
        try:
            before = self.store.question_detail(question_id)
            has_answered = any(get(event, "user_id") == user_id
                               for event in get(before, "events", default=[]))
            self.store.record_answer(user_id, question_id, result,
                                     event_type="review" if has_answered else "practice")
            self._refresh_questions()
            if question_id in self.question_rows:
                self.question_tree.selection_set(question_id)
                self.question_tree.see(question_id)
                self._show_question(question_id)
            note = ("已记录复习作答。个人最新状态已更新；题目难度仍按首次作答统计。"
                    if has_answered else "已记录首次作答。题目难度已按全部学习者的首次作答重新计算。")
            messagebox.showinfo("记录成功", note, parent=self.root)
        except Exception as exc:
            messagebox.showerror("记录失败", str(exc), parent=self.root)

    def _page_progress(self) -> None:
        bar = card(self.body, padding=15)
        bar.pack(fill="x")
        label(bar.content, "选择学习者", size=9, color=MUTED).pack(side="left", padx=(0, 12))
        self.progress_user_var = tk.StringVar()
        self.progress_user_combo = ttk.Combobox(bar.content, textvariable=self.progress_user_var,
                                                state="readonly", style="App.TCombobox",
                                                width=32)
        self.progress_user_combo.pack(side="left")
        self.progress_user_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_progress())
        button(bar.content, "删除学习者",
               lambda: self._delete_user(self.user_ids.get(self.progress_user_var.get()) or ""),
               small=True, danger=True).pack(side="right")
        button(bar.content, "添加学习者", self._add_user,
               small=True).pack(side="right", padx=(0, 8))

        summary = tk.Frame(self.body, bg=BG)
        summary.pack(fill="x", pady=15)
        for col in range(3):
            summary.grid_columnconfigure(col, weight=1, uniform="progress")
        self.progress_metrics: list[tk.Frame] = []
        for col, caption in enumerate(("已作答题目", "最新自评为会", "建议复习")):
            item = self._metric(summary, caption, "—")
            item.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 6,
                                                             0 if col == 2 else 6))
            self.progress_metrics.append(item)

        panel = card(self.body, padding=14)
        panel.pack(fill="both", expand=True, pady=(0, 3))
        label(panel.content, "逐题学习进度与练习建议", size=12,
              weight="bold").pack(fill="x", pady=(0, 12))
        self.progress_tree = self._tree(panel.content, [
            ("question", "题号", 150), ("chapter", "章节", 225),
            ("status", "最近自评", 95), ("first", "首次自评", 90),
            ("ratio", "题目难度系数", 100), ("hint", "系统建议", 210),
        ])
        self._load_users()

    def _load_users(self, select_user_id: str | None = None) -> None:
        self.user_ids = {}
        for user in self.store.users():
            user_id = str(get(user, "user_id", default=""))
            caption = f"{get(user, 'display_name', default=user_id)}  ·  {user_id}"
            self.user_ids[caption] = user_id
        self.progress_user_combo.configure(values=list(self.user_ids))
        selected = next((label for label, user_id in self.user_ids.items()
                         if user_id == select_user_id), None)
        self.progress_user_var.set(selected or next(iter(self.user_ids), ""))
        self._refresh_progress()

    def _add_user(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("添加学习者与首次作答")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.geometry(f"530x590+{self.root.winfo_rootx()+190}+{self.root.winfo_rooty()+35}")
        dialog.grab_set()

        panel = card(dialog, padding=22)
        panel.pack(fill="both", expand=True, padx=15, pady=15)
        form = panel.content
        label(form, "添加匿名学习者", size=16, weight="bold").pack(fill="x")
        label(form, "可同时选择习题册、章节和题目，登记该学习者的第一次自评。",
              size=9, color=MUTED).pack(fill="x", pady=(4, 16))
        label(form, "学习者昵称", size=9, weight="bold").pack(fill="x", pady=(0, 5))
        name_var = tk.StringVar()
        name_entry = tk.Entry(form, textvariable=name_var, font=(FONT, 11),
                              relief="solid", bd=1, bg=WHITE, fg=TEXT)
        name_entry.pack(fill="x", ipady=7)

        book_map: dict[str, str] = {}
        for book in self.store.books():
            book_id = str(get(book, "book_id", default=""))
            title = str(get(book, "title", default=book_id))
            book_map[f"{title} · {book_id}"] = book_id
        chapter_map: dict[str, int] = {}
        question_map: dict[str, str] = {}
        book_var = tk.StringVar(value=next(iter(book_map), ""))
        chapter_var = tk.StringVar()
        question_var = tk.StringVar()
        result_var = tk.StringVar(value="未作答（只添加学习者）")

        label(form, "习题册", size=9, weight="bold").pack(fill="x", pady=(13, 5))
        book_combo = ttk.Combobox(form, textvariable=book_var,
                                  values=list(book_map), state="readonly" if book_map else "disabled",
                                  style="App.TCombobox")
        book_combo.pack(fill="x")
        label(form, "章节", size=9, weight="bold").pack(fill="x", pady=(13, 5))
        chapter_combo = ttk.Combobox(form, textvariable=chapter_var, values=[],
                                     state="readonly", style="App.TCombobox")
        chapter_combo.pack(fill="x")
        label(form, "题目", size=9, weight="bold").pack(fill="x", pady=(13, 5))
        question_combo = ttk.Combobox(form, textvariable=question_var, values=[],
                                      state="readonly", style="App.TCombobox")
        question_combo.pack(fill="x")
        label(form, "首次自评", size=9, weight="bold").pack(fill="x", pady=(13, 5))
        result_combo = ttk.Combobox(form, textvariable=result_var,
                                    values=["未作答（只添加学习者）", "会", "不会"],
                                    state="readonly", style="App.TCombobox")
        result_combo.pack(fill="x")

        def refresh_questions(_event: Any = None) -> None:
            question_map.clear()
            book_id = book_map.get(book_var.get())
            chapter_no = chapter_map.get(chapter_var.get())
            if book_id and chapter_no is not None:
                for question in self.store.questions(book_id=book_id,
                                                     chapter_no=chapter_no):
                    question_id = str(get(question, "question_id", default=""))
                    number = get(question, "question_no", default="")
                    question_map[f"第 {number} 题 · {question_id}"] = question_id
            question_combo.configure(values=list(question_map))
            question_var.set(next(iter(question_map), ""))

        def refresh_chapters(_event: Any = None) -> None:
            chapter_map.clear()
            book_id = book_map.get(book_var.get())
            if book_id:
                for chapter in self.store.chapters(book_id=book_id):
                    number = int(get(chapter, "chapter_no", default=0))
                    title = str(get(chapter, "title", default=""))
                    chapter_map[f"第 {number} 章 · {title}"] = number
            chapter_combo.configure(values=list(chapter_map))
            chapter_var.set(next(iter(chapter_map), ""))
            refresh_questions()

        book_combo.bind("<<ComboboxSelected>>", refresh_chapters)
        chapter_combo.bind("<<ComboboxSelected>>", refresh_questions)
        refresh_chapters()

        actions = tk.Frame(form, bg=WHITE)
        actions.pack(fill="x", pady=(20, 0))

        def save() -> None:
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("昵称不能为空", "请输入学习者昵称。", parent=dialog)
                name_entry.focus_set()
                return
            selected_result = {"会": 1, "不会": 2}.get(result_var.get())
            question_id = question_map.get(question_var.get()) if selected_result else None
            if selected_result and not question_id:
                messagebox.showwarning("请选择题目", "选择“会”或“不会”时，需先选择习题册、章节和题目。",
                                       parent=dialog)
                return
            try:
                new_user = self.store.add_user(name, initial_question_id=question_id,
                                               initial_result=selected_result)
                new_id = str(get(new_user, "user_id", default=""))
                dialog.destroy()
                if self.active_page == "progress":
                    self._load_users(new_id)
                else:
                    self.show_page(self.active_page)
                    if self.active_page == "overview":
                        caption = next((caption for caption, user_id in self.home_user_ids.items()
                                        if user_id == new_id), None)
                        if caption:
                            self.home_user_var.set(caption)
            except Exception as exc:
                messagebox.showerror("添加学习者失败", str(exc), parent=dialog)

        button(actions, "取消", dialog.destroy, small=True).pack(side="right")
        button(actions, "保存学习者", save, primary=True,
               small=True).pack(side="right", padx=(0, 8))
        name_entry.focus_set()

    def _refresh_progress(self) -> None:
        user_id = self.user_ids.get(self.progress_user_var.get())
        self.progress_tree.delete(*self.progress_tree.get_children())
        if not user_id:
            return
        rows = self.store.user_progress(user_id)
        done = sum(1 for row in rows if str(get(row, "status", default=0)) in ("1", "2"))
        learned = sum(1 for row in rows if str(get(row, "status", default=0)) == "1")
        review = sum(1 for row in rows if str(get(row, "status", default=0)) == "2")
        for metric, value in zip(self.progress_metrics, (done, learned, review)):
            content = metric.content
            children = content.winfo_children()
            if len(children) >= 2:
                children[1].configure(text=str(value))
        for index, row in enumerate(rows):
            status = get(row, "status", default=0)
            ratio = get(row, "difficulty_coefficient")
            sample = int(get(row, "first_answer_count", "distinct_user_count", default=0) or 0)
            if str(status) == "2":
                hint = "优先复习"
            elif str(status) == "1":
                hint = "按计划巩固"
            elif sample >= 2 and ratio is not None and float(ratio) <= 0.4:
                hint = "可挑战高难题"
            else:
                hint = "尚未作答"
            self.progress_tree.insert("", "end", iid=str(index), values=(
                get(row, "question_id", default=""),
                get(row, "chapter_title", default=""),
                result_text(status),
                result_text(get(row, "first_result")),
                coefficient(ratio), hint,
            ))

    def _page_sql(self) -> None:
        work = tk.Frame(self.body, bg=BG)
        work.pack(fill="both", expand=True, pady=(0, 3))
        work.grid_columnconfigure(0, weight=0, minsize=260)
        work.grid_columnconfigure(1, weight=1)
        work.grid_rowconfigure(0, weight=1)

        list_panel = card(work, padding=14)
        list_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        list_panel.configure(width=260)
        list_panel.pack_propagate(False)
        label(list_panel.content, "查询案例", size=12,
              weight="bold").pack(fill="x", pady=(0, 12))
        self.query_list = tk.Listbox(
            list_panel.content, bg=WHITE, fg=TEXT, selectbackground=TEAL_LIGHT,
            selectforeground=TEAL, relief="flat", borderwidth=0,
            highlightthickness=0, font=(FONT, 10), activestyle="none",
            exportselection=False,
        )
        self.query_list.pack(fill="both", expand=True)
        self.query_list.bind("<<ListboxSelect>>", self._query_selected)

        result_panel = card(work, padding=14)
        result_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        line = tk.Frame(result_panel.content, bg=WHITE)
        line.pack(fill="x", pady=(0, 9))
        self.query_title = label(line, "", size=12, weight="bold")
        self.query_title.pack(side="left")
        button(line, "运行查询", self._run_query, primary=True,
               small=True).pack(side="right")
        button(line, "复制 SQL 语句", self._copy_sql,
               small=True).pack(side="right", padx=(0, 8))

        label(result_panel.content, "SQL 语句", size=8,
              color=MUTED).pack(fill="x")
        self.sql_text = tk.Text(result_panel.content, height=9, bg="#F1F6F8",
                                fg=TEXT, relief="flat", borderwidth=0,
                                padx=12, pady=10, font=("Consolas", 10),
                                wrap="none", state="disabled")
        self.sql_text.pack(fill="x", pady=(5, 12))
        self.query_result_caption = label(result_panel.content, "查询返回结果", size=9,
                                          weight="bold")
        self.query_result_caption.pack(fill="x", pady=(0, 8))
        self.result_holder = tk.Frame(result_panel.content, bg=WHITE)
        self.result_holder.pack(fill="both", expand=True)

        self.query_examples = self.store.query_examples()
        for example in self.query_examples:
            query_id = int(get(example, "id", default=0))
            title = str(get(example, "title", default=f"查询 {query_id}"))
            self.query_list.insert("end", f"{query_id:02d}  "
                                   f"{SQL_LIST_TITLES.get(query_id, title)}")
        if self.query_examples:
            self.query_list.selection_set(0)
            self._query_selected()

    def _query_selected(self, _event: Any = None) -> None:
        chosen = self.query_list.curselection()
        if not chosen:
            return
        example = self.query_examples[chosen[0]]
        title = str(get(example, "title", default=""))
        sql = str(get(example, "sql", default=""))
        self.query_title.configure(text=title)
        self.sql_text.configure(state="normal")
        self.sql_text.delete("1.0", "end")
        self.sql_text.insert("1.0", sql)
        self.sql_text.configure(state="disabled")
        self._run_query()

    def _copy_sql(self) -> None:
        sql = self.sql_text.get("1.0", "end").strip()
        if sql:
            self.root.clipboard_clear()
            self.root.clipboard_append(sql)
            self.query_result_caption.configure(text="SQL 已复制到剪贴板")

    def _run_query(self) -> None:
        chosen = self.query_list.curselection()
        if not chosen:
            return
        query_id = int(get(self.query_examples[chosen[0]], "id", default=0))
        try:
            result = self.store.run_query(query_id)
            columns = list(get(result, "columns", default=[]) or [])
            rows = list(get(result, "rows", default=[]) or [])
            for child in self.result_holder.winfo_children():
                child.destroy()
            if not columns:
                label(self.result_holder, "查询没有返回字段", color=MUTED).pack(fill="x")
                return
            specs = [(str(column), sql_column_title(column), 165) for column in columns]
            tree = self._tree(self.result_holder, specs, height=12)
            for index, row in enumerate(rows):
                values = [get(row, str(column), default="") for column in columns]
                tree.insert("", "end", iid=str(index),
                            values=["—" if value is None else str(value) for value in values])
            self.query_result_caption.configure(text=f"查询返回  ·  {len(rows)} 行")
        except Exception as exc:
            messagebox.showerror("查询执行失败", str(exc), parent=self.root)

    def _page_evidence(self) -> None:
        intro = card(self.body, padding=12)
        intro.pack(fill="x")
        label(intro.content, "在本地演示库中验证并发处理与备份恢复", size=12,
              weight="bold").pack(fill="x")
        label(intro.content,
              "左侧同时写入两条不同作答；右侧选择真实演示记录，先删除，再从删除前备份恢复。",
              size=9, color=MUTED, wraplength=850, justify="left").pack(fill="x", pady=(3, 0))

        panels = tk.Frame(self.body, bg=BG)
        panels.pack(fill="both", expand=True, pady=(10, 3))
        panels.grid_columnconfigure(0, weight=1)
        panels.grid_columnconfigure(1, weight=1)
        panels.grid_rowconfigure(0, weight=1)
        left = card(panels, padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = card(panels, padding=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        label(left.content, "两条作答并发写入", size=13,
              weight="bold").pack(fill="x")
        label(left.content, "两个线程提交不同事件，观察排队和最终状态。",
              size=9, color=MUTED, wraplength=360, justify="left").pack(fill="x", pady=(3, 7))
        button(left.content, "同时提交两条作答", self._run_concurrent_distinct,
               primary=True, small=True).pack(anchor="w")
        self.concurrency_output = self._evidence_text(left.content, [
            "执行过程",
            "1. 为同一学习者和题目准备两条不同 event_id 的作答，一条练习、一条复习。",
            "2. 两个线程各开一个 SQLite 连接，经同步屏障同时开始写事务。",
            "3. 先拿到写锁的线程提交；另一线程等待写锁，再写入并提交。",
            "4. 按作答时间而非提交先后确定首答及最新状态。",
            "5. 检查两个 event_id 均已保存，事件总数增加 2。",
            "",
            "点击按钮后，下方会显示每条事件、等待时间、提交顺序及核对结果。",
        ])

        label(right.content, "备份后恢复数据", size=13,
              weight="bold").pack(fill="x")
        label(right.content, "选择一条作答，生成删除前备份并删除；随后单独点击恢复。",
              size=9, color=MUTED, wraplength=360, justify="left").pack(fill="x", pady=(3, 6))
        self.recovery_event_var = tk.StringVar()
        self.recovery_event_ids: dict[str, str] = {}
        self.recovery_deleted_event_id: str | None = None
        self.recovery_event_combo = ttk.Combobox(
            right.content, textvariable=self.recovery_event_var,
            state="readonly", style="App.TCombobox", width=35)
        self.recovery_event_combo.pack(fill="x", pady=(0, 4))
        self.recovery_event_combo.bind("<<ComboboxSelected>>",
                                       lambda _event: self._show_recovery_selection())
        self.recovery_selection_label = label(
            right.content, "", size=8, color=MUTED,
            wraplength=360, justify="left")
        self.recovery_selection_label.pack(fill="x", pady=(0, 6))
        actions = tk.Frame(right.content, bg=WHITE)
        actions.pack(fill="x")
        self.delete_recovery_button = button(
            actions, "删除所选记录", self._delete_recovery_event,
            danger=True, small=True)
        self.delete_recovery_button.pack(side="left")
        self.restore_button = button(actions, "从备份恢复", self._restore_recovery,
                                     primary=True, small=True)
        self.restore_button.pack(side="left", padx=(8, 0))
        self.recovery_output = self._evidence_text(right.content, [
            "执行过程",
            "1. 在上方选定一条事件；保存当前完整数据库备份。",
            "2. 在写事务中删除这条事件，并重算此人此题的进度。",
            "3. 对照删除前后的记录数和个人进度，确认损失实际发生。",
            "4. 点击“从备份恢复”，把备份写回工作库。",
            "5. 比对各表行数、内容摘要、quick_check 和外键检查。",
            "",
            "恢复会回到删除前的备份时点；此后新增的作答也会被覆盖。",
        ])
        self._refresh_recovery_candidates()

    def _refresh_recovery_candidates(self, preferred_event_id: str | None = None) -> None:
        candidates = self.store.recovery_candidates(limit=200)
        self.recovery_event_ids = {}
        self.recovery_event_rows: dict[str, Any] = {}
        for event in candidates:
            event_id = str(get(event, "event_id", default=""))
            if not event_id:
                continue
            caption = (
                f"{get(event, 'display_name', 'user_id', default='')} · "
                f"{get(event, 'question_id', default='')} · "
                f"{result_text(get(event, 'result'))} · {event_id}")
            self.recovery_event_ids[caption] = event_id
            self.recovery_event_rows[event_id] = event
        labels = list(self.recovery_event_ids)
        self.recovery_event_combo.configure(
            values=labels, state="readonly" if labels else "disabled")
        selected = next((item for item in labels
                         if self.recovery_event_ids[item] == preferred_event_id), None)
        self.recovery_event_var.set(selected or (labels[0] if labels else ""))
        backup_pending = bool(self.store.has_recovery_backup())
        self.delete_recovery_button.configure(
            state="normal" if labels and not backup_pending else "disabled")
        self.restore_button.configure(state="normal" if backup_pending else "disabled")
        self._show_recovery_selection()

    def _show_recovery_selection(self) -> None:
        event_id = self.recovery_event_ids.get(self.recovery_event_var.get())
        if not event_id:
            self.recovery_selection_label.configure(text="暂无可选择的作答记录")
            return
        event = self.recovery_event_rows[event_id]
        role = []
        if get(event, "is_first_answer", default=False):
            role.append("首次作答")
        if get(event, "is_latest", default=False):
            role.append("当前最新")
        role_text = "、".join(role) if role else "中间记录"
        self.recovery_selection_label.configure(
            text=f"事件 {event_id} · {timestamp(get(event, 'answered_at'))} · {role_text}")

    def _set_evidence_output(self, output: tk.Text, lines: list[str],
                             result: Any = None) -> None:
        if result is not None:
            lines += ["", "原始检查数据", json.dumps(
                result, ensure_ascii=False, indent=2, default=str)]
        output.configure(state="normal")
        output.delete("1.0", "end")
        output.insert("1.0", "\n".join(lines))
        output.configure(state="disabled")
        output.yview_moveto(0)

    def _run_concurrent_distinct(self) -> None:
        try:
            result = self.store.concurrent_distinct_demo()
            requests = get(result, "requests", default=[]) or []
            outcomes = get(result, "outcomes", default=[]) or []
            role_name = {
                "earlier_practice": "较早时间的练习",
                "later_review": "较晚时间的复习",
            }
            order = get(result, "commit_order", default=[]) or []
            order_text = " → ".join(
                role_name.get(str(item), str(item)) for item in order) or "—"
            wait_text = "；".join(
                f"{role_name.get(str(get(item, 'label', default='?')), '?')} "
                f"{get(item, 'lock_wait_ms', default='—')} ms"
                for item in outcomes) or "—"
            lines = [
                "并发提交结果：" + ("通过" if get(result, "passed", default=False)
                                  else "未通过，请检查"),
                f"不同事件已保存：{get(result, 'row_count', default='—')} / 2；"
                f"全库作答 {get(result, 'before_event_count', default='—')} → "
                f"{get(result, 'after_event_count', default='—')}",
                f"写锁等待：{wait_text}",
                f"写锁取得 / 提交顺序：{order_text}",
                f"首答 {result_text(get(result, 'first_result'))}；"
                f"最新状态 {result_text(get(result, 'latest_status'))}",
                "",
                "详细过程",
                f"1. 学习者 {get(result, 'user_id', default='—')}，"
                f"题目 {get(result, 'question_id', default='—')}。",
                "   两个不同 event_id 的请求经同步屏障同时开始：",
            ]
            for request in requests:
                event_type = ("复习" if get(request, "event_type") == "review"
                              else "练习")
                role = str(get(request, "label", default="?"))
                event_id = str(get(request, "event_id", default="—"))
                lines.append(
                    f"  {role_name.get(role, role)}："
                    f"…{event_id[-8:]} · {event_type} · "
                    f"{result_text(get(request, 'result'))} · "
                    f"{timestamp(get(request, 'answered_at'))}")
            lines += ["", "2. 同时出发，各连接等待并取得 SQLite 写锁"]
            for outcome in outcomes:
                wait_ms = get(outcome, "lock_wait_ms", default="—")
                transaction_ms = get(outcome, "transaction_ms", default="—")
                role = str(get(outcome, "label", default="?"))
                status = str(get(outcome, "status", default="—"))
                event_id = str(get(outcome, "event_id", default="—"))
                lines.append(
                    f"  {role_name.get(role, role)} / "
                    f"…{event_id[-8:]}："
                    f"{'已写入' if status == 'inserted' else status}；"
                    f"等待写锁 {wait_ms} ms，事务用时 {transaction_ms} ms")
            lines += [
                "",
                "3. 按作答时间重建首答与最新状态",
                f"  首次作答：{timestamp(get(result, 'first_answered_at'))}，"
                f"自评 {result_text(get(result, 'first_result'))}",
                f"  最新状态：{timestamp(get(result, 'last_answered_at'))}，"
                f"自评 {result_text(get(result, 'latest_status'))}",
                "  首答和最新状态按作答时间计算，与线程提交先后无关。",
                "",
                "4. 持久化核对",
                f"  两个事件编号实际保存：{get(result, 'row_count', default='—')} 条（预期 2 条）",
                f"  全库作答数：{get(result, 'before_event_count', default='—')} → "
                f"{get(result, 'after_event_count', default='—')}（预期增加 2）",
            ]
            self._set_evidence_output(self.concurrency_output, lines, result)
            self._refresh_recovery_candidates()
        except Exception as exc:
            messagebox.showerror("并发演示失败", str(exc), parent=self.root)

    def _delete_recovery_event(self) -> None:
        event_id = self.recovery_event_ids.get(self.recovery_event_var.get())
        if not event_id:
            messagebox.showwarning("请选择作答记录", "请先从下拉框选择一条作答记录。",
                                   parent=self.root)
            return
        try:
            result = self.store.delete_event_for_recovery(event_id)
            before = get(result, "before_counts", default={}) or {}
            after = get(result, "after_counts", default={}) or {}
            backup_path = get(result, "backup_path", default="")
            lines = [
                "删除阶段：" + ("已核对" if get(result, "passed", default=False)
                              else "核对未通过，请检查"),
                f"已选择并删除事件：…{event_id[-8:]}",
                f"备份文件：{Path(str(backup_path)).name if backup_path else '—'}"
                "（本地演示数据目录）",
                "",
                "1. 从当前完整演示库创建备份，保存删除前状态。",
                "2. 在数据库事务中删除所选事件，重算对应的个人逐题进度。",
                f"3. 作答记录数：{get(before, 'answer_events', default='—')} → "
                f"{get(after, 'answer_events', default='—')}",
                f"4. 逐题进度行数：{get(before, 'user_question_progress', default='—')} → "
                f"{get(after, 'user_question_progress', default='—')}",
                f"5. 此人此题删除前进度："
                f"{json.dumps(get(result, 'progress_before'), ensure_ascii=False, default=str)}",
                f"   删除后进度："
                f"{json.dumps(get(result, 'progress_after'), ensure_ascii=False, default=str)}",
                "",
                "点击“从备份恢复”后，将回到删除前的完整备份时点；"
                "备份后新增的其他作答也会被覆盖。",
            ]
            self._set_evidence_output(self.recovery_output, lines, result)
            self.recovery_deleted_event_id = event_id
            self._refresh_recovery_candidates()
        except Exception as exc:
            messagebox.showerror("删除演示记录失败", str(exc), parent=self.root)
            self._refresh_recovery_candidates()

    def _restore_recovery(self) -> None:
        try:
            result = self.store.restore_recovery_backup()
            before = get(result, "before_counts", default={}) or {}
            after = get(result, "after_counts", default={}) or {}
            backup = get(result, "backup_counts", default={}) or {}
            lines = [
                "备份恢复结果：" + ("通过" if get(result, "passed", default=False)
                                  else "未通过，请检查"),
                "",
                "1. 将删除前备份写回本地工作数据库。",
                f"2. 作答记录数：删除后 {get(before, 'answer_events', default='—')} → "
                f"恢复后 {get(after, 'answer_events', default='—')}；"
                f"备份为 {get(backup, 'answer_events', default='—')}",
                f"3. 逐题进度行数：删除后 "
                f"{get(before, 'user_question_progress', default='—')} → "
                f"恢复后 {get(after, 'user_question_progress', default='—')}",
                f"4. 六张表内容摘要与备份一致："
                f"{'是' if get(result, 'hashes_match', default=False) else '否'}",
                f"5. 数据库 quick_check：{get(result, 'quick_check', default='—')}",
                f"6. 外键错误数：{get(result, 'foreign_key_errors', default='—')}",
                "",
                "恢复完成后，所选事件会重新出现在上方列表中。",
            ]
            self._set_evidence_output(self.recovery_output, lines, result)
            event = get(result, "event", default={}) or {}
            self._refresh_recovery_candidates(
                preferred_event_id=get(event, "event_id",
                                       default=self.recovery_deleted_event_id))
            self.recovery_deleted_event_id = None
        except Exception as exc:
            messagebox.showerror("备份恢复失败", str(exc), parent=self.root)
            self._refresh_recovery_candidates()

    def _evidence_text(self, parent: tk.Misc, lines: list[str]) -> tk.Text:
        holder = tk.Frame(parent, bg="#F1F6F8")
        holder.pack(fill="both", expand=True, pady=(13, 0))
        output = tk.Text(holder, bg="#F1F6F8", fg=TEXT, relief="flat",
                         borderwidth=0, padx=12, pady=12, wrap="word",
                         font=(FONT, 10), spacing2=3, spacing3=5)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=output.yview,
                               style="App.Vertical.TScrollbar")
        output.configure(yscrollcommand=scroll.set)
        output.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        output.insert("1.0", "\n".join(lines))
        output.configure(state="disabled")
        return output

    def _page_about(self) -> None:
        panel = card(self.body, padding=24)
        panel.pack(fill="both", expand=True, pady=(0, 3))
        sections = [
            ("这个软件展示什么", "它把考研数学小程序中的习题册、章节、题号和学习者“会 / 不会”记录，做成可查询的 SQLite 关系型数据库课程演示。您可以筛选题目、添加匿名学习者、记录作答并立即观察统计变化。"),
            ("难度系数口径", "每位学习者对每道题只计最早一次作答。系数 = 首次作答时标记“会”的人数 ÷ 首次作答人数，范围为 0 到 1。越小表示这个样本中自评会做的人越少；无人首次作答时显示“暂无样本”。"),
            ("作答结果的含义", "“会 / 不会”由使用者自行标记，不代表系统读取题目标准答案或自动阅卷。复习和重做会保留在作答记录里，个人最新状态会变化，但题目的首次作答统计不会被重复计数。"),
            ("数据来源与边界", "软件使用匿名样例数据，在您的电脑上离线运行。它不连接微信 CloudBase，也不包含或同步真实微信用户的作答记录。正式微信小程序仍使用独立的云数据库。"),
            ("数据库要素", "六张表：学习者表 users、习题册表 books、章节表 chapters、题目表 questions、作答记录表 answer_events、学习进度表 user_question_progress；两个统计视图：首次作答视图 v_first_answers、题目难度视图 v_question_difficulty。另有主外键、CHECK 约束、索引、触发器、六类 SQL 查询、并发事务和备份恢复演示。"),
        ]
        for heading, description in sections:
            label(panel.content, heading, size=11, weight="bold").pack(fill="x", pady=(0, 5))
            label(panel.content, description, size=9, color=MUTED,
                  wraplength=900, justify="left").pack(fill="x", pady=(0, 19))
        button(panel.content, "恢复初始演示数据", self._reset_demo,
               danger=True, small=True).pack(anchor="w", pady=(2, 0))

    def _reset_demo(self) -> None:
        confirmed = messagebox.askyesno(
            "恢复初始演示数据", "将清除本软件中新增的匿名学习者和作答记录，恢复初始样例。确定继续吗？",
            parent=self.root,
        )
        if not confirmed:
            return
        try:
            self.store.reset()
            self.show_page("overview")
            messagebox.showinfo("已恢复初始数据", "本地演示数据已恢复初始样例。",
                                parent=self.root)
        except Exception as exc:
            messagebox.showerror("恢复初始数据失败", str(exc), parent=self.root)


def main() -> None:
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
