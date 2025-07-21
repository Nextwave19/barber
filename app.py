import os
import smtplib
import requests
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from email.message import EmailMessage
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_secret")

# תמחור שירותים
services_prices = {
    "Men's Haircut": 80,
    "Women's Haircut": 120,
    "Blow Dry": 70,
    "Color": 250
}

# הגדרת לוח זמינות
free_slots = {}
def init_free_slots():
    today = datetime.today()
    times = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
             "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00"]
    for i in range(7):
        date_str = (today + timedelta(days=i)).strftime("%d/%m")
        free_slots[date_str] = times.copy()
init_free_slots()

chat_history = []

# הגנה לדף אדמין
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_admin(*args, **kwargs):
        if session.get('username') != ADMIN_USERNAME:
            return "Unauthorized", 403
        return f(*args, **kwargs)
    return decorated_admin

@app.route("/")
def index():
    return render_template("index.html", username=session.get("username"), is_admin=session.get("username") == ADMIN_USERNAME)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == ADMIN_USERNAME:
            if password == ADMIN_PASSWORD:
                session['username'] = username
                return redirect(url_for("admin_command"))
            else:
                return render_template("login.html", error="Incorrect admin password")
        else:
            session['username'] = username
            return redirect(url_for("index"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("index"))

@app.route("/admin-command")
@admin_required
def admin_command():
    return render_template("admin_command.html", username=session.get("username"))

@app.route("/availability")
def availability():
    return jsonify(free_slots)

@app.route("/book", methods=["POST"])
def book():
    data = request.get_json()
    name = data.get("name")
    phone = data.get("phone")
    date = data.get("date")
    time = data.get("time")
    service = data.get("service")

    if not all([name, phone, date, time, service]):
        return jsonify({"error": "Missing fields"}), 400

    if date not in free_slots or time not in free_slots[date]:
        return jsonify({"error": "No availability at that time."}), 400

    price = services_prices.get(service)
    if not price:
        return jsonify({"error": "Unknown service."}), 400

    free_slots[date].remove(time)
    try:
        send_email(name, phone, date, time, service, price)
    except Exception as e:
        print("Error sending email:", e)

    return jsonify({"message": f"Appointment booked for {date} at {time} for {service} ({price}₪)."})

@app.route("/ask", methods=["POST"])
def ask():
    global chat_history
    data = request.get_json()
    user_message = data.get("message", "")

    chat_history.append({"role": "user", "content": user_message})
    if len(chat_history) > 11:
        chat_history = chat_history[-11:]

    messages = [{"role": "system", "content": "You are HairBossBot – a friendly, helpful assistant for a modern hair salon. Help users book appointments, explain services, and answer politely."}] + chat_history

    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
    if not GITHUB_TOKEN:
        return jsonify({"error": "Missing GitHub API token"}), 500

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-4.1",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 100
    }

    try:
        response = requests.post(
            "https://models.github.ai/inference/v1/chat/completions",
            headers=headers, json=payload)
        response.raise_for_status()
        output = response.json()
        answer = output["choices"][0]["message"]["content"].strip()
        chat_history.append({"role": "assistant", "content": answer})
        if len(chat_history) > 11:
            chat_history = chat_history[-11:]
        return jsonify({"answer": answer})
    except Exception as e:
        print("Error calling GitHub AI API:", e)
        return jsonify({"error": str(e)}), 500

def send_email(name, phone, date, time, service, price):
    msg = EmailMessage()
    msg.set_content(f"""
New appointment at HairBoss:
Name: {name}
Phone: {phone}
Date: {date}
Time: {time}
Service: {service}
Price: {price}₪
""")
    msg['Subject'] = f'New Appointment - {name}'
    msg['From'] = 'nextwaveaiandweb@gmail.com'
    msg['To'] = 'nextwaveaiandweb@gmail.com'

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login('nextwaveaiandweb@gmail.com', 'vmhb kmke ptlk kdzs')
        server.send_message(msg)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print("Failed to send email:", e)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
