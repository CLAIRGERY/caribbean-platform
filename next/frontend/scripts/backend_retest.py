"""One-shot Render backend re-test (bounded). Prints reachability summary only."""

import socket
import ssl
import time

host = "sakgaze-api.onrender.com"
ctx = ssl.create_default_context()
t0 = time.time()
try:
    s = socket.create_connection((host, 443), timeout=20)
    ss = ctx.wrap_socket(s, server_hostname=host)
    ss.settimeout(10)
    ss.sendall(b"GET /health HTTP/1.1\r\nHost: sakgaze-api.onrender.com\r\nConnection: close\r\n\r\n")
    data = b""
    while True:
        try:
            c = ss.recv(65536)
        except socket.timeout:
            print(f"recv-timeout after {time.time()-t0:.1f}s; bytes so far: {len(data)}")
            break
        if not c:
            break
        data += c
        if data > b"" and len(data) > 200000:
            break
    print(f"total bytes: {len(data)}")
    print(data[:250].decode(errors="replace"))
except Exception as e:
    print(f"elapsed={time.time()-t0:.1f}s ERR {type(e).__name__}: {e}")
