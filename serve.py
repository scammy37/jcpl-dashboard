import os, http.server, functools

port = int(os.environ.get("PORT", 8080))
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=os.path.dirname(os.path.abspath(__file__)))
with http.server.HTTPServer(("", port), handler) as httpd:
    print(f"Serving on http://localhost:{port}", flush=True)
    httpd.serve_forever()
