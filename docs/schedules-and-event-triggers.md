# Schedules & Event Triggers

Automate agent runs either on a fixed interval (`client.schedules`) or from an
external webhook payload (`client.event_triggers`). Covers CRUD, run history
pagination, secret rotation, webhook signature verification, and a
FastAPI callback handler example.

```python
from teardrop import (
    CreateEventTriggerRequest,
    CreateScheduleRequest,
    UpdateScheduleRequest,
)

schedule = await client.schedules.create(CreateScheduleRequest(
    name="Daily Summary",
    prompt="Summarize portfolio balances",
    interval_seconds=86_400,
    callback_url="https://callback.example.com/schedules",
))

schedules = await client.schedules.list()
schedule = await client.schedules.get(schedule.id)
schedule = await client.schedules.update(
    schedule.id,
    UpdateScheduleRequest(enabled=False, callback_url=None),
)
runs = await client.schedules.runs(schedule.id, limit=10)
async for run in client.schedules.runs_iter(schedule.id, limit=100):
    print(run.status, run.run_id)
await client.schedules.delete(schedule.id)

trigger = await client.event_triggers.create(CreateEventTriggerRequest(
    name="On Payment Inbound",
    prompt="Audit incoming payment of {{amount}} for user {{userId}}. Full tx: {{event_json}}",
    callback_url="https://callback.example.com/events",
))

print(trigger.event_path)
print(trigger.secret)  # store now; only returned on create / rotate

rotation = await client.event_triggers.rotate_secret(trigger.id)
trigger_runs = await client.event_triggers.runs(trigger.id, limit=10)
async for run in client.event_triggers.runs_iter(trigger.id, limit=100):
    print(run.status, run.run_id)
```

Inbound dispatch is server-to-server and not a client method: your webhook source sends `POST /agent/events/{trigger_token}` with `X-Teardrop-Trigger-Secret` and a JSON body. Persist the secret returned by `create()` or `rotate_secret()` immediately.

## Verifying Signed Callback Payloads

```python
from teardrop import verify_webhook

if not verify_webhook(raw_payload_bytes, signature_header, secret):
    raise PermissionError("invalid webhook signature")
```

## Example Callback Handler (FastAPI)

```python
from fastapi import FastAPI, Header, HTTPException, Request
from teardrop import verify_webhook

app = FastAPI()
TEARDROP_SECRET = "whsec_from_trigger_create_or_rotate"


@app.post("/teardrop/event")
async def teardrop_event(
    request: Request,
    x_teardrop_trigger_secret: str | None = Header(default=None),
):
    payload = await request.body()
    signature = x_teardrop_trigger_secret or ""

    if not verify_webhook(payload, signature, TEARDROP_SECRET):
        raise HTTPException(status_code=401, detail="invalid signature")

    event = await request.json()
    # Use event values inside your prompt template, e.g. {{event_json}}, {{amount}}, etc.
    return {"ok": True, "event_id": event.get("id")}
```

---

**Related:** [README](../README.md) · [Agent Runs](agent-runs.md) · [Webhook Verification](../src/teardrop/webhook_verify.py)
