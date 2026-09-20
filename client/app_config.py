# -*- coding: utf-8 -*-
"""本地配置读写模块：纯 JSON 文件，不依赖任何数据库。

配置目录结构：
  config/
    app.json    应用设置（本地端口、选中节点、内核路径等）
    nodes.json  节点列表（由代理链接解析而来）
    xray-config.json  当前生成的 Xray 内核配置（运行时生成）
"""
from __future__ import annotations

import json
import os
import sys
import threading
from typing import Any, Dict, List, Optional

if getattr(sys, "frozen", False):
    CLIENT_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    CLIENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(CLIENT_DIR, "config")

APP_FILE = os.path.join(CONFIG_DIR, "app.json")
NODES_FILE = os.path.join(CONFIG_DIR, "nodes.json")
XRAY_CONFIG_FILE = os.path.join(CONFIG_DIR, "xray-config.json")
XRAY_LOG_FILE = os.path.join(CONFIG_DIR, "xray.log")

DEFAULT_APP: Dict[str, Any] = {
    "local_socks_port": 11080,
    "local_http_port": 11081,
    "selected_index": -1,
    "core_path": "core/xray/xray.exe",
    "base_url": "",
    "email": "",
    "panel_type": "sspanel",
    "password": "",
    "remember_password": False,
    "auto_login": False,
    "auto_startup": False,
}

_lock = threading.Lock()


def _ensure_config_dir() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_json(path: str, default: Any) -> Any:
    _ensure_config_dir()
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: str, data: Any) -> None:
    _ensure_config_dir()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def get_app_config() -> Dict[str, Any]:
    with _lock:
        cfg = load_json(APP_FILE, dict(DEFAULT_APP))
        merged = dict(DEFAULT_APP)
        merged.update(cfg or {})
        return merged


def save_app_config(cfg: Dict[str, Any]) -> None:
    with _lock:
        save_json(APP_FILE, cfg)


def load_nodes() -> List[Dict[str, Any]]:
    with _lock:
        nodes = load_json(NODES_FILE, [])
        return nodes if isinstance(nodes, list) else []


def save_nodes(nodes: List[Dict[str, Any]]) -> None:
    with _lock:
        save_json(NODES_FILE, nodes)


def add_node(node: Dict[str, Any]) -> int:
    nodes = load_nodes()
    key = (node.get("protocol"), node.get("server"), node.get("port"))
    for i, n in enumerate(nodes):
        if (n.get("protocol"), n.get("server"), n.get("port")) == key:
            return i
    nodes.append(node)
    save_nodes(nodes)
    return len(nodes) - 1


def remove_node(index: int) -> None:
    nodes = load_nodes()
    if 0 <= index < len(nodes):
        nodes.pop(index)
        save_nodes(nodes)
