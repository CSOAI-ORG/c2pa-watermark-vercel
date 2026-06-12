# c2pa-watermark-mcp — Vercel serverless wrapper

A Vercel-deployable HTTP API wrapping the
[c2pa-watermark-mcp](https://github.com/CSOAI-ORG/c2pa-watermark-mcp) package.

## Routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/` | none | Health + docs |
| GET | `/health` | none | Liveness |
| GET | `/status` | none | Server health + c2pa-python availability |
| POST | `/sign` | Pro Bearer | Issue a C2PA manifest |
| POST | `/verify` | none (or `X-C2PA-Key-Base64`) | Verify a manifest against asset bytes |

## Env vars

| Var | Required | Notes |
|-----|----------|-------|
| `MEOK_C2PA_KEY` | yes (for /sign) | HMAC signing key, rotate quarterly |
| `MEOK_PRO_KEYS` | yes (for /sign) | Comma-separated Pro API keys |

## Deploy

```bash
cd c2pa-watermark-vercel
npm install
vercel --prod
# Then in Vercel dashboard:
#   vercel env add MEOK_C2PA_KEY production
#   vercel env add MEOK_PRO_KEYS production
#   vercel --prod  # redeploy
```

## Usage

```bash
# Sign (Pro tier)
curl -X POST https://c2pa-watermark-mcp.vercel.app/sign \
  -H "Authorization: Bearer meok_pro_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQMAAAAl21bKAAAAA1BMVEX/AAAZ4gk3AAAAAXRSTlMAQObYZgAAAApJREFUCNdjYAAAAAIAAeIhvDMAAAAASUVORK5CYII=",
    "asset_mime": "image/png",
    "claim_generator": "MEOK-SDXL/1.0",
    "ai_generated": true
  }'

# Verify (public)
curl -X POST https://c2pa-watermark-mcp.vercel.app/verify \
  -H "Content-Type: application/json" \
  -H "X-C2PA-Key-Base64: <base64-of-signing-key>" \
  -d '{
    "asset_base64": "...",
    "manifest": { ... }
  }'
```

## License

MIT © MEOK AI Labs / CSOAI-ORG
