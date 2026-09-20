# Aurora

基于 **Xray-core** 的轻量级订阅管理型代理客户端，对接 SSPanel / V2Board / Xboard 面板。

> 原生 Windows 桌面应用（Python + tkinter），无需浏览器、无需 Web 界面，单文件 EXE 即用。

## 功能特性

- **账号密码登录**：对接 SSPanel-Uim / V2Board / Xboard 三类主流面板
- **自动订阅**：登录后自动拉取订阅地址、解析节点列表
- **多协议支持**：VMess / VLESS / Trojan / Shadowsocks，含 WebSocket / gRPC / Reality / XTLS-Vision
- **系统代理自动开关**：连接时自动设置 Windows 系统代理，断开/退出自动恢复
- **账号信息面板**：实时显示用户名、邮箱、余额、到期时间、剩余流量
- **一键签到**：支持 SSPanel / V2Board 签到接口
- **记住密码 & 自动登录**：勾选后下次打开直接登录
- **开机自启动**：设置里一键开关
- **纯本地配置**：所有数据存本地 JSON，不依赖数据库

## 下载

前往 [Releases](../../releases) 下载对应版本：

| 版本 | 文件名 | 适用系统 |
|------|--------|---------|
| **64位**（推荐） | `Aurora-x64.exe` | Windows 10 / 11 64位 |
| **32位** | `Aurora-x86.exe` | Windows 7 / 8 / 10 / 11 32位 |

> Windows SmartScreen 提示未知发布者时，点"更多信息"→"仍要运行"。

## 使用

1. 打开 Aurora
2. 选择面板类型（sspanel / v2board / xboard）
3. 填写面板地址（如 `https://your-panel.com`）
4. 输入邮箱和密码，点登录
5. 登录后自动拉取节点列表
6. 选中节点，点"连接所选节点"
7. 系统代理自动设置，浏览器直接上网

## 技术栈

- **Python 3.11** + **tkinter**（原生 GUI）
- **Xray-core v26.3**（代理内核）
- **requests**（HTTP API）
- **Pillow**（图标）
- **PyInstaller**（打包单文件 EXE）

## 项目结构

```
client/
├── main.py              # 主程序（登录窗 + 主窗）
├── api_client.py        # 面板 API 对接（sspanel/v2board/xboard）
├── link_parser.py       # 代理链接解析（vmess/vless/trojan/ss）
├── core_adapter.py       # Xray 内核配置生成与进程管理
├── proxy_manager.py      # Windows 系统代理自动开关
├── autostart.py         # 开机自启动注册表管理
├── app_config.py        # 本地 JSON 配置读写
├── aurora.png           # 应用图标
├── aurora.ico
└── core/xray/           # Xray 内核（通过 Release 分发，不在 repo 里）
```

## 开发

```bash
# 安装依赖
pip install requests pillow pyinstaller

# 从源码运行
cd client
python main.py

# 打包 64 位单文件 EXE（需自行下载 Xray-core 64位到 client/core/xray/）
pyinstaller --onefile --noconsole --name Aurora-x64 --icon aurora.ico \
  --add-data "core/xray/xray.exe;." \
  --add-data "core/xray/geoip.dat;." \
  --add-data "core/xray/geosite.dat;." \
  main.py

# 打包 32 位（兼容 Win7，需 Python 3.8 32位 + Xray 32位）
pyinstaller --onefile --noconsole --name Aurora-x86 --icon aurora.ico \
  --add-data "core/xray32/xray.exe;." \
  --add-data "core/xray32/geoip.dat;." \
  --add-data "core/xray32/geosite.dat;." \
  main.py
```

## 多平台支持

- [x] **Windows** — 当前版本（64位 + 32位）
- [ ] **Android** — 开发中，敬请期待
- [ ] **macOS** — 规划中
- [ ] **iOS** — 规划中

## 支持的面板

| 面板 | 登录方式 | 用户信息 | 签到 | 订阅 |
|------|---------|---------|------|------|
| SSPanel-Uim | 表单 + Cookie | /user 页面解析 | /user/checkin | /sub/{token}/v2ray |
| V2Board | JWT API | /api/v1/user/info | /api/v1/user/checkin | /api/v1/user/getSubscribe |
| Xboard | JWT API（同 V2Board） | 同上 | 同上 | 同上 |

## 系统兼容性

| 系统 | 64位版 | 32位版 |
|------|--------|--------|
| Windows 11 | ✅ | ✅ |
| Windows 10 | ✅ | ✅ |
| Windows 8 | ❌ | ✅ |
| Windows 7 | ❌ | ✅ |

## 协议

GPL-3.0 — 仅供学习研究使用，请勿用于非法用途。

## 致谢

- [Xray-core](https://github.com/XTLS/Xray-core) — 代理内核
- [SSPanel-Uim](https://github.com/Anankke/SSPanel-Uim) — 面板参考
- [V2Board](https://github.com/v2board/v2board) — API 参考
