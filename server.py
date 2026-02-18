#!/usr/bin/env python3
"""
Mini web server for Ad Tech Intelligence dashboards.
Run: python3 server.py
Then open: http://localhost:8080
"""

import http.server
import os
import socketserver
import glob
from datetime import datetime

PORT = 8080
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=OUTPUT_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(build_index().encode("utf-8"))
        else:
            super().do_GET()


def build_index():
    curators = sorted(glob.glob(os.path.join(OUTPUT_DIR, "dashboard-*.html")), reverse=True)
    financials = sorted(glob.glob(os.path.join(OUTPUT_DIR, "financial-intel-*.html")), reverse=True)
    pdfs = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.pdf")), reverse=True)

    def card(filepath, title, desc, icon, color):
        fname = os.path.basename(filepath)
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%b %d, %Y at %H:%M")
        size = os.path.getsize(filepath)
        size_str = f"{size/1024:.0f} KB" if size < 1_000_000 else f"{size/1_000_000:.1f} MB"
        return f"""
        <a href="/{fname}" class="card" style="--accent:{color}">
            <div class="card-icon">{icon}</div>
            <div class="card-body">
                <h3>{title}</h3>
                <p>{desc}</p>
                <div class="card-meta">{mtime} &middot; {size_str}</div>
            </div>
            <div class="card-arrow">&rarr;</div>
        </a>"""

    cards_html = ""
    for f in curators:
        cards_html += card(f, "Performance DSP Intelligence",
                          "Content curation — blogs, podcasts, YouTube. Relevance scoring, key signals, must-reads.",
                          "📡", "#6366f1")
    for f in financials:
        cards_html += card(f, "Financial Deep Analysis",
                          "Equity research note — P&L analysis, moats, DSP landscape, strategic outlook.",
                          "📊", "#10b981")
    for f in pdfs:
        cards_html += card(f, "Financial Report (PDF)",
                          "Printable version of the financial analysis. Share via email or Slack.",
                          "📄", "#f59e0b")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ad Tech Intelligence Hub</title>
<style>
:root {{ --bg: #0a0a10; --surface: #12121c; --border: #252538; --text: #e2e2ef; --text2: #8888a0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }}
.container {{ max-width: 720px; margin: 0 auto; padding: 60px 24px; }}
.logo {{ font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 3px; color: #6366f1; margin-bottom: 8px; }}
h1 {{ font-size: 36px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 8px; }}
h1 span {{ color: #818cf8; }}
.subtitle {{ color: var(--text2); font-size: 15px; margin-bottom: 40px; line-height: 1.6; }}
.cards {{ display: flex; flex-direction: column; gap: 16px; }}
.card {{
    display: flex; align-items: center; gap: 20px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; padding: 24px; text-decoration: none; color: inherit;
    transition: all 0.2s; border-left: 4px solid var(--accent);
}}
.card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.3); border-color: var(--accent); }}
.card-icon {{ font-size: 32px; flex-shrink: 0; }}
.card-body {{ flex: 1; }}
.card-body h3 {{ font-size: 17px; font-weight: 600; margin-bottom: 4px; }}
.card-body p {{ font-size: 13px; color: var(--text2); line-height: 1.5; }}
.card-meta {{ font-size: 11px; color: #555; margin-top: 6px; }}
.card-arrow {{ font-size: 22px; color: var(--text2); flex-shrink: 0; transition: transform 0.2s; }}
.card:hover .card-arrow {{ transform: translateX(4px); color: var(--accent); }}
footer {{ text-align: center; margin-top: 60px; color: var(--text2); font-size: 12px; }}
footer a {{ color: #818cf8; text-decoration: none; }}
</style>
</head>
<body>
<div class="container">
    <div class="logo">Ad Tech Intelligence</div>
    <h1>Dashboard <span>Hub</span></h1>
    <p class="subtitle">
        Decision-support tools for ad tech product leaders building exchanges and DSPs.
        Content is auto-generated from RSS feeds, SEC filings, and curated financial data.
    </p>
    <div class="cards">
        {cards_html}
    </div>
    <footer>
        Ad Tech Intelligence Hub &middot; Generated with Python &middot; 
        <a href="https://github.com">Source</a>
    </footer>
</div>
</body>
</html>"""


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"\n  Ad Tech Intelligence Hub")
        print(f"  http://localhost:{PORT}")
        print(f"  Serving from: {OUTPUT_DIR}")
        print(f"  Press Ctrl+C to stop\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")
