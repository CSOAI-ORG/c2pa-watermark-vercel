"""
C2PA Watermark MCP — Vercel serverless API
==========================================
Wraps the c2pa_watermark_mcp package as Vercel routes:
  GET  /         — health + docs
  POST /sign     — issue a C2PA manifest (requires MEOK_PRO_KEY)
  POST /verify   — verify a manifest against asset bytes (public)
  GET  /status   — server health + c2pa-python availability

Env vars:
  MEOK_C2PA_KEY   HMAC signing key (rotate quarterly)
  MEOK_PRO_KEYS   comma-separated list of authorized API keys
"""
from __future__ import annotations

import base64
import hmac
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler

from c2pa_watermark_mcp import sign_asset, status, verify_asset

C2PA_KEY = os.environ.get("MEOK_C2PA_KEY", "").encode("utf-8")
PRO_KEYS = set(
    k.strip()
    for k in os.environ.get("MEOK_PRO_KEYS", "").split(",")
    if k.strip()
)


def _json_response(handler: BaseHTTPRequestHandler, status: int, body: dict) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(json.dumps(body).encode("utf-8"))


def _check_auth(handler: BaseHTTPRequestHandler) -> bool:
    """Free tier = no auth, Pro tier = require MEOK_PRO_KEYS match."""
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth[7:]
    return token in PRO_KEYS


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/health":
            return _json_response(self, 200, status())
        if self.path == "/status":
            return _json_response(self, 200, status())
        return _json_response(self, 404, {"error": "not_found", "path": self.path})

    def do_POST(self):
        if self.path == "/sign":
            return self._handle_sign()
        if self.path == "/verify":
            return self._handle_verify()
        return _json_response(self, 404, {"error": "not_found", "path": self.path})

    # ── /sign ────────────────────────────────────────────────────────────
    def _handle_sign(self):
        if not PRO_KEYS:
            return _json_response(self, 503, {
                "error": "pro_keys_not_configured",
                "message": "Server has no MEOK_PRO_KEYS configured. Set one in Vercel env.",
            })
        if not _check_auth(self):
            return _json_response(self, 401, {
                "error": "unauthorized",
                "message": "Valid Bearer token required. Pro tier only.",
                "upgrade": "https://buy.stripe.com/5kQ6oJ0xS3ce8sl7ew8k91j",
            })
        if not C2PA_KEY:
            return _json_response(self, 503, {
                "error": "signing_key_not_configured",
                "message": "Set MEOK_C2PA_KEY in Vercel env.",
            })

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            return _json_response(self, 400, {"error": "invalid_json", "message": str(e)})

        asset_b64 = body.get("asset_base64", "")
        if not asset_b64:
            return _json_response(self, 400, {
                "error": "missing_asset",
                "message": "Provide asset_base64 (base64-encoded file bytes)",
            })

        try:
            asset_bytes = base64.b64decode(asset_b64)
        except Exception as e:
            return _json_response(self, 400, {"error": "bad_base64", "message": str(e)})

        result = sign_asset(
            asset_bytes=asset_bytes,
            asset_mime=body.get("asset_mime", "application/octet-stream"),
            claim_generator=body.get("claim_generator", "MEOK-C2PA-Vercel/1.0"),
            signing_key=C2PA_KEY,
            assertions=body.get("assertions"),
            ingredients=body.get("ingredients"),
            ai_generated=body.get("ai_generated", True),
        )
        return _json_response(self, 200, result)

    # ── /verify ──────────────────────────────────────────────────────────
    def _handle_verify(self):
        # /verify is public (auditors verify without auth)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            return _json_response(self, 400, {"error": "invalid_json", "message": str(e)})

        asset_b64 = body.get("asset_base64", "")
        manifest = body.get("manifest")
        if not asset_b64 or not manifest:
            return _json_response(self, 400, {
                "error": "missing_fields",
                "message": "Provide asset_base64 + manifest",
            })

        # The signing key is the same one used to sign. In production
        # you'd fetch the signer's public key from a manifest store.
        # For now, support a custom key via header for offline verifiers.
        verify_key_b64 = self.headers.get("X-C2PA-Key-Base64", "")
        if verify_key_b64:
            try:
                verify_key = base64.b64decode(verify_key_b64)
            except Exception:
                return _json_response(self, 400, {"error": "bad_key"})
        else:
            verify_key = C2PA_KEY

        if not verify_key:
            return _json_response(self, 400, {
                "error": "no_verification_key",
                "message": (
                    "Server is not configured with a signing key. Pass "
                    "X-C2PA-Key-Base64 header to verify with a specific key."
                ),
            })

        try:
            asset_bytes = base64.b64decode(asset_b64)
        except Exception as e:
            return _json_response(self, 400, {"error": "bad_base64", "message": str(e)})

        verdict = verify_asset(asset_bytes=asset_bytes, manifest=manifest, signing_key=verify_key)
        return _json_response(self, 200, verdict)
