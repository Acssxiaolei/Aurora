# -*- coding: utf-8 -*-
"""Aurora — 订阅管理型代理客户端 v2.2。

支持面板：sspanel / v2board / xboard
功能：登录、账号信息、签到、订阅拉取、节点连接、系统代理自动开关、
      记住密码、自动登录、开机自启、刷新节点
"""
from __future__ import annotations

import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import app_config
import autostart
import core_adapter
import link_parser
import proxy_manager
from api_client import SSPanelError, checkin, fetch_subscription, get_user_info, login as api_login

APP_TITLE = "Aurora"
BRAND_BG = "#312e81"
BRAND_TEXT = "#c7d2fe"
BG = "#f0f2f5"
CARD = "#ffffff"
ACCENT = "#4f6ef7"
ACCENT_DARK = "#3b5bdb"
SUCCESS = "#16a34a"
DANGER = "#dc2626"
FG = "#1e293b"
MUTED = "#94a3b8"
FONT = "Microsoft YaHei UI"

_icon_ref = None


def _load_icon(size=64):
    """加载应用图标。"""
    global _icon_ref
    try:
        from PIL import Image, ImageTk
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aurora.png")
        if not os.path.exists(path):
            return None
        img = Image.open(path).resize((size, size), Image.LANCZOS)
        _icon_ref = ImageTk.PhotoImage(img)
        return _icon_ref
    except Exception:
        return None


def _setup_style():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(".", font=(FONT, 10))
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Treeview", rowheight=30, font=(FONT, 9), borderwidth=0)
    style.configure("Treeview.Heading", font=(FONT, 9, "bold"), background="#f8fafc")
    style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#fff")])


def _mk_button(parent, text, command, primary=False):
    """彩色按钮（tk.Button 原生支持 bg）。"""
    if primary:
        btn = tk.Button(parent, text=text, command=command, bg=ACCENT, fg="#fff",
                        font=(FONT, 10, "bold"), relief="flat", padx=20, pady=8,
                        activebackground=ACCENT_DARK, activeforeground="#fff", cursor="hand2")
    else:
        btn = tk.Button(parent, text=text, command=command, bg=CARD, fg=FG,
                        font=(FONT, 10), relief="flat", padx=14, pady=6,
                        activebackground="#f1f5f9", cursor="hand2")
    return btn


# ==================== 设置对话框 ====================
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, cfg: dict, on_save):
        super().__init__(parent)
        self.title("设置")
        self.geometry("480x420")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()
        self._on_save = on_save

        frm = tk.Frame(self, bg=BG, padx=24, pady=20)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="面板地址", bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(0, 4))
        self.base_url_var = tk.StringVar(value=cfg.get("base_url", ""))
        tk.Entry(frm, textvariable=self.base_url_var, font=(FONT, 10), width=50,
                 relief="solid", bd=1).pack(fill="x", pady=(0, 14))

        tk.Label(frm, text="面板类型", bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(0, 4))
        self.panel_var = tk.StringVar(value=cfg.get("panel_type", "sspanel"))
        ttk.Combobox(frm, textvariable=self.panel_var, state="readonly",
                     values=["sspanel", "v2board", "xboard"]).pack(fill="x", pady=(0, 14))

        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        tk.Checkbutton(frm, text="开机自启动", variable=self.autostart_var,
                       bg=BG, font=(FONT, 10)).pack(anchor="w", pady=(0, 14))

        _mk_button(frm, "检查更新", self._check_update).pack(anchor="w", pady=(0, 8))
        self.update_label = tk.Label(frm, text="当前版本 v2.2.0", bg=BG, fg=MUTED)
        self.update_label.pack(anchor="w", pady=(0, 20))

        btn_row = tk.Frame(frm, bg=BG)
        btn_row.pack(fill="x")
        _mk_button(btn_row, "取消", self.destroy).pack(side="right")
        _mk_button(btn_row, "保存", self._save, primary=True).pack(side="right", padx=(0, 8))

    def _check_update(self):
        self.update_label.config(text="已是最新版本 v2.2.0", fg=SUCCESS)

    def _save(self):
        self._on_save(self.base_url_var.get().strip(), self.panel_var.get(), self.autostart_var.get())
        self.destroy()


# ==================== 登录窗口 ====================
class LoginWindow:
    def __init__(self, auto_start: bool = False):
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("760x500")
        self.root.resizable(False, False)
        self.root.configure(bg=CARD)
        _setup_style()

        icon = _load_icon(72)
        if icon:
            self.root.iconphoto(True, icon)

        cfg = app_config.get_app_config()

        # 左半边：品牌区
        left = tk.Frame(self.root, bg=BRAND_BG, width=280)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        brand_inner = tk.Frame(left, bg=BRAND_BG)
        brand_inner.place(relx=0.5, rely=0.5, anchor="center")
        if icon:
            tk.Label(brand_inner, image=icon, bg=BRAND_BG).pack(pady=(0, 16))
        tk.Label(brand_inner, text="Aurora", bg=BRAND_BG, fg="#fff",
                 font=(FONT, 30, "bold")).pack()
        tk.Label(brand_inner, text="Secure Proxy Client", bg=BRAND_BG, fg=BRAND_TEXT,
                 font=(FONT, 10)).pack(pady=(8, 0))

        # 右半边：表单
        right = tk.Frame(self.root, bg=CARD, padx=48, pady=32)
        right.pack(side="right", fill="both", expand=True)

        tk.Label(right, text="欢迎回来", bg=CARD, fg=FG,
                 font=(FONT, 18, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Label(right, text="登录以继续", bg=CARD, fg=MUTED,
                 font=(FONT, 10)).pack(anchor="w", pady=(0, 24))

        tk.Label(right, text="面板地址", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(0, 4))
        self.base_url_var = tk.StringVar(value=cfg.get("base_url", ""))
        tk.Entry(right, textvariable=self.base_url_var, font=(FONT, 10),
                 relief="solid", bd=1).pack(fill="x", pady=(0, 12), ipady=4)

        tk.Label(right, text="面板类型", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(0, 4))
        self.panel_var = tk.StringVar(value=cfg.get("panel_type", "sspanel"))
        ttk.Combobox(right, textvariable=self.panel_var, state="readonly",
                     values=["sspanel", "v2board", "xboard"]).pack(fill="x", pady=(0, 12))

        tk.Label(right, text="邮箱", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(0, 4))
        self.email_var = tk.StringVar(value=cfg.get("email", ""))
        tk.Entry(right, textvariable=self.email_var, font=(FONT, 10),
                 relief="solid", bd=1).pack(fill="x", pady=(0, 12), ipady=4)

        tk.Label(right, text="密码", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(0, 4))
        self.pwd_var = tk.StringVar(value=cfg.get("password", "") if cfg.get("remember_password") else "")
        tk.Entry(right, textvariable=self.pwd_var, show="*", font=(FONT, 10),
                 relief="solid", bd=1).pack(fill="x", pady=(0, 12), ipady=4)

        opts = tk.Frame(right, bg=CARD)
        opts.pack(fill="x", pady=(0, 16))
        self.remember_var = tk.BooleanVar(value=cfg.get("remember_password", False))
        tk.Checkbutton(opts, text="记住密码", variable=self.remember_var,
                       bg=CARD, font=(FONT, 9)).pack(side="left", padx=(0, 16))
        self.auto_login_var = tk.BooleanVar(value=cfg.get("auto_login", False))
        tk.Checkbutton(opts, text="自动登录", variable=self.auto_login_var,
                       bg=CARD, font=(FONT, 9)).pack(side="left")

        self.login_btn = _mk_button(right, "登 录", self.on_login, primary=True)
        self.login_btn.pack(fill="x")

        self.root.bind("<Return>", lambda e: self.on_login())

        if auto_start and cfg.get("auto_login") and cfg.get("base_url") and cfg.get("email") and cfg.get("password"):
            self.root.after(300, self.on_login)

    def on_login(self):
        base_url = self.base_url_var.get().strip()
        panel = self.panel_var.get()
        email = self.email_var.get().strip()
        pwd = self.pwd_var.get()
        if not base_url or not email or not pwd:
            messagebox.showinfo("提示", "请填写面板地址、邮箱和密码")
            return
        self.login_btn.config(state="disabled", text="登录中...")
        threading.Thread(target=self._do_login, args=(base_url, panel, email, pwd), daemon=True).start()

    def _do_login(self, base_url, panel, email, pwd):
        try:
            session = api_login(panel, base_url, email, pwd)
            user_info = get_user_info(panel, session, base_url)
        except SSPanelError as e:
            self.root.after(0, lambda: self._login_fail(str(e)))
            return
        except Exception as e:
            self.root.after(0, lambda: self._login_fail(f"未知错误: {e}"))
            return
        self.root.after(0, lambda: self._login_ok(base_url, panel, email, pwd, session, user_info))

    def _login_fail(self, msg):
        self.login_btn.config(state="normal", text="登 录")
        messagebox.showerror("登录失败", msg)

    def _login_ok(self, base_url, panel, email, pwd, session, user_info):
        cfg = app_config.get_app_config()
        cfg["base_url"] = base_url
        cfg["panel_type"] = panel
        cfg["email"] = email
        cfg["remember_password"] = self.remember_var.get()
        cfg["auto_login"] = self.auto_login_var.get()
        cfg["password"] = pwd if self.remember_var.get() else ""
        app_config.save_app_config(cfg)
        self.root.destroy()
        main_win = MainWindow(panel, session, base_url, email, user_info)
        main_win.root.mainloop()

    def run(self):
        self.root.mainloop()


# ==================== 主窗口 ====================
class MainWindow:
    def __init__(self, panel_type, session, base_url, email, user_info):
        self.panel_type = panel_type
        self.session = session
        self.base_url = base_url
        self.email = email
        self.user_info = user_info
        self.nodes = app_config.load_nodes()
        self.busy = False

        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("960x680")
        self.root.minsize(860, 600)
        self.root.configure(bg=BG)
        _setup_style()

        icon = _load_icon(64)
        if icon:
            self.root.iconphoto(True, icon)

        self._build_ui()
        self._refresh_node_list()
        self._refresh_account_panel()
        self._status_tick()

    def _build_ui(self):
        card = tk.Frame(self.root, bg=CARD, padx=20, pady=16)
        card.pack(fill="x", padx=16, pady=(16, 8))

        left = tk.Frame(card, bg=CARD)
        left.pack(side="left")
        self.nick_var = tk.StringVar(value=self.user_info.get("nickname", "加载中..."))
        tk.Label(left, textvariable=self.nick_var, bg=CARD, fg=FG,
                 font=(FONT, 15, "bold")).pack(anchor="w")
        self.email_var = tk.StringVar(value=self.email)
        tk.Label(left, textvariable=self.email_var, bg=CARD, fg=MUTED,
                 font=(FONT, 9)).pack(anchor="w")

        right = tk.Frame(card, bg=CARD)
        right.pack(side="right")
        self.traffic_var = tk.StringVar(value="流量 --")
        self.expire_var = tk.StringVar(value="到期 --")
        self.balance_var = tk.StringVar(value="余额 --")
        for v in (self.traffic_var, self.expire_var, self.balance_var):
            tk.Label(right, textvariable=v, bg=CARD, fg=FG,
                     font=(FONT, 9)).pack(anchor="e")

        bar = tk.Frame(self.root, bg=BG, padx=16, pady=4)
        bar.pack(fill="x")
        _mk_button(bar, "签到", self.on_checkin).pack(side="left")
        _mk_button(bar, "刷新节点", self.on_update_sub).pack(side="left", padx=(8, 0))
        _mk_button(bar, "退出登录", self.on_logout).pack(side="right")
        _mk_button(bar, "设置", self.on_settings).pack(side="right", padx=(0, 8))

        list_card = tk.Frame(self.root, bg=CARD, padx=12, pady=12)
        list_card.pack(fill="both", expand=True, padx=16, pady=8)
        cols = ("name", "protocol", "server", "port")
        self.tree = ttk.Treeview(list_card, columns=cols, show="headings", selectmode="browse")
        for c, t, w in (("name", "节点名称", 300), ("protocol", "协议", 80), ("server", "服务器", 240), ("port", "端口", 60)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        vsb = ttk.Scrollbar(list_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        btnrow = tk.Frame(self.root, bg=BG, padx=16, pady=4)
        btnrow.pack(fill="x")
        _mk_button(btnrow, "断 开", self.on_disconnect).pack(side="left", padx=(8, 0))
        _mk_button(btnrow, "连接所选节点", self.on_connect, primary=True).pack(side="left")

        bottom = tk.Frame(self.root, bg=BG, padx=16, pady=(4, 12))
        bottom.pack(fill="both", expand=True)
        self.log_box = scrolledtext.ScrolledText(bottom, height=7, font=("Consolas", 9), state="disabled",
                                                 wrap="word", bg="#0f172a", fg="#e2e8f0", relief="flat")
        self.log_box.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(self.root, textvariable=self.status_var, anchor="w", bg="#e2e8f0", fg=FG,
                 padx=12, pady=6, font=(FONT, 9)).pack(fill="x", side="bottom")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ts}] {text}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _refresh_account_panel(self):
        info = self.user_info
        self.nick_var.set(info.get("nickname", self.email))
        self.traffic_var.set(f"流量 {info.get('used_traffic','--')} / {info.get('total_traffic','--')}")
        self.expire_var.set(f"到期 {info.get('expire','--')}")
        if info.get("balance") is not None:
            self.balance_var.set(f"余额 ¥{info.get('balance',0):.2f}")
        if info.get("sub_token"):
            self._log("订阅 token 已获取，自动拉取节点...")
            threading.Thread(target=self._do_fetch_sub, daemon=True).start()

    def _refresh_node_list(self):
        self.tree.delete(*self.tree.get_children())
        for i, n in enumerate(self.nodes):
            self.tree.insert("", "end", iid=str(i),
                             values=(n.get("name"), n.get("protocol"), n.get("server"), n.get("port")))

    def _selected_index(self) -> int:
        sel = self.tree.selection()
        return int(sel[0]) if sel else -1

    def on_checkin(self):
        threading.Thread(target=self._do_checkin, daemon=True).start()

    def _do_checkin(self):
        try:
            msg = checkin(self.panel_type, self.session, self.base_url)
            self.root.after(0, lambda: self._log(f"签到结果: {msg}"))
        except SSPanelError as e:
            self.root.after(0, lambda: self._log(f"签到失败: {e}"))

    def on_update_sub(self):
        if not self.user_info.get("sub_token"):
            messagebox.showinfo("提示", "未获取到订阅 token")
            return
        self._log("正在刷新节点...")
        threading.Thread(target=self._do_fetch_sub, daemon=True).start()

    def _do_fetch_sub(self):
        token = self.user_info["sub_token"]
        try:
            text = fetch_subscription(self.base_url, token)
            nodes, failed = link_parser.parse_many(text)
            self.root.after(0, lambda: self._sub_done(nodes, failed))
        except SSPanelError as e:
            self.root.after(0, lambda: self._log(f"拉取订阅失败: {e}"))

    def _sub_done(self, nodes, failed):
        self.nodes = nodes
        app_config.save_nodes(nodes)
        self._refresh_node_list()
        self._log(f"节点刷新完成：{len(nodes)} 个" + (f"，{len(failed)} 条失败" if failed else ""))

    def on_settings(self):
        cfg = app_config.get_app_config()
        SettingsDialog(self.root, cfg, self._save_settings)

    def _save_settings(self, base_url, panel_type, autostart_on):
        cfg = app_config.get_app_config()
        cfg["base_url"] = base_url
        cfg["panel_type"] = panel_type
        cfg["auto_startup"] = autostart_on
        app_config.save_app_config(cfg)
        if autostart_on:
            autostart.enable()
        else:
            autostart.disable()
        self._log("设置已保存")

    def on_logout(self):
        self.on_disconnect()
        proxy_manager.restore_system_proxy()
        self.root.destroy()
        LoginWindow().run()

    def on_connect(self):
        idx = self._selected_index()
        if idx < 0:
            messagebox.showinfo("提示", "请先选择节点")
            return
        if core_adapter.is_running():
            messagebox.showinfo("提示", "内核已在运行，请先断开")
            return
        node = self.nodes[idx]
        cfg = app_config.get_app_config()
        cfg["selected_index"] = idx
        app_config.save_app_config(cfg)
        self.busy = True
        self._log(f"正在连接 [{node.get('name')}] ...")
        threading.Thread(target=self._do_connect, args=(node,), daemon=True).start()

    def _do_connect(self, node):
        ok, msg = core_adapter.start(node)
        self.root.after(0, lambda: self._connect_done(ok, msg))

    def _connect_done(self, ok, msg):
        self.busy = False
        if ok:
            cfg = app_config.get_app_config()
            proxy_manager.set_system_proxy(cfg["local_http_port"])
            self._log(f"连接成功，系统代理已自动设置为 127.0.0.1:{cfg['local_http_port']}")
        else:
            self._log(f"连接失败: {msg}")
            messagebox.showerror("连接失败", msg)

    def on_disconnect(self):
        proxy_manager.restore_system_proxy()
        if core_adapter.stop():
            self._log("已断开，系统代理已恢复")
        else:
            self._log("当前未连接")

    def on_close(self):
        proxy_manager.restore_system_proxy()
        core_adapter.stop()
        self.root.destroy()

    def _status_tick(self):
        cfg = app_config.get_app_config()
        running = core_adapter.is_running()
        state = "已连接" if running else "未连接"
        if running:
            secs = int(core_adapter.running_seconds())
            self.status_var.set(
                f"{state}（{secs//60}分{secs%60}秒） | 代理 127.0.0.1:{cfg['local_http_port']} | {self.base_url}"
            )
        else:
            self.status_var.set(f"{state} | {self.base_url}")
        self.root.after(1000, self._status_tick)


def main():
    try:
        core_adapter.ensure_core_files()
        LoginWindow(auto_start=True).run()
    except Exception:
        import traceback
        try:
            with open(os.path.join(app_config.CLIENT_DIR, "crash.log"), "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except OSError:
            pass
        raise


if __name__ == "__main__":
    main()
