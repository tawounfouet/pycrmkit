"""Local HTTP boundary test for the standard-library webhook transport."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from pycrmkit.webhooks import (
    StdlibWebhookTransport,
    WebhookRequest,
)


class _Handler(BaseHTTPRequestHandler):
    received_body = b""
    received_delivery_id = ""

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        type(self).received_body = self.rfile.read(length)
        type(self).received_delivery_id = self.headers.get(
            "X-PyCRMKit-Delivery-ID",
            "",
        )
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        del format, args


def test_stdlib_transport_posts_to_local_http_boundary_when_explicitly_allowed() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        transport = StdlibWebhookTransport(allow_private_networks=True)
        response = transport.send(
            WebhookRequest(
                url=f"http://127.0.0.1:{server.server_port}/hook",
                body=b'{"ok":true}',
                headers={
                    "Content-Type": "application/json",
                    "X-PyCRMKit-Delivery-ID": "delivery-local",
                },
            )
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert response.status_code == 204
    assert _Handler.received_body == b'{"ok":true}'
    assert _Handler.received_delivery_id == "delivery-local"
