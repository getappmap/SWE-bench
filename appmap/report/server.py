import functools
import http.server
import json
import os
import socketserver


INDEX_HTML_PATH = os.path.join(os.path.dirname(__file__), "index.html")

result_list = []

class ReportHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/index.html" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open(INDEX_HTML_PATH, "rb") as f:
                self.copyfile(f, self.wfile)
        elif self.path == "/reports-list":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result_list).encode())
        else:
            super().do_GET()


def serve_reports(directory: str, port, results):
    Handler = functools.partial(ReportHandler, directory=directory)
    result_list.extend(results)
    result_list.sort(key=lambda x: x["id"])

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"Serving at port {port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down server")
            httpd.server_close()
            httpd.shutdown()
