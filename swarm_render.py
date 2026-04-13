#!/usr/bin/env python3
import os, sqlite3, urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import stripe

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Miami", "Atlanta", "Seattle", "Denver", "Boston"]

def build_pages():
    os.makedirs("pages", exist_ok=True)
    for city in CITIES:
        html = f'''<!DOCTYPE html>
<html>
<head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Emergency Plumber {city}</title>
<style>
body{{font-family:Arial;padding:20px;max-width:600px;margin:auto}}
input,textarea{{width:100%;padding:10px;margin:5px 0}}
button{{background:#ff6600;color:white;padding:15px;width:100%;border:none}}
</style>
</head>
<body>
<h1>Emergency Plumber in {city}</h1>
<p>Fixed price: $50</p>
<form action="/submit" method="POST">
<input name="name" placeholder="Your name" required>
<input name="phone" placeholder="Phone number" required>
<textarea name="problem" placeholder="Describe your emergency" required></textarea>
<button>GET HELP NOW</button>
</form>
</body>
</html>'''
        with open(f"pages/{city}.html", "w") as f:
            f.write(html)
    with open("pages/index.html", "w") as f:
        f.write("<h1>Emergency Services</h1><ul>")
        for city in CITIES:
            f.write(f'<li><a href="{city}.html">{city}</a></li>')
        f.write("</ul>")
    print("Built pages")

def process_lead(data):
    phone = data.get('phone', [''])[0]
    if phone:
        try:
            payment = stripe.PaymentIntent.create(
                amount=5000,
                currency='usd',
                payment_method_types=['card'],
                description=f"Lead from {phone}"
            )
            conn = sqlite3.connect('money.db')
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS earnings (id INTEGER PRIMARY KEY, amount REAL, phone TEXT, created_at TIMESTAMP)")
            c.execute("INSERT INTO earnings (amount, phone, created_at) VALUES (?, ?, ?)", (50, phone, datetime.now()))
            conn.commit()
            conn.close()
            print("CHARGED $50 - " + phone)
            return True
        except Exception as e:
            print("Charge failed: " + str(e))
    return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h2>Swarm Active</h2><p>Go to <a href='/pages/'>/pages/</a></p>")
            return
        
        if self.path == '/pages/':
            self.path = '/pages/index.html'
        
        try:
            if self.path.startswith('/pages/'):
                filepath = self.path[1:]  # Remove leading slash
                if os.path.isdir(filepath):
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not Found")
                    return
                with open(filepath, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not Found")
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        if self.path == '/submit':
            length = int(self.headers['Content-Length'])
            data = urllib.parse.parse_qs(self.rfile.read(length).decode())
            process_lead(data)
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h2>Request received</h2><p>A specialist will call you.</p><a href='/pages/'>Back</a>")

    def log_message(self, format, *args):
        print(f"{datetime.now()} {args}")

build_pages()
port = int(os.environ.get('PORT', 8000))
print(f"Swarm starting on port {port}")
server = HTTPServer(('0.0.0.0', port), Handler)
print("Swarm is LIVE")
server.serve_forever()
