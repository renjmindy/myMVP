#!/usr/bin/env python
# coding: utf-8
"""
Example client for POST /predict (standard library only).

    python examples/call_predict.py <snapshot.png|jpg> [server_url]
    python examples/call_predict.py samples/sample_found.jpg http://localhost:8000

Prints the single-line JSON, the saved image name (X-Image) and the failure reason (X-Reason).
"""
import http.client
import json
import os
import sys
import uuid
from datetime import datetime
from urllib.parse import urlparse


def predict(image_path, server="http://localhost:8000", timestamp=None):
    """Upload one snapshot. Returns (result_dict, image_name, reason)."""
    timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")     # also write this into your own log
    boundary = uuid.uuid4().hex
    with open(image_path, "rb") as f:
        data = f.read()
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="timestamp"\r\n\r\n{timestamp}\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(image_path)}"\r\n'
        f'Content-Type: application/octet-stream\r\n\r\n'
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()

    u = urlparse(server)
    conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=60)
    conn.request("POST", "/predict", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    resp = conn.getresponse()
    text = resp.read().decode()
    if resp.status != 200:
        raise RuntimeError(f"HTTP {resp.status}: {text}")
    return json.loads(text), resp.getheader("X-Image", ""), resp.getheader("X-Reason", "")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    result, image_name, reason = predict(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000")
    print(json.dumps(result, separators=(",", ":")))
    print("found:", result["found"], " x:", result["x"], " y:", result["y"])
    print("saved image:", image_name or "-", "  reason:", reason or "-")
