"""
SafeCircle local demo server.

    python server.py                 # http://localhost:8000
    python server.py --host 0.0.0.0  # open from a phone on the same Wi-Fi
    python server.py --no-ai         # force rules-only mode

Put OPENAI_API_KEY in the environment or a .env file to turn on AI checking.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(ROOT, "static")


def load_dotenv():
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()
sys.path.insert(0, ROOT)
from shield import engine, llm, store  # noqa: E402
from shield import ml_layer  # noqa: E402
from shield.policy import POLICY_VERSION  # noqa: E402

AI_ENABLED = True
MAX_BODY = 12 * 1024 * 1024
DATA_URL = re.compile(r"^data:(image/(?:png|jpeg|jpg|webp|gif));base64,(.+)$", re.S)


class Handler(BaseHTTPRequestHandler):
    server_version = "SafeCircleDemo/0.2"

    def log_message(self, fmt, *args):
        if "/api/guardian" not in (args[0] if args else ""):
            sys.stderr.write("  %s\n" % (fmt % args))

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("Upload is too large. Send an image under 10 MB.")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _static(self, path):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        full = os.path.normpath(os.path.join(STATIC, rel))
        if not full.startswith(STATIC) or not os.path.isfile(full):
            return self._json(404, {"error": "Not found"})
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        data = open(full, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        p = url.path
        if p == "/api/status":
            return self._json(200, {
                "ai": AI_ENABLED and llm.available(),
                "provider": "openai" if llm.available() else None,
                "model": llm.model_name() if llm.available() else None,
                "ml": ml_layer.status(),
                "policy_version": POLICY_VERSION,
                "demo_takeover": llm.demo_takeover_enabled(),
            })
        if p == "/api/samples":
            return self._json(200, json.load(open(os.path.join(ROOT, "samples.json"), encoding="utf-8")))
        if p == "/api/guardian":
            return self._json(200, engine.guardian_view())
        if p == "/api/settings":
            return self._json(200, store.get_settings())
        m = re.fullmatch(r"/api/cases/(\d+)/advice", p)
        if m:
            lang = parse_qs(url.query).get("lang", ["en"])[0]
            return self._json(200, engine.advice(int(m.group(1)), lang))
        m = re.fullmatch(r"/api/cases/(\d+)", p)
        if m:
            detail = engine.case_detail(int(m.group(1)))
            if not detail:
                return self._json(404, {"error": "Not found"})
            return self._json(200, detail)
        if p.startswith("/api/"):
            return self._json(404, {"error": "Not found"})
        return self._static(p)

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            body = self._body()
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json(400, {"error": str(exc)})

        if p == "/api/check":
            image_b64, image_type = None, "image/jpeg"
            if body.get("image"):
                m = DATA_URL.match(body["image"])
                if not m:
                    return self._json(400, {"error": "Send a PNG, JPEG, WebP or GIF image."})
                image_type = m.group(1).replace("jpg", "jpeg")
                image_b64 = m.group(2)
                try:
                    base64.b64decode(image_b64[:100] + "==", validate=False)
                except Exception:
                    return self._json(400, {"error": "The image couldn't be read."})
            case_id = body.get("case_id")
            try:
                case_id = int(case_id) if case_id is not None else None
            except (TypeError, ValueError):
                case_id = None
            result = engine.check(
                text=body.get("text", ""),
                image_b64=image_b64,
                image_type=image_type,
                lang=body.get("lang", "en"),
                use_ai=AI_ENABLED,
                case_id=case_id,
                role=body.get("role", "other"),
            )
            return self._json(200, result)

        m = re.fullmatch(r"/api/cases/(\d+)/(ask-family|report)", p)
        if m:
            case_id, action = int(m.group(1)), m.group(2)
            fn = engine.ask_family if action == "ask-family" else engine.report
            result = fn(case_id, body.get("lang", "en"))
            return self._json(404 if result["status"] == "not_found" else 200, result)

        m = re.fullmatch(r"/api/cases/(\d+)/judge", p)
        if m:
            from shield.agents import judge as judge_agent
            case_id = int(m.group(1))
            detail = engine.case_detail(case_id)
            if not detail:
                return self._json(404, {"error": "Not found"})
            out = judge_agent.run(detail["case"], facts=detail["facts"], items=detail["items"])
            if out is None:
                return self._json(503, {"error": "Judge unavailable"})
            return self._json(200, out)

        m = re.fullmatch(r"/api/cases/(\d+)/override", p)
        if m:
            result = engine.override(
                int(m.group(1)),
                body.get("reviewer", "reviewer"),
                body.get("verdict", "unclear"),
                body.get("note", ""),
            )
            return self._json(404 if result.get("status") == "not_found" else 200, result)

        m = re.fullmatch(r"/api/alerts/(\d+)/handled", p)
        if m:
            store.handle_alert(int(m.group(1)))
            return self._json(200, {"status": "ok"})

        if p == "/api/settings":
            store.update_settings(body)
            return self._json(200, store.get_settings())

        if p == "/api/reset":
            store.reset()
            return self._json(200, {"status": "ok"})

        if p == "/api/agent/draft":
            result = engine.draft_reply(body.get("case_id"), body.get("history", []), body.get("lang", "en"))
            if result is None:
                return self._json(503, {"error": "AI not available or case not found"})
            # Backward-compatible: also expose first draft text as "draft".
            first = None
            drafts = result.get("drafts") or []
            if drafts:
                first = drafts[0].get("text")
            return self._json(200, {**result, "draft": first})

        if p == "/api/agent/engage":
            if not llm.demo_takeover_enabled():
                return self._json(403, {"error": "Demo takeover disabled"})
            result = engine.agent_engage(body.get("case_id"), body.get("history", []), body.get("lang", "en"))
            if result is None:
                return self._json(503, {"error": "AI not available, case not found, or severity too low"})
            return self._json(200, {"reply": result})

        return self._json(404, {"error": "Unknown endpoint"})


def main():
    global AI_ENABLED
    ap = argparse.ArgumentParser(description="SafeCircle local demo")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-ai", action="store_true", help="rules only, even if an API key is set")
    args = ap.parse_args()
    AI_ENABLED = not args.no_ai

    store.conn()
    ml_st = ml_layer.status()
    mode = f"rules + AI ({llm.model_name()})" if AI_ENABLED and llm.available() else "rules only"
    ml_mode = "on" if ml_st.get("available") else "off"
    print(f"\n  SafeCircle demo running at http://{'localhost' if args.host == '127.0.0.1' else args.host}:{args.port}")
    print(f"  Detection mode: {mode}  |  ML: {ml_mode}  |  policy {POLICY_VERSION}")
    print(f"  Three-panel demo: http://localhost:{args.port}/demo.html")
    if args.host == "0.0.0.0":
        print("  Open it from a phone on the same Wi-Fi using this computer's IP address.")
    print("  Press Ctrl+C to stop.\n")
    try:
        ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
