# GSP 2026年7月线下学习会 - AI主持演示系统

将线下学习会PPT转换为交互式网页，支持远程控制翻页。

## 快速启动

```bash
python ws_server.py
```

| 页面 | 地址 |
|------|------|
| 演示 | http://localhost:8080/slides.html |
| 控制 | http://localhost:8080/controller.html |

## 键盘快捷键

| 按键 | 功能 |
|------|------|
| `Ctrl` + `F1` | 显示/隐藏底部控制栏 |
| `→` / `Space` | 下一页 |
| `←` | 上一页 |
| `Home` | 首页 |
| `End` | 末页 |
| `F` | 全屏 |

## 远程控制

- 同局域网下手机/电脑打开控制页面即可遥控翻页
- 支持 Tailscale 等虚拟组网
- 多控制端自动同步

## 项目结构

```
├── ws_server.py        ← 启动入口（HTTP + WebSocket 一体服务器）
├── slides.html         ← 主演示页面（原生HTML）
├── controller.html     ← 远程控制页面（适配手机端）
└── intro_video.mp4     ← 开场视频
```

## 技术栈

纯前端 HTML/CSS/JavaScript + Python WebSocket/HTTP 服务器，零依赖。

## 后续规划

- AI语音播报
- 游戏互动（问答、投票、抽奖）
- 实时弹幕
