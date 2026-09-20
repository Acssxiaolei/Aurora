# -*- coding: utf-8 -*-
"""代理链接解析器：把 vmess:// vless:// trojan:// ss:// 链接解析为统一节点模型。

统一节点模型（dict）字段：
  protocol  : vmess | vless | trojan | shadowsocks
  name      : 节点备注名
  server    : 服务器地址
  port      : 服务器端口(int)
  id        : vmess/vless 的 UUID
  password  : trojan/ss 的密码
  method    : ss 的加密方式
  security  : 加密方式(vmess) / 传输安全(tls|reality|none)
  network   : tcp | ws | grpc | h2 ...
  tls       : 是否启用 TLS
  sni       : TLS SNI
  host      : ws/h2 的 Host
  path      : ws/h2/grpc 的路径
  alpn      : ALPN
  fp        : 指纹
  flow      : 流控（如 xtls-rprx-vision）
  type      : tcp 伪装类型（none/http）
  plugin    : ss 插件
  raw       : 原始链接
"""
from __future__ import annotations

import base64
import json
import urllib.parse
from typing import Any, Dict, Optional


def _b64decode(data: str) -> bytes:
    """宽松 base64 解码：兼容标准/URL-Safe、自动补 padding。"""
    s = data.strip()
    s = s.replace("-", "+").replace("_", "/")
    pad = len(s) % 4
    if pad:
        s += "=" * (4 - pad)
    return base64.b64decode(s)


def _b64decode_str(data: str) -> str:
    return _b64decode(data).decode("utf-8", errors="replace")


def detect_link_type(link: str) -> Optional[str]:
    """识别链接类型，无法识别返回 None。"""
    for prefix in ("vmess://", "vless://", "trojan://", "ss://", "ssr://"):
        if link.strip().lower().startswith(prefix):
            return prefix[:-3]
    return None


def parse_link(link: str) -> Optional[Dict[str, Any]]:
    """解析单条链接，失败返回 None。"""
    link = link.strip()
    low = link.lower()
    try:
        if low.startswith("vmess://"):
            return _parse_vmess(link)
        if low.startswith("vless://"):
            return _parse_vless(link)
        if low.startswith("trojan://"):
            return _parse_trojan(link)
        if low.startswith("ss://"):
            return _parse_ss(link)
    except Exception:
        return None
    return None


# ---------------- vmess ----------------

def _parse_vmess(link: str) -> Dict[str, Any]:
    payload = link[len("vmess://"):]
    try:
        raw = _b64decode_str(payload)
        cfg = json.loads(raw)
        if isinstance(cfg, dict) and "add" in cfg:
            return _normalize_vmess_json(cfg, link)
    except Exception:
        pass
    try:
        inner = _b64decode_str(payload)
        raw = _b64decode_str(inner)
        cfg = json.loads(raw)
        if isinstance(cfg, dict) and "add" in cfg:
            return _normalize_vmess_json(cfg, link)
    except Exception:
        pass
    raise ValueError("无法解析 vmess 链接")


def _normalize_vmess_json(cfg: Dict[str, Any], raw_link: str) -> Dict[str, Any]:
    def g(*keys, default=""):
        for k in keys:
            if k in cfg and cfg[k]:
                return cfg[k]
        return default

    node: Dict[str, Any] = {
        "protocol": "vmess",
        "name": g("ps", "remark", default="未命名节点") or "未命名节点",
        "server": g("add", "address"),
        "port": int(g("port", default=0) or 0),
        "id": g("id"),
        "security": g("scy", "security", default="auto") or "auto",
        "network": g("net", "network", default="tcp") or "tcp",
        "tls": g("tls", default="none") not in ("none", "", "0", "false"),
        "sni": g("sni", "host"),
        "host": g("host"),
        "path": g("path"),
        "alpn": g("alpn"),
        "fp": g("fp", "fingerprint"),
        "type": g("type", default="none") or "none",
        "aid": int(g("aid", "alterId", default="0") or 0),
        "raw": raw_link,
    }
    if not node["server"] or not node["port"] or not node["id"]:
        raise ValueError("vmess 链接缺少必要字段")
    return node


# ---------------- vless ----------------

def _parse_vless(link: str) -> Dict[str, Any]:
    u = urllib.parse.urlparse(link)
    if u.scheme != "vless":
        raise ValueError("非 vless 链接")
    node: Dict[str, Any] = {
        "protocol": "vless",
        "name": urllib.parse.unquote(u.fragment or "") or "未命名节点",
        "server": u.hostname or "",
        "port": u.port or 0,
        "id": u.username or "",
        "raw": link,
    }
    q = urllib.parse.parse_qs(u.query)
    def gv(key):
        return q.get(key, [""])[0]

    node["security"] = gv("security") or "none"
    node["network"] = gv("type") or "tcp"
    node["tls"] = node["security"] in ("tls", "reality")
    node["sni"] = gv("sni") or (gv("host") if node["security"] in ("tls", "reality") else "")
    node["host"] = gv("host")
    node["path"] = gv("path")
    node["alpn"] = gv("alpn")
    node["fp"] = gv("fp")
    node["flow"] = gv("flow")
    node["type"] = gv("headerType") or "none"
    node["pbk"] = gv("pbk")
    node["sid"] = gv("sid")
    node["spx"] = gv("spx")
    if not node["server"] or not node["port"] or not node["id"]:
        raise ValueError("vless 链接缺少必要字段")
    return node


# ---------------- trojan ----------------

def _parse_trojan(link: str) -> Dict[str, Any]:
    u = urllib.parse.urlparse(link)
    if u.scheme != "trojan":
        raise ValueError("非 trojan 链接")
    node: Dict[str, Any] = {
        "protocol": "trojan",
        "name": urllib.parse.unquote(u.fragment or "") or "未命名节点",
        "server": u.hostname or "",
        "port": u.port or 0,
        "password": urllib.parse.unquote(u.username or ""),
        "raw": link,
    }
    q = urllib.parse.parse_qs(u.query)
    def gv(key):
        return q.get(key, [""])[0]

    node["security"] = gv("security") or "tls"
    node["network"] = gv("type") or "tcp"
    node["tls"] = node["security"] in ("tls", "reality")
    node["sni"] = gv("sni") or gv("host")
    node["host"] = gv("host")
    node["path"] = gv("path")
    node["alpn"] = gv("alpn")
    node["fp"] = gv("fp")
    node["flow"] = gv("flow")
    node["type"] = gv("headerType") or "none"
    if not node["server"] or not node["port"] or not node["password"]:
        raise ValueError("trojan 链接缺少必要字段")
    return node


# ---------------- shadowsocks ----------------

def _parse_ss(link: str) -> Dict[str, Any]:
    payload = link[len("ss://"):]
    if "@" in payload and "?" not in payload.split("@")[0]:
        head, tail = payload.split("@", 1)
        method_pass = ""
        try:
            decoded = _b64decode_str(head)
            if ":" in decoded:
                method_pass = decoded
        except Exception:
            if ":" in head:
                method_pass = head
        if not method_pass:
            raise ValueError("ss 链接缺少凭据")
        method, password = method_pass.split(":", 1)
        u = urllib.parse.urlparse("ss://" + tail)
        node: Dict[str, Any] = {
            "protocol": "shadowsocks",
            "name": urllib.parse.unquote(u.fragment or "") or "未命名节点",
            "server": u.hostname or "",
            "port": u.port or 0,
            "method": method,
            "password": urllib.parse.unquote(password),
            "network": "tcp",
            "tls": False,
            "raw": link,
        }
        q = urllib.parse.parse_qs(u.query)
        if "plugin" in q:
            node["plugin"] = q["plugin"][0]
    else:
        try:
            decoded = _b64decode_str(payload.split("#")[0])
            u = urllib.parse.urlparse("ss://" + decoded)
            node = {
                "protocol": "shadowsocks",
                "name": urllib.parse.unquote(payload.split("#")[1]) if "#" in payload else "未命名节点",
                "server": u.hostname or "",
                "port": u.port or 0,
                "method": u.username or "",
                "password": urllib.parse.unquote(u.password or ""),
                "network": "tcp",
                "tls": False,
                "raw": link,
            }
        except Exception:
            raise ValueError("无法解析 ss 链接")
    if not node["server"] or not node["port"] or not node["method"] or not node["password"]:
        raise ValueError("ss 链接缺少必要字段")
    return node


# ---------------- 批量 ----------------

def parse_many(text):
    """从多行文本（或链接列表）中解析出所有节点，返回 (节点列表, 失败行列表)。"""
    if isinstance(text, (list, tuple)):
        lines = list(text)
    else:
        lines = text.splitlines()
    nodes: list = []
    failed: list = []
    for line in lines:
        line = (line or "").strip()
        if not line:
            continue
        if line.startswith(("#", "//")):
            continue
        node = parse_link(line)
        if node is not None:
            nodes.append(node)
        else:
            failed.append(line)
    return nodes, failed
