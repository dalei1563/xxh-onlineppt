# GSP 学习会 AI 主持演示系统 v3

线下学习会 PPT 的在线化演示系统，支持远程控制翻页、拖拽排序、插入全屏图片/视频页、实时游戏积分、AI 语音播报。

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py
```

| 页面 | 地址 |
|------|------|
| 演示 | http://localhost:8000/slides.html |
| 控制台 | http://localhost:8000/controller.html |
| 编辑器 | http://localhost:8000/editor.html |

## 键盘快捷键

| 按键 | 功能 |
|------|------|
| `Ctrl` + `F1` | 显示/隐藏底部控制栏 |
| `→` / `Space` | 下一页 |
| `←` / `Backspace` | 上一页 |
| `Home` | 首页 |
| `End` | 末页 |
| `F` | 全屏 |
| `Esc` | 视频页跳过视频 |

## 核心特性

- **单一数据源**：所有幻灯片存储在数据库，由服务端模板渲染，观众端、编辑器、控制台看到的内容完全一致。
- **插入图片/视频页**：在编辑器上传单张图片或单个视频，自动创建铺满全屏的素材页，并实时同步到所有客户端。
- **拖拽排序**：编辑器中拖拽卡片调整顺序，保存后演示页和控制台立即按新顺序展示。
- **实时同步**：基于 WebSocket 的统一协议，翻页、插入、删除、排序即时同步到所有客户端。
- **远程控制**：同局域网下手机/电脑打开控制台即可遥控翻页，支持积分管理、TTS 播报、AI 对话。

## 项目结构

```
├── main.py                  # FastAPI 入口
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量示例
├── ai/                      # AI 服务（TTS/ASR/LLM）
├── api/                     # REST API 路由
├── db/                      # 数据库模型与连接
├── editor/                  # 幻灯片模板定义
├── game/                    # 游戏/积分 Pydantic 模型
├── services/                # 业务服务层（幻灯片、积分）
├── state/                   # 运行时权威状态
├── static/                  # 前端静态资源
│   ├── slides.html          # 主演示页
│   ├── controller.html      # 控制台
│   ├── editor.html          # 幻灯片编辑器（拖拽排序 + 上传图片/视频页）
│   ├── css/slides.css       # 幻灯片共享样式
│   └── js/                  # 前端共享 JS 模块
│       ├── ws-client.js     # WebSocket 连接管理
│       └── slide-store.js   # 幻灯片状态存储
├── test_smoke.py            # 端到端冒烟测试
├── ws/                      # WebSocket 协议与处理器
│   ├── handler.py           # 连接管理
│   ├── protocol.py          # 消息 schema
│   ├── router.py            # 消息路由
│   └── handlers/            # 各领域处理器
└── data/                    # SQLite 数据库（运行时生成）
```

## 技术栈

- 后端：FastAPI + SQLAlchemy + SQLite + WebSocket
- AI：智谱 GLM API（TTS、ASR、LLM）
- 前端：原生 HTML/CSS/JavaScript + SortableJS

## 环境变量

复制 `.env.example` 为 `.env`，并按需填写：

```bash
# 智谱 API 配置
ZHIPU_API_KEY=your_zhipu_api_key_here
ZHIPU_TTS_MODEL=glm-4-voice
ZHIPU_LLM_MODEL=glm-4-7b
ZHIPU_ASR_MODEL=glm-asr-2512

# GLM-Realtime（AI 幻灯片的实时语音对话）
ZHIPU_REALTIME_MODEL=glm-realtime-flash
ZHIPU_REALTIME_VOICE=tongtong

# 代理配置（可选，用于调用智谱 API）
AI_PROXY=http://your_proxy:port

# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
# 现场运行保持 false；仅开发调试时设为 true
SERVER_RELOAD=false

# 可选：将运行时数据库放在项目目录之外，便于备份或部署持久化卷
GSP_DB_PATH=/path/to/gsp_scores.db

# 可选：单个图片/视频上传上限，默认 100 MB
MAX_UPLOAD_SIZE_BYTES=104857600
```

> 首次启动没有数据库时，系统会从 `editor/default_slides.py` 恢复受版本管理的默认活动课件。运行时的积分和编辑结果仍保存在数据库中，请按活动需要备份该文件。

## 使用说明

### 1. 插入图片/视频页

1. 打开 `/editor.html`。
2. 点击顶部 `🖼️ 插入图片页` 或 `🎬 插入视频页`。
3. 选择要上传的文件，新页面会自动出现在末尾，并同步到演示页和控制台。

支持格式：
- 图片：jpg / png / gif / webp / bmp
- 视频：mp4 / webm / ogg / mov

### 2. 调整顺序

1. 在 `/editor.html` 中拖拽卡片到目标位置。
2. 点击顶部 `💾 保存排序`。
3. 演示页和控制台会立即按新顺序展示。

### 3. 删除幻灯片

点击卡片右下角的 `🗑` 删除按钮，删除后所有客户端同步更新。

## 后续扩展

新增功能只需：
1. 在 `ws/protocol.py` 定义消息类型；
2. 在 `ws/handlers/` 添加处理器；
3. 在 `services/` 添加业务逻辑；
4. 在前端 `slide-store.js` 或页面脚本中订阅事件。
