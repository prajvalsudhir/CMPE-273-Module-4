"""Inventory Service - tracks item availability.

Runs as an independent process on port 5001.
Owns the inventory/stock data (in-memory sample data).
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# Sample inventory data: item_id -> units in stock
STOCK = {
    "book-001": 10,
    "headphones-002": 5,
    "keyboard-003": 0,
}


class InventoryHandler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/availability":
            params = parse_qs(parsed.query)
            item_id = params.get("item_id", [None])[0]
            try:
                quantity = int(params.get("quantity", ["1"])[0])
            except ValueError:
                return self._send(400, {"error": "quantity must be an integer"})
            if not item_id:
                return self._send(400, {"error": "item_id is required"})
            stock = STOCK.get(item_id)
            if stock is None:
                return self._send(404, {"error": f"unknown item: {item_id}"})
            available = stock >= quantity
            print(f"[inventory] availability check: {item_id} x{quantity} -> "
                  f"{'AVAILABLE' if available else 'UNAVAILABLE'} (stock={stock})", flush=True)
            return self._send(200, {
                "item_id": item_id,
                "requested": quantity,
                "stock": stock,
                "available": available,
            })
        return self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass  # keep terminal output clean


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 5001), InventoryHandler)
    print("[inventory] Inventory Service running on http://127.0.0.1:5001", flush=True)
    server.serve_forever()
