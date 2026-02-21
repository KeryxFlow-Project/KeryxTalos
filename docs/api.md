# KeryxFlow API Reference

REST API, WebSocket, and webhook reference for external integrations, monitoring dashboards, and programmatic control.

## Server Configuration

The API server is configured via `ApiSettings` with the `KERYXFLOW_API_` environment variable prefix.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `host` | `str` | `127.0.0.1` | Bind address |
| `port` | `int` | `8080` | Listen port |
| `token` | `str` | `""` | Bearer auth token (empty = no auth) |
| `cors_origins` | `list[str]` | `["*"]` | Allowed CORS origins |
| `webhook_secret` | `str` | `""` | Webhook secret header (empty = no auth) |

```bash
KERYXFLOW_API_HOST=0.0.0.0
KERYXFLOW_API_PORT=8080
KERYXFLOW_API_TOKEN=my-secret-token
KERYXFLOW_API_CORS_ORIGINS=["http://localhost:3000"]
KERYXFLOW_API_WEBHOOK_SECRET=my-webhook-secret
```

## Starting the Server

The API server starts automatically when the `TradingEngine` is launched. To start standalone:

```python
from keryxflow.api import create_app
import uvicorn

app = create_app()
uvicorn.run(app, host="127.0.0.1", port=8080)
```

Or via CLI:

```bash
poetry run keryxflow --api-only
```

---

## Authentication

### Bearer Token (REST)

Include the token in the `Authorization` header:

```
Authorization: Bearer <token>
```

If `KERYXFLOW_API_TOKEN` is empty (the default), authentication is skipped and all endpoints are publicly accessible.

### WebSocket Token

Pass the token as a query parameter:

```
ws://127.0.0.1:8080/ws/events?token=my-secret-token
```

### Webhook Secret

Webhook endpoints use a separate secret via the `X-Webhook-Secret` header:

```
X-Webhook-Secret: my-webhook-secret
```

---

## REST Endpoints

All REST endpoints are under the `/api` prefix and require bearer token auth (if configured).

### GET /api/status

Returns the current risk manager and trading session status.

**curl:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/status
```

**Python:**
```python
import requests

r = requests.get("http://localhost:8080/api/status",
                  headers={"Authorization": f"Bearer {TOKEN}"})
print(r.json())
```

**Response:**
```json
{
  "risk": {
    "circuit_breaker": false,
    "daily_pnl_pct": -0.5,
    "open_positions": 1,
    "max_open_positions": 3
  },
  "session": {
    "state": "RUNNING",
    "uptime_seconds": 3600,
    "is_paused": false
  }
}
```

---

### GET /api/positions

Returns all open positions with unrealized PnL.

**curl:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/positions
```

**Response:**
```json
[
  {
    "id": "pos-abc123",
    "symbol": "BTC/USDT",
    "side": "buy",
    "quantity": 0.01,
    "entry_price": 67000.0,
    "current_price": 67500.0,
    "unrealized_pnl": 5.0,
    "unrealized_pnl_percentage": 0.75,
    "stop_loss": 66000.0,
    "take_profit": 69000.0,
    "opened_at": "2026-02-19T10:00:00Z"
  }
]
```

---

### GET /api/trades

Returns the 50 most recent trades.

**curl:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/trades
```

**Response:**
```json
[
  {
    "id": "trade-abc123",
    "symbol": "BTC/USDT",
    "side": "buy",
    "quantity": 0.01,
    "entry_price": 67000.0,
    "exit_price": 67500.0,
    "stop_loss": 66000.0,
    "take_profit": 69000.0,
    "pnl": 5.0,
    "pnl_percentage": 0.75,
    "status": "closed",
    "is_paper": true,
    "created_at": "2026-02-19T10:00:00Z",
    "closed_at": "2026-02-19T12:30:00Z"
  }
]
```

---

### GET /api/balance

Returns the portfolio balance.

**curl:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/balance
```

**Response:**
```json
{
  "total": 10000.0,
  "free": 8000.0,
  "used": 2000.0
}
```

---

### GET /api/agent/status

Returns the cognitive agent session state and statistics.

**curl:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/agent/status
```

**Response:**
```json
{
  "state": "RUNNING",
  "cycles_completed": 42,
  "success_rate": 0.95,
  "total_trades": 10,
  "win_rate": 0.6,
  "pnl": 150.0,
  "tool_calls": 320,
  "tokens_used": 125000
}
```

---

### POST /api/panic

Triggers an emergency stop: closes all open positions and pauses trading. No request body required.

**curl:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/panic
```

**Response:**
```json
{
  "status": "panic_triggered"
}
```

---

### POST /api/pause

Toggles pause/resume for trading. If active, pauses. If paused, resumes. No request body required.

**curl:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/pause
```

**Response (paused):**
```json
{
  "status": "paused"
}
```

**Response (resumed):**
```json
{
  "status": "resumed"
}
```

---

## WebSocket

### WS /ws/events

Streams all EventBus events as JSON in real-time. Connect with any WebSocket client.

**Connection:**
```
ws://127.0.0.1:8080/ws/events
ws://127.0.0.1:8080/ws/events?token=my-secret-token
```

**Python client:**
```python
import asyncio
import json
import websockets

async def monitor():
    async with websockets.connect("ws://localhost:8080/ws/events") as ws:
        async for message in ws:
            event = json.loads(message)
            print(f"[{event['type']}] {event['data']}")

asyncio.run(monitor())
```

**Event JSON format:**
```json
{
  "type": "price_update",
  "timestamp": "2026-02-19T10:00:00.123456Z",
  "data": {
    "symbol": "BTC/USDT",
    "price": 67500.0
  }
}
```

The WebSocket streams all event types from the system EventBus. See `keryxflow/core/events.py` for the full list of `EventType` values.

---

## Webhook Endpoint

### POST /api/webhook/signal

Receives trading signals from external sources (TradingView, custom scripts, etc.) and publishes them to the event bus. Authentication uses the `X-Webhook-Secret` header.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | `string` | Yes | Trading pair (e.g. `BTC/USDT`) |
| `side` | `"buy"` or `"sell"` | Yes | Trade direction |
| `price` | `float` | No | Signal price |
| `quantity` | `float` | No | Trade quantity |
| `source` | `string` | No | Source identifier (default: `tradingview`) |
| `strategy` | `string` | No | Strategy name |

**curl:**
```bash
curl -X POST http://localhost:8080/api/webhook/signal \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: my-webhook-secret" \
  -d '{"symbol": "BTC/USDT", "side": "buy", "price": 67000.0, "source": "tradingview"}'
```

**Python:**
```python
import requests

r = requests.post("http://localhost:8080/api/webhook/signal",
    headers={"X-Webhook-Secret": "my-webhook-secret"},
    json={"symbol": "BTC/USDT", "side": "buy", "price": 67000.0})
print(r.json())
```

**Response:**
```json
{
  "status": "received",
  "symbol": "BTC/USDT",
  "side": "buy"
}
```

### TradingView Integration

To send TradingView alerts to KeryxFlow:

1. Set up the webhook endpoint with a public URL (use ngrok for local testing)
2. In TradingView, create an alert and set the webhook URL to `https://your-host/api/webhook/signal`
3. Set the alert message body to JSON:

```json
{
  "symbol": "{{ticker}}",
  "side": "{{strategy.order.action}}",
  "price": {{close}},
  "source": "tradingview",
  "strategy": "{{strategy.order.alert_message}}"
}
```

4. Set the `X-Webhook-Secret` header if webhook authentication is configured

---

## Error Handling

All endpoints return standard HTTP status codes:

| Status | Meaning |
|--------|---------|
| `200` | Success |
| `401` | Invalid or missing authentication token |
| `422` | Validation error (invalid request body) |
| `500` | Internal server error |

On authentication failure:
```json
{
  "detail": "Invalid or missing token"
}
```

On webhook authentication failure:
```json
{
  "detail": "Invalid or missing webhook secret"
}
```
