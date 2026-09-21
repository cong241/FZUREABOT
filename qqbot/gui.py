from __future__ import annotations

import queue
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Callable

from .models import DutyEntry, Settings
from .napcat import NapCatClient, NapCatEndpoint
from .scheduler import SchedulerController
from .service import ReminderResult, ReminderService
from .storage import (
    load_roster,
    load_sent_dates,
    load_settings,
    next_workday,
    save_roster,
    save_sent_dates,
)


def parse_entry_fields(date_text: str, qq_text: str, name: str) -> DutyEntry:
    try:
        duty_date = datetime.strptime(date_text.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("日期必须是 YYYY-MM-DD 格式") from exc
    if not qq_text.strip().isdigit():
        raise ValueError("QQ号只能包含数字")
    return DutyEntry(duty_date, int(qq_text), name)


class DutyBotWindow:
    def __init__(self, root: tk.Tk, base_dir: Path) -> None:
        self.root = root
        self.base_dir = base_dir
        self.roster_path = base_dir / "roster.json"
        self.settings_path = base_dir / "settings.json"
        self.sent_path = base_dir / "sent_reminders.json"
        self.settings: Settings = load_settings(self.settings_path)
        self.entries = load_roster(self.roster_path)
        self.sent_dates = load_sent_dates(self.sent_path)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="napcat")
        self.results: queue.Queue[Callable[[], None]] = queue.Queue()
        self.scheduler = SchedulerController(self.settings.send_time, self._scheduled_send)

        self.status_var = tk.StringVar(value="NapCat：尚未检查")
        self.auto_var = tk.StringVar(value="自动提醒：已停止")
        self.next_var = tk.StringVar(value="")
        self._build_ui()
        self._refresh_tree()
        self._refresh_next()
        self.start_auto()
        self.root.after(100, self._drain_results)
        self.root.after(500, self._run_pending)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.root.title("QQ 值班提醒机器人")
        self.root.geometry("900x650")
        self.root.minsize(760, 520)

        top = ttk.LabelFrame(self.root, text="运行状态", padding=10)
        top.pack(fill="x", padx=10, pady=(10, 5))
        ttk.Label(top, textvariable=self.status_var).pack(anchor="w")
        ttk.Label(top, textvariable=self.auto_var).pack(anchor="w")
        ttk.Label(top, textvariable=self.next_var).pack(anchor="w")

        roster_frame = ttk.LabelFrame(self.root, text="值班排班", padding=8)
        roster_frame.pack(fill="both", expand=True, padx=10, pady=5)
        columns = ("date", "qq", "name")
        self.tree = ttk.Treeview(roster_frame, columns=columns, show="headings")
        self.tree.heading("date", text="值班日期")
        self.tree.heading("qq", text="QQ号")
        self.tree.heading("name", text="姓名")
        self.tree.column("date", width=150, anchor="center")
        self.tree.column("qq", width=180, anchor="center")
        self.tree.column("name", width=160, anchor="center")
        scrollbar = ttk.Scrollbar(roster_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        edit_bar = ttk.Frame(self.root, padding=(10, 5))
        edit_bar.pack(fill="x")
        ttk.Button(edit_bar, text="继续排班", command=self.add_entry).pack(side="left", padx=3)
        ttk.Button(edit_bar, text="修改选中", command=self.edit_entry).pack(side="left", padx=3)
        ttk.Button(edit_bar, text="删除选中", command=self.delete_entry).pack(side="left", padx=3)
        ttk.Button(edit_bar, text="保存排班", command=self.save_entries).pack(side="left", padx=3)

        action_bar = ttk.LabelFrame(self.root, text="发送控制", padding=8)
        action_bar.pack(fill="x", padx=10, pady=5)
        ttk.Button(action_bar, text="检查连接", command=self.check_connection).pack(side="left", padx=3)
        ttk.Button(action_bar, text="立即提醒明天值班人", command=self.send_tomorrow).pack(side="left", padx=3)
        ttk.Button(action_bar, text="强制重发", command=self.force_send_tomorrow).pack(side="left", padx=3)
        ttk.Button(action_bar, text="启动自动提醒", command=self.start_auto).pack(side="left", padx=3)
        ttk.Button(action_bar, text="停止自动提醒", command=self.stop_auto).pack(side="left", padx=3)

        log_frame = ttk.LabelFrame(self.root, text="运行日志", padding=8)
        log_frame.pack(fill="both", padx=10, pady=(5, 10))
        self.log_text = tk.Text(log_frame, height=7, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

    def _refresh_tree(self) -> None:
        self.entries.sort(key=lambda item: item.duty_date)
        self.tree.delete(*self.tree.get_children())
        for entry in self.entries:
            self.tree.insert(
                "", "end", iid=entry.duty_date.isoformat(),
                values=(entry.duty_date.isoformat(), entry.qq, entry.name),
            )

    def _refresh_next(self) -> None:
        tomorrow = date.today() + timedelta(days=1)
        entry = next((item for item in self.entries if item.duty_date == tomorrow), None)
        if entry:
            self.next_var.set(
                f"明日值班：{entry.name}（QQ {entry.qq}，{tomorrow.isoformat()}）"
            )
        else:
            future = next((item for item in self.entries if item.duty_date > date.today()), None)
            if future:
                self.next_var.set(
                    f"下一次值班：{future.name}（{future.duty_date.isoformat()}）"
                )
            else:
                self.next_var.set("后续没有排班，请点击“继续排班”添加")

    def _selected_entry(self) -> DutyEntry | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择一条排班记录")
            return None
        key = selected[0]
        return next(item for item in self.entries if item.duty_date.isoformat() == key)

    def _ask_entry(self, initial: DutyEntry | None = None) -> DutyEntry | None:
        if initial:
            default_date = initial.duty_date.isoformat()
            default_qq = str(initial.qq)
            default_name = initial.name
        else:
            last = max((item.duty_date for item in self.entries), default=date.today())
            default_date = next_workday(last).isoformat()
            default_qq = ""
            default_name = ""
        date_text = simpledialog.askstring("值班日期", "请输入日期（YYYY-MM-DD）", initialvalue=default_date, parent=self.root)
        if date_text is None:
            return None
        qq_text = simpledialog.askstring("QQ号", "请输入群成员QQ号", initialvalue=default_qq, parent=self.root)
        if qq_text is None:
            return None
        name = simpledialog.askstring("姓名", "请输入群名片末尾姓名", initialvalue=default_name, parent=self.root)
        if name is None:
            return None
        try:
            return parse_entry_fields(date_text, qq_text, name)
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc))
            return None

    def add_entry(self) -> None:
        entry = self._ask_entry()
        if entry is None:
            return
        if any(item.duty_date == entry.duty_date for item in self.entries):
            messagebox.showerror("日期重复", f"{entry.duty_date} 已有排班")
            return
        self.entries.append(entry)
        self._refresh_tree()
        self._refresh_next()

    def edit_entry(self) -> None:
        original = self._selected_entry()
        if original is None:
            return
        replacement = self._ask_entry(original)
        if replacement is None:
            return
        if replacement.duty_date != original.duty_date and any(
            item.duty_date == replacement.duty_date for item in self.entries
        ):
            messagebox.showerror("日期重复", f"{replacement.duty_date} 已有排班")
            return
        self.entries[self.entries.index(original)] = replacement
        self._refresh_tree()
        self._refresh_next()

    def delete_entry(self) -> None:
        entry = self._selected_entry()
        if entry and messagebox.askyesno("确认删除", f"删除 {entry.duty_date} 的 {entry.name}？"):
            self.entries.remove(entry)
            self._refresh_tree()
            self._refresh_next()

    def save_entries(self) -> None:
        try:
            save_roster(self.roster_path, self.entries)
        except ValueError as exc:
            messagebox.showerror("保存失败", str(exc))
            return
        self._log("排班已保存")

    def _make_service(self) -> ReminderService:
        endpoint = NapCatEndpoint.from_config(Path(self.settings.napcat_config))
        return ReminderService(
            self.settings,
            self.entries,
            self.sent_dates,
            client_factory=lambda: NapCatClient(endpoint),
            persist_sent=lambda dates: save_sent_dates(self.sent_path, dates),
        )

    def _submit(self, operation: Callable[[], object], callback: Callable[[object], None]) -> None:
        future = self.executor.submit(operation)

        def completed(done):
            try:
                value = done.result()
                self.results.put(lambda: callback(value))
            except Exception as exc:
                self.results.put(lambda exc=exc: self._show_error(exc))

        future.add_done_callback(completed)

    def check_connection(self) -> None:
        def check():
            service = self._make_service()
            client = service.client_factory()
            return client.get_login_info()

        def show(info):
            qq = int(info.get("user_id", 0))
            if qq != self.settings.robot_qq:
                self.status_var.set(f"NapCat：账号不符（当前 {qq}）")
            else:
                self.status_var.set(f"NapCat：已连接，机器人 {qq}")
            self._log(self.status_var.get())

        self._submit(check, show)

    def send_tomorrow(self) -> None:
        self._send(date.today() + timedelta(days=1), force=False)

    def force_send_tomorrow(self) -> None:
        if messagebox.askyesno("确认强制重发", "这可能让同一成员收到重复提醒，确定继续吗？"):
            self._send(date.today() + timedelta(days=1), force=True)

    def _scheduled_send(self) -> None:
        self._send(date.today() + timedelta(days=1), force=False)

    def _send(self, duty_date: date, *, force: bool) -> None:
        self._submit(lambda: self._make_service().send(duty_date, force=force), self._show_result)

    def _show_result(self, result: object) -> None:
        assert isinstance(result, ReminderResult)
        self._log(result.message)
        if result.status == "error":
            messagebox.showerror("发送失败", result.message)
        elif result.status == "sent":
            messagebox.showinfo("发送成功", result.message)

    def start_auto(self) -> None:
        self.scheduler.start()
        self.auto_var.set(f"自动提醒：运行中（每天 {self.settings.send_time}）")
        self._log(self.auto_var.get())

    def stop_auto(self) -> None:
        self.scheduler.stop()
        self.auto_var.set("自动提醒：已停止")
        self._log(self.auto_var.get())

    def _run_pending(self) -> None:
        self.scheduler.run_pending()
        self.root.after(500, self._run_pending)

    def _drain_results(self) -> None:
        while True:
            try:
                callback = self.results.get_nowait()
            except queue.Empty:
                break
            callback()
        self.root.after(100, self._drain_results)

    def _show_error(self, exc: Exception) -> None:
        self._log(f"操作失败：{exc}")
        messagebox.showerror("操作失败", str(exc))

    def _log(self, message: str) -> None:
        if not hasattr(self, "log_text"):
            return
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{stamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        warning = "关闭窗口后自动提醒会停止。确定退出吗？"
        if not self.scheduler.running or messagebox.askyesno("确认退出", warning):
            self.scheduler.stop()
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.root.destroy()
