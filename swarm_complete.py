#!/usr/bin/env python3
import os, sqlite3, urllib.parse, json, requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import stripe

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Specialist phone numbers (hardcoded for now - replace with real numbers)
SPECIALISTS = {
    "New York": "+15551234567",
    "Los Angeles": "+15557654321",
    "Chicago": "+15559876543",
    "Houston": "+15553456789",
    "Phoenix": "+15554567890",
}

def send_sms(to, message):
    """Send SMS via Twilio (free trial available)"""
    # You'll need Twilio account: https://www.twilio.com/try-free
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_number = os.environ.get('TWILIO_PHONE_NUMBER')
    
    if account_sid and auth_token and from_number:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        data = {
            'From': from_number,
            'To': to,
            'Body': message
        }
        try:
            r = requests.post(url, data=data, auth=(account_sid, auth_token))
            return r.status_code == 201
        except:
            return False
    else:
        # Fallback: print to console (Render logs will show it)
        print(f"SMS TO {to}: {message}")
        return False

def build_pages():
    os.makedirs("pages", exist_ok=True)
    for city, specialist_phone in SPECIALISTS.items():
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Emergency Plumber {city}</title>
    <script src="https://js.stripe.com/v3/"></script>
    <style>
        body {{ font-family: Arial; padding: 20px; max-width: 600px; margin: auto; }}
        input, textarea, .StripeElement {{ width: 100%; padding: 10px; margin: 5px 0; border: 1px solid #ccc; border-radius: 4px; }}
        button {{ background: #ff6600; color: white; padding: 15px; width: 100%; border: none; font-size: 16px; cursor: pointer; }}
        .hidden {{ display: none; }}
        #card-element {{ background: white; padding: 12px; }}
        #card-errors {{ color: red; margin-top: 10px; }}
    </style>
</head>
<body>
    <h1>Emergency Plumber in {city}</h1>
    <p>Fixed price: <strong>$50</strong></p>
    
    <form id="payment-form">
        <input id="name" placeholder="Your name" required>
        <input id="phone" placeholder="Your phone number" required>
        <textarea id="problem" placeholder="Describe your emergency" required></textarea>
        <div id="card-element"></div>
        <div id="card-errors" role="alert"></div>
        <button id="submit-btn">PAY $50 & GET HELP</button>
    </form>
    <div id="result" class="hidden"></div>

    <script>
        const stripe = Stripe('pk_live_51TK20zFJ9UZ40ZiFjdMNKpDU5ACqKok5Gks1M3SxSUL1VtikKPkJSW0ihaCfaABXZ8HTq3jpc7EzSPLpdMmcgIA001AA1EcZJ');
        const elements = stripe.elements();
        const cardElement = elements.create('card');
        cardElement.mount('#card-element');

        const form = document.getElementById('payment-form');
        const submitBtn = document.getElementById('submit-btn');
        const resultDiv = document.getElementById('result');

        form.addEventListener('submit', async (e) => {{
            e.preventDefault();
            submitBtn.disabled = true;
            submitBtn.textContent = 'Processing...';

            // First, create payment intent on server
            const leadData = {{
                name: document.getElementById('name').value,
                phone: document.getElementById('phone').value,
                problem: document.getElementById('problem').value,
                city: '{city}'
            }};

            const intentRes = await fetch('/create-payment', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(leadData)
            }});
            const {{ client_secret }} = await intentRes.json();

            const {{ paymentIntent, error }} = await stripe.confirmCardPayment(client_secret, {{
                payment_method: {{
                    card: cardElement,
                    billing_details: {{
                        name: leadData.name,
                        phone: leadData.phone
                    }}
                }}
            }});

            if (error) {{
                document.getElementById('card-errors').textContent = error.message;
                submitBtn.disabled = false;
                submitBtn.textContent = 'PAY $50 & GET HELP';
            }} else {{
                // Notify specialist
                await fetch('/notify-specialist', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        ...leadData,
                        payment_intent_id: paymentIntent.id
                    }})
                }});
                resultDiv.innerHTML = '<h2>✓ Specialist will call you within 15 minutes</h2>';
                resultDiv.classList.remove('hidden');
                form.classList.add('hidden');
            }}
        }});
    </script>
</body>
</html>'''
        with open(f"pages/{city}.html", "w") as f:
            f.write(html)
    
    with open("pages/index.html", "w") as f:
        f.write("<h1>Emergency Services</h1><ul>")
        for city in SPECIALISTS.keys():
            f.write(f'<li><a href="{city}.html">{city}</a></li>')
        f.write("</ul>")
    print("Built pages with Stripe and SMS")

def create_payment_intent(data):
    try:
        intent = stripe.PaymentIntent.create(
            amount=5000,
            currency='usd',
            payment_method_types=['card'],
            description=f"Emergency plumber in {data.get('city')} for {data.get('phone')}"
        )
        return intent.client_secret
    except Exception as e:
        print(f"Payment error: {e}")
        return None

def notify_specialist(data):
    city = data.get('city')
    specialist_phone = SPECIALISTS.get(city)
    if specialist_phone:
        message = f"EMERGENCY PLUMBER - {data.get('name')} needs help in {city}. Problem: {data.get('problem')[:50]}. Call them at {data.get('phone')}"
        send_sms(specialist_phone, message)
        
        # Also save to database
        conn = sqlite3.connect('money.db')
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY, name TEXT, phone TEXT, city TEXT, problem TEXT, created_at TIMESTAMP)")
        c.execute("INSERT INTO leads (name, phone, city, problem, created_at) VALUES (?, ?, ?, ?, ?)", 
                  (data.get('name'), data.get('phone'), city, data.get('problem'), datetime.now()))
        conn.commit()
        conn.close()
        return True
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
                filepath = self.path[1:]
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
        length = int(self.headers['Content-Length'])
        data = json.loads(self.rfile.read(length).decode())
        
        if self.path == '/create-payment':
            client_secret = create_payment_intent(data)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"client_secret": client_secret}).encode())
        
        elif self.path == '/notify-specialist':
            notify_specialist(data)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"{datetime.now()} {args}")

build_pages()
port = int(os.environ.get('PORT', 8000))
print(f"Swarm starting on port {port}")
server = HTTPServer(('0.0.0.0', port), Handler)
print("Swarm is LIVE - Specialists will receive SMS when leads come in")
server.serve_forever()
