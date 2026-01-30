# Upgrade Plan: MCP OAuth 2.1 Authorization

**Date**: 2026-01-30
**Current State**: Server-side OAuth client credentials (env vars)
**Target State**: MCP spec-compliant OAuth 2.1 authorization

## Background

The current jama-mcp-server uses a "server-side" OAuth approach:
- Credentials stored in `.env` or AWS Parameter Store
- Server handles token exchange internally
- Works but bypasses MCP's auth model

The MCP spec (2025-11-25) defines proper OAuth 2.1 authorization at the transport level.

## Key Changes Required

### 1. Protected Resource Metadata (RFC9728)

Server MUST expose authorization server location via:

```
GET /.well-known/oauth-protected-resource
```

Returns:
```json
{
  "resource": "https://jama-mcp.example.com",
  "authorization_servers": ["https://jama.iscinternal.com/oauth"],
  "scopes_supported": ["read", "write"],
  "bearer_methods_supported": ["header"]
}
```

### 2. 401 Response with WWW-Authenticate

When client requests without token:

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer resource_metadata="https://jama-mcp.example.com/.well-known/oauth-protected-resource",
                         scope="read"
```

### 3. Token Validation (not acquisition)

Server no longer acquires tokens - it validates them:

```python
# OLD: Server gets its own token
credentials = get_jama_credentials()
client = JamaClient(credentials=(client_id, client_secret), oauth=True)

# NEW: Server validates client-provided token
def validate_token(token: str) -> bool:
    # Validate JWT signature, expiry, scopes
    # Or introspect with Jama's token endpoint
    pass
```

### 4. Scope-Based Authorization

Define scopes for Jama operations:

| Scope | Operations |
|-------|------------|
| `jama:read` | get_*, search_*, list_* |
| `jama:write` | create_*, update_*, delete_* |
| `jama:admin` | All operations |

## Architecture Changes

### Current Flow
```
Claude Code → MCP Server → (OAuth internally) → Jama API
                ↑
            .env credentials
```

### New Flow
```
Claude Code → OAuth Server → Token
     ↓
Claude Code → MCP Server (with Bearer token) → Jama API
                ↑
            Validates token
```

## Implementation Steps

### Phase 1: HTTP Transport (Required for MCP OAuth)

Currently using STDIO. Need to add HTTP/SSE transport option.

```python
# Add FastAPI/Starlette HTTP endpoint
from mcp.server.sse import SseServerTransport

app = Starlette(routes=[
    Route("/mcp", endpoint=mcp_sse_handler),
    Route("/.well-known/oauth-protected-resource", endpoint=resource_metadata),
])
```

### Phase 2: Protected Resource Metadata

```python
async def resource_metadata(request):
    return JSONResponse({
        "resource": str(request.url.replace(path="/")),
        "authorization_servers": [os.environ["JAMA_AUTH_SERVER"]],
        "scopes_supported": ["jama:read", "jama:write"],
        "bearer_methods_supported": ["header"]
    })
```

### Phase 3: Token Validation Middleware

```python
async def validate_bearer_token(request, call_next):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return Response(
            status_code=401,
            headers={
                "WWW-Authenticate": f'Bearer resource_metadata="{RESOURCE_METADATA_URL}"'
            }
        )

    token = auth[7:]
    if not await validate_with_jama(token):
        return Response(status_code=401)

    return await call_next(request)
```

### Phase 4: Scope Enforcement

```python
def require_scope(scope: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx: Context, *args, **kwargs):
            token_scopes = ctx.request_context.get("scopes", [])
            if scope not in token_scopes:
                raise PermissionError(f"Missing scope: {scope}")
            return await func(ctx, *args, **kwargs)
        return wrapper
    return decorator

@mcp.tool()
@require_scope("jama:write")
async def jama_create_item(...):
    ...
```

## Jama OAuth Consideration

**Critical Question**: Does Jama's OAuth support the required flows?

Jama Connect uses OAuth 2.0 client credentials. For MCP OAuth to work:

1. **Option A**: Jama as Authorization Server
   - User authenticates with Jama directly
   - Jama issues tokens with user identity
   - MCP server validates tokens with Jama
   - **Requires**: Jama to support authorization code flow (not just client credentials)

2. **Option B**: External Authorization Server
   - Use corporate IdP (Okta, Azure AD) as auth server
   - MCP server validates tokens from IdP
   - MCP server uses service account to call Jama API
   - Token maps user identity for audit, but Jama calls use shared creds

3. **Option C**: Hybrid (Recommended for ISC)
   - Keep current client credentials for Jama API access
   - Add MCP OAuth layer for Claude Code → MCP Server auth
   - ISC Azure AD as authorization server
   - User identity passed through for audit logging

## Migration Path

### v1.1 (Backward Compatible)
- Add HTTP transport option (keep STDIO working)
- Add protected resource metadata endpoint
- Add optional bearer token validation
- Environment flag to enable MCP OAuth mode

### v2.0 (Full MCP OAuth)
- HTTP transport as primary
- Remove env-based credentials option
- Full scope enforcement
- Audit logging with user identity

## Files to Modify

| File | Changes |
|------|---------|
| `server.py` | Add HTTP transport, metadata endpoints |
| `auth.py` | Add token validation (vs acquisition) |
| `middleware.py` | New - bearer validation, scope checking |
| `tools/*.py` | Add scope decorators |
| `pyproject.toml` | Add starlette, uvicorn deps |

## Testing

1. Unit tests for token validation
2. Integration tests with mock auth server
3. E2E test with Azure AD (if Option C)
4. Backward compatibility test with STDIO

## Open Questions

1. Does Jama support authorization code flow for end-user auth?
2. Can we use ISC Azure AD as the MCP authorization server?
3. What scopes should map to which Jama operations?
4. How do we handle refresh tokens in MCP context?

## References

- [MCP Authorization Spec 2025-11-25](https://spec.modelcontextprotocol.io/specification/2025-11-25/basic/authorization/)
- [RFC9728 - OAuth 2.0 Protected Resource Metadata](https://datatracker.ietf.org/doc/html/rfc9728)
- [RFC8414 - OAuth 2.0 Authorization Server Metadata](https://datatracker.ietf.org/doc/html/rfc8414)
- [Jama REST API Auth](https://dev.jamasoftware.com/api/authentication)
