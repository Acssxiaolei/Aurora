# -*- coding: utf-8 -*-
"""Xray 内核适配器：根据节点模型生成 Xray 配置，并管理内核子进程。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional

import app_config
from app_config import XRAY_CONFIG_FILE, XRAY_LOG_FILE

_CREATE_NO_WINDOW = 0x08000000

_process: Optional[subprocess.Popen] = None
_proc_lock = threading.RLock()
_start_time: float = 0.0
_last_error: str = ""


def _build_stream_settings(node: Dict[str, Any]) -> Dict[str, Any]:
    network = node.get("network") or "tcp"
    tls_enabled = bool(node.get("tls"))
    security = node.get("security") or ("tls" if tls_enabled else "none")
    if security in ("tls", "reality"):
        pass
    elif security in ("none", "", None, "auto", "aes-128-gcm", "chacha20-poly1305"):
        security = "none" if security in ("none", "", None) else security
    if node.get("protocol") == "vmess" and security not in ("tls", "reality"):
        tls_enabled = bool(node.get("tls"))
        security = "tls" if tls_enabled else "none"

    stream: Dict[str, Any] = {"network": network}

    tls_cfg: Dict[str, Any] = {}
    if node.get("sni"):
        tls_cfg["serverName"] = node["sni"]
    if node.get("fp"):
        tls_cfg["fingerprint"] = node["fp"]
    if node.get("alpn"):
        tls_cfg["alpn"] = [a.strip() for a in str(node["alpn"]).split(",") if a.strip()]

    if security == "reality":
        stream["security"] = "reality"
        reality_cfg = dict(tls_cfg)
        if node.get("pbk"):
            reality_cfg["publicKey"] = node["pbk"]
        if node.get("sid"):
            reality_cfg["shortId"] = node["sid"]
        if node.get("spx"):
            reality_cfg["spiderX"] = node["spx"]
        stream["realitySettings"] = reality_cfg
    elif security == "tls":
        stream["security"] = "tls"
        if tls_cfg:
            stream["tlsSettings"] = tls_cfg
    else:
        stream["security"] = "none"

    if network == "ws":
        ws_cfg: Dict[str, Any] = {}
        if node.get("path"):
            ws_cfg["path"] = node["path"]
        host = node.get("host")
        if host:
            ws_cfg["headers"] = {"Host": host}
        stream["wsSettings"] = ws_cfg
    elif network in ("h2", "http"):
        http_cfg: Dict[str, Any] = {}
        if node.get("host"):
            http_cfg["host"] = [node["host"]]
        if node.get("path"):
            http_cfg["path"] = node["path"]
        stream["httpSettings"] = http_cfg
    elif network == "grpc":
        grpc_cfg: Dict[str, Any] = {}
        if node.get("path"):
            grpc_cfg["serviceName"] = node["path"].lstrip("/")
        stream["grpcSettings"] = grpc_cfg
    elif network == "tcp":
        header_type = node.get("type") or "none"
        if header_type and header_type != "none":
            stream["tcpSettings"] = {"header": {"type": header_type}}
    return stream


def build_outbound(node: Dict[str, Any]) -> Dict[str, Any]:
    proto = node.get("protocol")
    addr = node.get("server")
    port = int(node.get("port") or 0)
    out: Dict[str, Any] = {"tag": "proxy", "protocol": proto}

    if proto == "vmess":
        out["settings"] = {
            "vnext": [{
                "address": addr,
                "port": port,
                "users": [{
                    "id": node.get("id"),
                    "alterId": int(node.get("aid") or 0),
                    "security": node.get("security") or "auto",
                }],
            }]
        }
    elif proto == "vless":
        user: Dict[str, Any] = {"id": node.get("id"), "encryption": "none"}
        if node.get("flow"):
            user["flow"] = node["flow"]
        out["settings"] = {
            "vnext": [{"address": addr, "port": port, "users": [user]}]
        }
    elif proto == "trojan":
        server: Dict[str, Any] = {"address": addr, "port": port, "password": node.get("password")}
        if node.get("flow"):
            server["flow"] = node["flow"]
        out["settings"] = {"servers": [server]}
    elif proto == "shadowsocks":
        ss_server: Dict[str, Any] = {
            "address": addr,
            "port": port,
            "method": node.get("method"),
            "password": node.get("password"),
            "uot": True,
        }
        plugin = node.get("plugin")
        if plugin:
            parts = plugin.split(";")
            ss_server["plugin"] = parts[0].strip()
            rest = ";".join(parts[1:]).strip()
            if rest:
                ss_server["pluginOpts"] = rest
        out["settings"] = {"servers": [ss_server]}
    else:
        raise ValueError(f"不支持的协议: {proto}")

    out["streamSettings"] = _build_stream_settings(node)
    return out


def build_config(node: Dict[str, Any], socks_port: int, http_port: int) -> Dict[str, Any]:
    return {
        "log": {
            "loglevel": "warning",
            "access": "none",
            "error": XRAY_LOG_FILE,
        },
        "inbounds": [
            {
                "tag": "socks-in",
                "listen": "127.0.0.1",
                "port": socks_port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True},
            },
            {
                "tag": "http-in",
                "listen": "127.0.0.1",
                "port": http_port,
                "protocol": "http",
                "settings": {},
            },
        ],
        "outbounds": [
            build_outbound(node),
            {"tag": "direct", "protocol": "freedom"},
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [
                {"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"},
                {"type": "field", "network": "tcp,udp", "outboundTag": "proxy"},
            ],
        },
    }


def ensure_core_files() -> None:
    if not getattr(sys, "frozen", False):
        return
    dst_dir = os.path.join(app_config.CLIENT_DIR, "core", "xray")
    os.makedirs(dst_dir, exist_ok=True)
    for name in ("xray.exe", "geoip.dat", "geosite.dat", "wintun.dll"):
        src = os.path.join(getattr(sys, "_MEIPASS", ""), name)
        dst = os.path.join(dst_dir, name)
        if os.path.isfile(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass


def resolve_core_path() -> Optional[str]:
    ensure_core_files()
    cfg = app_config.get_app_config()
    rel = cfg.get("core_path") or "core/xray/xray.exe"
    p = os.path.join(app_config.CLIENT_DIR, rel)
    return p if os.path.isfile(p) else None


def validate_config(config: Dict[str, Any]) -> bool:
    core = resolve_core_path()
    if core is None:
        return False
    with open(XRAY_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    r = subprocess.run(
        [core, "-test", "-c", XRAY_CONFIG_FILE],
        capture_output=True, text=True, timeout=30,
        creationflags=_CREATE_NO_WINDOW,
    )
    return r.returncode == 0


def start(node: Dict[str, Any]) -> tuple[bool, str]:
    global _process, _start_time, _last_error
    with _proc_lock:
        if _process is not None and _process.poll() is None:
            return False, "内核已在运行"
        core = resolve_core_path()
        if core is None:
            return False, f"未找到内核文件，请确认 {app_config.get_app_config().get('core_path')} 存在"
        cfg = app_config.get_app_config()
        config = build_config(node, int(cfg["local_socks_port"]), int(cfg["local_http_port"]))
        ok = validate_config(config)
        if not ok:
            return False, "内核配置校验失败，请检查节点参数是否完整"
        try:
            log_f = open(XRAY_LOG_FILE, "w", encoding="utf-8", errors="replace")
            _process = subprocess.Popen(
                [core, "run", "-c", XRAY_CONFIG_FILE],
                stdout=log_f,
                stderr=subprocess.STDOUT,
                creationflags=_CREATE_NO_WINDOW,
                cwd=app_config.CLIENT_DIR,
            )
            _start_time = time.time()
            _last_error = ""
            time.sleep(0.5)
            if _process.poll() is not None:
                return False, f"内核启动后立即退出（退出码 {_process.returncode}），请查看日志"
            return True, "内核已启动"
        except OSError as e:
            _last_error = str(e)
            return False, f"启动内核失败: {e}"


def stop() -> bool:
    global _process, _start_time
    with _proc_lock:
        if _process is None:
            return False
        if _process.poll() is None:
            try:
                _process.terminate()
                try:
                    _process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    _process.kill()
                    _process.wait(timeout=5)
            except Exception:
                pass
        _process = None
        _start_time = 0.0
        return True


def is_running() -> bool:
    with _proc_lock:
        return _process is not None and _process.poll() is None


def running_seconds() -> float:
    with _proc_lock:
        alive = _process is not None and _process.poll() is None
        return (time.time() - _start_time) if alive else 0.0


def get_last_log(lines: int = 20) -> str:
    if not os.path.exists(XRAY_LOG_FILE):
        return "(无日志)"
    try:
        with open(XRAY_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:])
    except OSError:
        return "(日志读取失败)"
