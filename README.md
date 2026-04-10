# teardrop-sdk

Python SDK for the [Teardrop](https://github.com/teardrop-ai/teardrop) AI agent API.

## Install

```bash
pip install teardrop-sdk
```

## Quick Start

```python
from teardrop import AsyncTeardropClient

async with AsyncTeardropClient(
    "https://api.teardrop.dev",
    email="you@example.com",
    secret="your-password",
) as client:
    async for event in client.run("What is the ETH price on Base?"):
        if event.type == "TEXT_MESSAGE_CONTENT":
            print(event.data.get("delta", ""), end="")
    print()
```

### Sync Usage

```python
from teardrop import TeardropClient

with TeardropClient(
    "https://api.teardrop.dev",
    email="you@example.com",
    secret="your-password",
) as client:
    for event in client.run_sync("What is 2 + 2?"):
        if event.type == "TEXT_MESSAGE_CONTENT":
            print(event.data.get("delta", ""), end="")
    print()
```

## Auth Methods

| Method | Constructor args |
|--------|-----------------|
| Email + password | `email=..., secret=...` |
| Client credentials (M2M) | `client_id=..., client_secret=...` |
| Pre-authenticated token | `token=...` |
| SIWE (pre-signed) | Pass `siwe_message` + `siwe_signature` via `authenticate_siwe()` |

## Features

- Async-first with sync wrapper
- Typed Pydantic models for all responses
- SSE streaming with parsed event objects
- Auto token refresh
- Zero langchain dependency
