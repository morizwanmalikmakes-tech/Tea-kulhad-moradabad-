#!/usr/bin/env python3
"""The Tea Factory Moradabad - Order Backend (pure stdlib, no deps)"""
import json, os, re, random, string, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get("PORT", "8080"))
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "orders.json")
LOCK = threading.Lock()
ADMIN_PW = "teafactory2026"
STATUSES = ["Placed", "Preparing", "Out for Delivery", "Delivered"]

def load():
    if os.path.exists(DB):
        with open(DB) as f: return json.load(f)
    return {"orders": {}}

def save(db):
    with open(DB, "w") as f: json.dump(db, f, indent=1)

def now(): return datetime.now().strftime("%d %b %Y, %I:%M %p")

def new_id():
    d = datetime.now().strftime("%y%m%d")
    r = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"TTF-{d}-{r}"

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, obj, ctype="application/json"):
        data = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self): self._send(200, {})

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        if p in ("/", "/index.html"):
            with open(os.path.join(BASE, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if p == "/api/ping":
            return self._send(200, {"ok": True, "time": now()})
        if p == "/api/admin":
            q = parse_qs(u.query)
            if q.get("pw", [""])[0] != ADMIN_PW:
                return self._send(403, {"error": "wrong password"})
            with LOCK:
                db = load()
            ol = sorted(db["orders"].values(), key=lambda o: o["placed_ts"], reverse=True)
            return self._send(200, {"orders": ol})
        m = re.match(r"^/api/orders/([\w-]+)$", p)
        if m:
            with LOCK:
                db = load()
            o = db["orders"].get(m.group(1).upper())
            if not o: return self._send(404, {"error": "order not found"})
            return self._send(200, o)
        self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if u.path == "/api/orders":
            items = body.get("items", [])
            cust = body.get("customer", {})
            if not items or not cust.get("name") or not cust.get("phone"):
                return self._send(400, {"error": "items + name + phone required"})
            with LOCK:
                db = load()
                oid = new_id()
                while oid in db["orders"]: oid = new_id()
                t = now()
                order = {
                    "id": oid, "items": items, "customer": cust,
                    "total": body.get("total", 0), "pay": body.get("pay", "COD"),
                    "status": "Placed", "status_idx": 0,
                    "placed_at": t, "placed_ts": datetime.now().isoformat(),
                    "eta": (datetime.now() + timedelta(minutes=35)).strftime("%I:%M %p"),
                    "timeline": [{"status": "Placed", "at": t}],
                }
                db["orders"][oid] = order
                save(db)
            return self._send(200, order)
        if u.path == "/api/admin":
            if body.get("pw") != ADMIN_PW:
                return self._send(403, {"error": "wrong password"})
            oid = (body.get("id") or "").upper()
            with LOCK:
                db = load()
                o = db["orders"].get(oid)
                if not o: return self._send(404, {"error": "order not found"})
                ni = min(o["status_idx"] + 1, len(STATUSES) - 1)
                o["status_idx"] = ni
                o["status"] = STATUSES[ni]
                o["timeline"].append({"status": STATUSES[ni], "at": now()})
                save(db)
            return self._send(200, o)
        self._send(404, {"error": "not found"})

if __name__ == "__main__":
    print(f"Tea Factory backend on 0.0.0.0:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
