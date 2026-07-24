# AI Voice Service

从在线 PPT 核心中拆出的独立 GLM-Realtime 语音对话服务。它拥有独立页面、
WebSocket、静态资源和运行配置，不访问 PPT 数据库或演示状态。

## 启动

```bash
pip install -r ai_voice_service/requirements.txt
copy ai_voice_service/.env.example ai_voice_service/.env
python ai_voice_service/main.py
```

默认地址：

- 页面：`http://127.0.0.1:8100/`
- 健康检查：`http://127.0.0.1:8100/health`
- WebSocket：`ws://127.0.0.1:8100/ws`

开发环境中如果没有 `ai_voice_service/.env`，服务会兼容读取仓库根目录 `.env`。
独立部署时应使用服务目录自己的 `.env`。

## iframe 协议

父页面与服务之间使用 `postMessage`，消息固定包含：

```json
{
  "source": "xxh-presentation",
  "version": 1,
  "type": "presentation.enter",
  "payload": {}
}
```

PPT 可发送：

- `presentation.enter`
- `presentation.leave`
- `presentation.pause`
- `presentation.resume`
- `ai.sendText`

服务会发送：

- `service.ready`

服务仅接受来自 `document.referrer` 所在源的父页面消息；HTTP 响应还通过
`AI_VOICE_ALLOWED_PARENT_ORIGINS` 设置 CSP `frame-ancestors` 白名单。
