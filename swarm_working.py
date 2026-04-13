#!/usr/bin/env python3
import os, sys, json, sqlite3, subprocess, time, threading, urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# Load Stripe
key_file = os.path.expanduser("~/.swarm/.env")
if os.path.exists(key_file):
    with open(key_file) as f:
        for line in f:
            if "STRIPE_SECRET_KEY" in line:
                STRIPE_KEY = line.split("=")[1].strip()
    os.environ['STRIPE_SECRET_KEY'] = STRIPE_KEY
    import stripe
    stripe.api_key = STRIPE_KEY
    print("Stripe loaded")
else:
    STRIPE_KEY = None
    print("No Stripe key")

CITIES = ["New York","Los Angeles","Chicago","Houston","Phoenix","Miami","Atlanta","Seattle","Denver","Boston"]

def discover_niches(city):
    try:
        prompt = f"List 5 urgent home services in {city} people pay $200+ for. Format: 'service|price'"
        result = subprocess.run(['ollama', 'run', 'llama3.2', prompt], capture_output=True, text=True, timeout=30)
        niches = []
        for line in result.stdout.strip().split('\n'):
            if '|' in line:
                parts = line.split('|')
                niches.append({'niche': parts[0].strip(), 'price': int(parts[1]) if parts[1].isdigit() else 300})
        return niches if niches else [{'niche': 'plumber', 'price': 350}]
    except:
        return [{'niche': 'plumber', 'price': 350}]

def build_page(city, niche, price):
    html = f'<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Emergency {niche} {city}</title><style>body{{font-family:Arial;padding:20px;max-width:600px;margin:auto}} input,textarea{{width:100%;padding:10px;margin:5px 0}} button{{background:#ff6600;color:white;padding:15px;width:100%;border:none}}</style></head><body><h1>Emergency {niche} in {city}</h1><p>Fixed price: ${price}</p><form method="POST"><input name="name" placeholder="Your name" required><input name="phone" placeholder="Phone number" required><textarea name="problem" placeholder="Describe your emergency" required></textarea><button>GET HELP NOW</button></form></body></html>'
    filename = f"{city}_{niche.replace(' ', '_')}.html"
    os.makedirs("pages", exist_ok=True)
    with open(f"pages/{filename}", "w") as f:
        f.write(html)
    return filename

def process_lead(data):
    if not STRIPE_KEY:
        return False
    phone = data.get('phone', '')
    problem = data.get('problem', '')
    try:
        urgent = subprocess.run(['ollama', 'run', 'llama3.2', f"Is this urgent? Reply yes or no: {problem}"],
                               capture_output=True, text=True, timeout=10)
        if 'yes' in urgent.stdout.lower():
            payment = stripe.PaymentIntent.create(amount=5000, currency='usd', payment_method_types=['card'])
            conn = sqlite3.connect('money.db')
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS earnings (id INTEGER PRIMARY KEY, amount REAL, phone TEXT, created_at TIMESTAMP)")
            c.execute("INSERT INTO earnings (amount, phone, created_at) VALUES (?, ?, ?)", (50, phone, datetime.now()))
            conn.commit()
            conn.close()
            print(f"CHARGED $50 - {phone}")
            return True
    except Exception as e:
        print(f"Charge failed: {e}")
    return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<h2>Swarm Active</h2>")
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        data = urllib.parse.parse_qs(self.rfile.read(length).decode())
        lead = {k: v[0] for k, v in data.items()}
        process_lead(lead)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Request received</h2>")
    def log_message(self, format, *args):
        pass

print("Starting web server on port 8000...")
server = port = int(os.environ.get('PORT', 8000))
server = HTTPServer(('0.0.0.0', port), Handler)

print("SWARM ONLINE")
print("Running forever...")

# Build initial pages
for city in CITIES:
    niches = discover_niches(city)
    for n in niches:
        build_page(city, n['niche'], n['price'])
        print(f"  {city}: {n['niche']} (${n['price']})")

server.serve_forever()
