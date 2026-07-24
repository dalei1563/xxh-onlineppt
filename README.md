# GSP 学习会在线演示系统 v3

线下学习会 PPT 的在线化演示系统，聚焦在线播放、远程控制、素材管理和实时同步。
AI 实时语音对话已拆分为独立服务，通过通用 iframe 幻灯片接入。

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 PPT 核心
python main.py

# 另开一个终端启动独立 AI 语音服务
python ai_voice_service/main.py

# Windows 也可以一次启动两个独立进程
powershell -ExecutionPolicy Bypass -File .\start_services.ps1
```

| 页面 | 地址 |
|------|------|
| 演示 | http://localhost:8000/slides.html |
| 控制台 | http://localhost:8000/controller.html |
| 编辑器 | http://localhost:8000/editor.html |
| AI 语音服务 | http://localhost:8100/ |

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
- **外部服务页**：通过受控 iframe 接入独立服务；按需加载，离开幻灯片后释放页面和连接。
- **拖拽排序**：编辑器中拖拽卡片调整顺序，保存后演示页和控制台立即按新顺序展示。
- **实时同步**：基于 WebSocket 的统一协议，翻页、插入、删除、排序即时同步到所有客户端。
- **远程控制**：同局域网下手机/电脑打开控制台即可遥控翻页、按章节跳转和发起 TTS 播报。
- **AI 服务解耦**：语音对话拥有独立进程、WebSocket、配置和静态资源，不访问 PPT 数据库。

## 项目结构

```
├── main.py                  # FastAPI 入口
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量示例
├── ai/                      # 核心可选 TTS 播报
├── ai_voice_service/        # 独立 AI 实时语音服务
├── api/                     # REST API 路由
├── db/                      # 数据库模型与连接
├── editor/                  # 幻灯片模板定义
├── services/                # 幻灯片与缩略图业务服务
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
- AI 语音服务：独立 FastAPI + 智谱 GLM-Realtime
- 前端：原生 HTML/CSS/JavaScript + SortableJS

## 环境变量

复制 `.env.example` 为 `.env`，并按需填写：

```bash
# 核心可选 TTS 配置
ZHIPU_API_KEY=your_zhipu_api_key_here
ZHIPU_TTS_MODEL=glm-4-voice

# PPT 内置 AI 幻灯片指向的独立服务
AI_VOICE_SERVICE_URL=http://127.0.0.1:8100/

# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
# 现场运行保持 false；仅开发调试时设为 true
SERVER_RELOAD=false

# 可选：将运行时数据库放在项目目录之外，便于备份或部署持久化卷
GSP_DB_PATH=/path/to/gsp_scores.db

# 可选：单个图片/视频上传上限。默认不限制；设为正整数时单位为字节
MAX_UPLOAD_SIZE_BYTES=0
```

AI 语音服务使用自己的 `ai_voice_service/.env`。完整配置见
`ai_voice_service/.env.example`，其中包括 GLM-Realtime 模型、声音和允许嵌入的
PPT 来源白名单。

完整的服务边界、协议、安全、部署和回滚说明见
[`docs/AI_VOICE_SERVICE_SPLIT.md`](docs/AI_VOICE_SERVICE_SPLIT.md)。

> 首次启动没有数据库时，系统会从 `editor/default_slides.py` 恢复受版本管理的默认活动课件。运行时的编辑结果保存在数据库中，请按活动需要备份该文件。

## 使用说明

### 1. 插入图片、视频或外部页面

1. 打开 `/editor.html`。
2. 点击顶部的插入图片、插入视频或插入外部页面按钮。
3. 选择要上传的文件，新页面会自动出现在末尾，并同步到演示页和控制台。

支持格式：
- 图片：jpg / png / gif / webp / bmp
- 视频：mp4 / webm / ogg / mov
- 外部页面：http / https URL

内置 AI 对话页在数据库中保存为 `service://ai-voice`，运行时通过
`AI_VOICE_SERVICE_URL` 解析。历史 `ai_chat` 记录会在启动时自动迁移。

### 2. 调整顺序

1. 在 `/editor.html` 中拖拽卡片到目标位置。
2. 点击顶部 `💾 保存排序`。
3. 演示页和控制台会立即按新顺序展示。

### 3. 删除幻灯片

点击卡片右下角的 `🗑` 删除按钮，删除后所有客户端同步更新。

## 后续扩展

核心实时功能扩展：
1. 在 `ws/protocol.py` 定义消息类型；
2. 在 `ws/handlers/` 添加处理器；
3. 在 `services/` 添加业务逻辑；
4. 在前端 `slide-store.js` 或页面脚本中订阅事件。

独立页面型功能优先使用 `external` 幻灯片，通过版本化 `postMessage` 协议接入，
避免把业务专用 WebSocket 和资源重新耦合进 PPT 核心。
