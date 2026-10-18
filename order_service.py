"""Order Service - creates and tracks orders.

Runs as an independent process on port 5000.
Owns the order data (in-memory order store).

Interaction with Inventory Service:
    Order Service asks Inventory Service whether the requested item
    is available. If the Inventory Service is down or the item is
    unavailable, the Order Service returns an appropriate error and
    keeps running instead of crashing.
"""
import json
import uuid
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

from notification import notify_order_created

INVENTORY_URL = "http://127.0.0.1:5001"
ORDERS = {}  # order_id -> order dict


def check_availability(item_id, quantity):
    """Query the Inventory Service. Returns (available, detail)."""
    url = f"{INVENTORY_URL}/availability?item_id={item_id}&quantity={quantity}"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data.get("available", False), data
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        # Dependency failure: inventory service unreachable
        raise ConnectionError(f"Inventory Service unavailable: {e}")


class OrderHandler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/orders":
            return self._send(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode() or "{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "invalid JSON body"})

        item_id = payload.get("item_id")
        quantity = payload.get("quantity", 1)
        user_id = payload.get("user_id", "guest")
        if not item_id:
            return self._send(400, {"error": "item_id is required"})

        # 1. Query Inventory Service
        try:
            available, detail = check_availability(item_id, quantity)
        except ConnectionError as e:
            # Failure case: dependency down -> 502, but keep running
            print(f"[order] ERROR: {e} -> returning 502", flush=True)
            return self._send(502, {
                "error": "Inventory Service unavailable",
                "message": "Could not verify item availability. Please try again later.",
            })

        if not available:
            print(f"[order] item {item_id} unavailable (stock={detail.get('stock')}) -> 409", flush=True)
            return self._send(409, {
                "error": "Item unavailable",
                "item_id": item_id,
                "stock": detail.get("stock"),
            })

        # 2. Create the order
        order_id = f"ord-{uuid.uuid4().hex[:8]}"
        order = {
            "order_id": order_id,
            "user_id": user_id,
            "item_id": item_id,
            "quantity": quantity,
            "status": "created",
        }
        ORDERS[order_id] = order
        print(f"[order] created {order_id} for {item_id} x{quantity}", flush=True)

        # 3. Emit "Order was created" event -> notification
        notify_order_created(order)

        return self._send(201, order)

    def do_GET(self):
        if self.path == "/orders":
            return self._send(200, {"orders": list(ORDERS.values())})
        return self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass  # keep terminal output clean


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 5000), OrderHandler)
    print("[order] Order Service running on http://127.0.0.1:5000", flush=True)
    server.serve_forever()
