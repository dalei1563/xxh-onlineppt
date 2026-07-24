# AI 语音对话服务拆分方案

## 目标

PPT 核心只负责幻灯片数据、在线播放、编辑、缩略图、翻页和实时控制。
AI 语音对话作为独立服务运行，任何故障、升级或上游延迟都不能阻断 PPT 核心。

## 服务边界

### PPT 核心（8000）

- 管理幻灯片、章节、排序和素材。
- 提供演示页、控制台和编辑器。
- 维护演示 WebSocket 和现场权威状态。
- 提供通用 `external` 幻灯片。
- 不保存 AI 会话，不接收麦克风音频，不连接 GLM-Realtime。

### AI 语音服务（8100）

- 提供独立对话页面和静态资源。
- 请求并释放麦克风。
- 为每个浏览器连接维护独立 GLM-Realtime 会话。
- 持有 AI API Key。
- 不访问 PPT 数据库或核心 WebSocket。

控制台保留轻量的文字 TTS 播报；游戏与积分领域已从核心服务移除。

## 接入协议

双方使用版本化 `postMessage`：

```json
{
  "source": "xxh-presentation",
  "version": 1,
  "type": "presentation.enter",
  "payload": {
    "slideId": "s-ec889a11"
  }
}
```

核心到外部服务：

- `presentation.enter`
- `presentation.leave`
- `presentation.pause`
- `presentation.resume`
- `ai.sendText`

AI 服务到核心：

- `service.ready`

双方必须校验 `source`、`version`、`event.source` 和 `event.origin`。

## 生命周期

1. 演示页只加载当前幻灯片 iframe。
2. external 幻灯片包装页加载独立服务 iframe。
3. 加载完成后发送 `presentation.enter`。
4. 离开幻灯片时发送 `presentation.leave` 并销毁整个包装页。
5. AI 页面停止麦克风、音频、重连计时器和 WebSocket。
6. 服务端在 WebSocket 断开后关闭上游 GLM 会话。

## 数据迁移

- 历史 `type=ai_chat` 自动修改为 `type=external`。
- 历史 HTML 路径替换为 `service://ai-voice`。
- 运行时通过 `AI_VOICE_SERVICE_URL` 解析真实地址。
- 迁移幂等，已迁移数据不会重复修改。

## 安全

- AI API Key 只存在于独立服务后端。
- 外部 URL 只接受 `http` 和 `https`。
- iframe 使用最小 sandbox：`allow-scripts allow-same-origin allow-forms`。
- 麦克风和自动播放通过 iframe `allow` 显式授权。
- AI 服务通过 CSP `frame-ancestors` 限制可嵌入的 PPT 来源。
- AI WebSocket 只接受同源页面或显式配置的客户端来源。
- 独立服务开启 `nosniff`，并显式注册 JavaScript/CSS MIME。
- WebSocket 限制单条消息大小，后端再次校验音频分片和文本长度。

## 部署

开发机可以分别启动：

```powershell
python main.py
python ai_voice_service/main.py
```

或运行：

```powershell
.\start_services.ps1
```

生产环境应把两个目录构建为两个独立进程或容器，并配置：

- 核心：`AI_VOICE_SERVICE_URL`
- AI：`AI_VOICE_ALLOWED_PARENT_ORIGINS`
- AI：`ZHIPU_API_KEY`
- AI：`ZHIPU_REALTIME_MODEL`、`ZHIPU_REALTIME_VOICE`

如果通过 HTTPS 提供 PPT，AI 服务也必须使用 HTTPS，否则浏览器会阻止混合内容和麦克风。

## 监控与故障隔离

- `GET /health` 返回配置状态和当前活动会话数量。
- PPT 核心健康与 AI 服务健康相互独立。
- AI 服务离线时，只有 external AI 页不可用，其他幻灯片和控制操作保持正常。
- 离开 AI 页后 `active_sessions` 应回到 0。

## 回滚

1. 停止 AI 服务不会影响 PPT 核心。
2. 如需临时移除 AI 页，可在编辑器删除或移动对应 external 幻灯片。
3. 如需更换实现，只修改 `AI_VOICE_SERVICE_URL`，数据库中的
   `service://ai-voice` 和 PPT 代码无需变化。

## 验收结果

- 核心和 AI 服务可独立启动、停止。
- 核心不再注册任何 `ai_realtime_*` WebSocket 消息。
- 控制台不再包含 AI 对话页签或会话代码。
- AI 页面所有 JS、CSS、视频和背景资源由 8100 服务提供。
- 浏览器确认双层 iframe 正常加载，GLM-Realtime 会话可以进入 ready。
- 浏览器离开 AI 页后，服务端活动会话从 1 降为 0。
- 核心与 AI 服务自动化冒烟测试均通过。
