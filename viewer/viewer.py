#!/usr/bin/env python

import http.server
import socketserver
import os
import sys

PORT = 8080

data_path = os.path.abspath(sys.argv[1])

# Serve files from the script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))


class SimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_my_headers()

        http.server.SimpleHTTPRequestHandler.end_headers(self)

    def send_my_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")

    def do_GET(self):
        if self.path == "/data.jsonl":
            return self.send_data()
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

    def send_data(self):
        self.send_response(200)
        self.send_header("Content-type", "application/jsonlines")
        self.end_headers()
        with open(data_path, "rb") as f:
            self.copyfile(f, self.wfile)


socketserver.TCPServer.allow_reuse_address = True
if __name__ == "__main__":
    Handler = SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("Serving at port:", PORT)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down server")
            httpd.server_close()
            httpd.shutdown()
