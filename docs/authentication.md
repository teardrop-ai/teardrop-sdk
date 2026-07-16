# Authentication

Covers JWT acquisition and refresh, SIWE (Sign-In With Ethereum), self-service
registration, email verification, organization invites, and live tool
discovery for the authenticated org. Applies to both `AsyncTeardropClient` and
`TeardropClient`.

## Auth Methods

Credentials are passed to the client constructor. `TokenManager` acquires a
JWT automatically on the first request and refreshes it before expiry
(30-minute window).

| Method | Constructor kwargs |
|---|---|
| Email + password | `email=..., secret=...` |
| Client credentials (M2M) | `client_id=..., client_secret=...` |
| Pre-authenticated static token | `token=...` |
| SIWE (sign-in with Ethereum) | Call `authenticate_siwe()` after construction (see below) |

## SIWE Login Flow

```python
async with AsyncTeardropClient("https://api.teardrop.dev") as client:
    # 1. Fetch a single-use nonce
    nonce_resp = await client.get_siwe_nonce()
    nonce = nonce_resp["nonce"]

    # 2. Build and sign an EIP-4361 message client-side (e.g. with siwe-py)
    #    Embed the nonce in the SIWE message body
    message = build_siwe_message(nonce=nonce, ...)
    signature = wallet.sign_message(message)

    # 3. Exchange for a JWT — stored automatically for subsequent calls
    token = await client.authenticate_siwe(message, signature)
```

## Email Registration

```python
tokens = await client.register(email="you@example.com", password="...")
# Verify email before first login
await client.verify_email(token=email_token)
```

## Token Refresh / Logout

```python
new_tokens = await client.refresh(refresh_token)
await client.logout(refresh_token)
```

## Inspect Identity

```python
me = await client.get_me()
# → JwtPayloadBase(sub=..., org_id=..., role="member", auth_method="email", ...)
```

## Organization Management

```python
# Create an invite link (role must be "member" or "user")
invite = await client.invite(email="colleague@example.com", role="member")
print(f"Invite URL: {invite['invite_url']}")
```

*Note: Attempting to invite with `role="admin"` will return a 422 error from the API.*

## Live Tool Discovery

List all tools available to the current agent, including their source and access status.

```python
tools = await client.get_agent_tools()
for tool in tools:
    # source: "platform" | "org" | "marketplace"
    # access_mode: "included" | "subscribed"
    print(f"{tool.name} ({tool.source}): {tool.access_mode}")
```

---

**Related:** [README](../README.md) · [Agent Runs](agent-runs.md) · [Marketplace](marketplace.md) · [spec/openapi.json](../spec/openapi.json)
