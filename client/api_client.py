# -*- coding: utf-8 -*-
"""SSPanel-Uim / V2Board / Xboard API 客户端。

支持三种面板：
  sspanel : 表单登录(Cookie) + /user 页面解析 + /sub/{token}/{subtype} 订阅
  v2board : RESTful API(JWT) + /api/v1/user/info + /api/v1/user/getSubscribe
  xboard  : 同 v2board（兼容接口）
"""
from __future__ import annotations

import base64
import re
import requests
from typing import Any, Dict


class SSPanelError(Exception):
    pass


def _norm_base_url(url: str) -> str:
    return url.rstrip("/")


# ==================== SSPanel ====================

def login_sspanel(base_url: str, email: str, password: str) -> requests.Session:
    base = _norm_base_url(base_url)
    s = requests.Session()
    s.headers.update({"User-Agent": "Aurora/2.0"})
    try:
        resp = s.post(f"{base}/auth/login",
                      data={"email": email, "password": password, "remember_me": "1"},
                      timeout=15, allow_redirects=True)
    except requests.RequestException as e:
        raise SSPanelError(f"网络请求失败: {e}")
    if resp.status_code != 200:
        raise SSPanelError(f"服务器返回 HTTP {resp.status_code}")
    body = resp.text
    if ("name=\"email\"" in body and "name=\"password\"" in body and "/user" not in resp.url):
        raise SSPanelError("邮箱或密码错误")
    return s


def get_user_info_sspanel(session: requests.Session, base_url: str) -> Dict[str, Any]:
    base = _norm_base_url(base_url)
    try:
        resp = session.get(f"{base}/user", timeout=15)
    except requests.RequestException as e:
        raise SSPanelError(f"获取用户信息失败: {e}")
    if resp.status_code != 200:
        raise SSPanelError(f"用户信息页 HTTP {resp.status_code}")
    html = resp.text
    info: Dict[str, Any] = {}
    m = re.search(r'<title>([^<]+)</title>', html)
    if m:
        info["nickname"] = m.group(1).strip()
    m = re.search(r'([\w.+-]+@[\w-]+\.[\w.]+)', html)
    if m:
        info["email"] = m.group(1)
    m = re.search(r'/sub/([A-Za-z0-9]{16,})/', html)
    if m:
        info["sub_token"] = m.group(1)
    m = re.search(r'(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)', html)
    if m:
        info["expire"] = m.group(1)
    m = re.search(r'([\d.]+\s*(?:GB|MB|TB))\s*/\s*([\d.]+\s*(?:GB|MB|TB))', html, re.IGNORECASE)
    if m:
        info["used_traffic"] = m.group(1).strip()
        info["total_traffic"] = m.group(2).strip()
    info["_panel"] = "sspanel"
    return info


def checkin_sspanel(session: requests.Session, base_url: str) -> str:
    base = _norm_base_url(base_url)
    try:
        resp = session.post(f"{base}/user/checkin", timeout=15)
    except requests.RequestException as e:
        raise SSPanelError(f"签到请求失败: {e}")
    try:
        j = resp.json()
        return j.get("msg") or j.get("message") or "签到成功"
    except ValueError:
        return "签到成功"


# ==================== V2Board / Xboard ====================

def login_v2board(base_url: str, email: str, password: str) -> requests.Session:
    base = _norm_base_url(base_url)
    s = requests.Session()
    s.headers.update({"User-Agent": "Aurora/2.0", "Content-Type": "application/json"})
    try:
        resp = s.post(f"{base}/api/v1/passport/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    except requests.RequestException as e:
        raise SSPanelError(f"网络请求失败: {e}")
    if resp.status_code != 200:
        raise SSPanelError(f"登录失败 HTTP {resp.status_code}")
    try:
        j = resp.json()
    except ValueError:
        raise SSPanelError("服务器返回非 JSON")
    if j.get("data") and j["data"].get("token"):
        s.headers.update({"Authorization": f"Bearer {j['data']['token']}"})
        return s
    raise SSPanelError(j.get("message") or "邮箱或密码错误")


def get_user_info_v2board(session: requests.Session, base_url: str) -> Dict[str, Any]:
    base = _norm_base_url(base_url)
    try:
        resp = session.get(f"{base}/api/v1/user/info", timeout=15)
    except requests.RequestException as e:
        raise SSPanelError(f"获取用户信息失败: {e}")
    if resp.status_code != 200:
        raise SSPanelError(f"用户信息 HTTP {resp.status_code}")
    j = resp.json().get("data", {})
    info: Dict[str, Any] = {
        "nickname": j.get("nickname") or j.get("username") or "",
        "email": j.get("email", ""),
        "balance": j.get("balance", 0),
        "_panel": "v2board",
    }
    transfer_enable = j.get("transfer_enable", 0)
    u = j.get("u", 0)
    d = j.get("d", 0)
    used = (u + d) / 1024 / 1024 / 1024
    total = transfer_enable / 1024 / 1024 / 1024
    if total > 0:
        info["used_traffic"] = f"{used:.1f} GB"
        info["total_traffic"] = f"{total:.1f} GB"
    expire = j.get("expired_at")
    if expire:
        import datetime
        info["expire"] = datetime.datetime.fromtimestamp(expire).strftime("%Y-%m-%d")
    try:
        sub_resp = session.get(f"{base}/api/v1/user/getSubscribe", timeout=15)
        sub_url = sub_resp.json().get("data", {}).get("subscribe_url", "")
        if sub_url:
            info["subscribe_url"] = sub_url
            m = re.search(r'token=([A-Za-z0-9]+)', sub_url)
            if m:
                info["sub_token"] = m.group(1)
    except Exception:
        pass
    return info


def checkin_v2board(session: requests.Session, base_url: str) -> str:
    base = _norm_base_url(base_url)
    try:
        resp = session.post(f"{base}/api/v1/user/checkin", timeout=15)
    except requests.RequestException as e:
        raise SSPanelError(f"签到请求失败: {e}")
    try:
        j = resp.json()
        return j.get("message") or j.get("data", {}).get("msg") or "签到成功"
    except ValueError:
        return "签到成功"


# ==================== 统一入口 ====================

def login(panel_type: str, base_url: str, email: str, password: str) -> requests.Session:
    if panel_type in ("v2board", "xboard"):
        return login_v2board(base_url, email, password)
    return login_sspanel(base_url, email, password)


def get_user_info(panel_type: str, session: requests.Session, base_url: str) -> Dict[str, Any]:
    if panel_type in ("v2board", "xboard"):
        return get_user_info_v2board(session, base_url)
    return get_user_info_sspanel(session, base_url)


def checkin(panel_type: str, session: requests.Session, base_url: str) -> str:
    if panel_type in ("v2board", "xboard"):
        return checkin_v2board(session, base_url)
    return checkin_sspanel(session, base_url)


def fetch_subscription(base_url: str, sub_token: str, subtype: str = "v2ray") -> str:
    base = _norm_base_url(base_url)
    try:
        resp = requests.get(f"{base}/sub/{sub_token}/{subtype}",
                            headers={"User-Agent": "Aurora/2.0"}, timeout=20)
    except requests.RequestException as e:
        raise SSPanelError(f"订阅请求失败: {e}")
    if resp.status_code != 200:
        raise SSPanelError(f"订阅 HTTP {resp.status_code}")
    text = resp.text.strip()
    try:
        decoded = base64.b64decode(text + "=" * (-len(text) % 4)).decode("utf-8", errors="replace")
        if "://" in decoded:
            return decoded
    except Exception:
        pass
    return text
