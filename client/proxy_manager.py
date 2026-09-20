# -*- coding: utf-8 -*-
"""Windows 系统代理自动管理：连接成功开代理，断开/退出恢复默认。"""
from __future__ import annotations

import ctypes
import winreg

_INET_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
_INTERNET_OPTION_SETTINGS_CHANGED = 39
_INTERNET_OPTION_REFRESH = 37

_saved_enable: int | None = None
_saved_server: str | None = None


def _notify_refresh():
    try:
        internet_set_option = ctypes.windll.Wininet.InternetSetOptionW
        internet_set_option(0, _INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
        internet_set_option(0, _INTERNET_OPTION_REFRESH, 0, 0)
    except Exception:
        pass


def set_system_proxy(http_port: int, host: str = "127.0.0.1") -> None:
    global _saved_enable, _saved_server
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INET_KEY, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        if _saved_enable is None:
            try:
                _saved_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            except FileNotFoundError:
                _saved_enable = 0
            try:
                _saved_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            except FileNotFoundError:
                _saved_server = ""
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"{host}:{http_port}")
    _notify_refresh()


def restore_system_proxy() -> None:
    global _saved_enable, _saved_server
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INET_KEY, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        if _saved_enable is not None:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, int(_saved_enable))
        if _saved_server is not None:
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, _saved_server)
    _saved_enable = None
    _saved_server = None
    _notify_refresh()
