import requests
from flask import Flask, request, jsonify, render_template, redirect, session
import json
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from collections import defaultdict

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def normalize_date(date_str):
    try:
        if "-" in date_str:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            dt = datetime.strptime(date_str, "%d/%m")
        day_name_hebrew = {
            "Sunday": "ראשון",
            "Monday": "שני",
            "Tuesday": "שלישי",
            "Wednesday": "רביעי",
            "Thursday": "חמישי",
            "Friday": "שישי",
            "Saturday": "שבת"
        }
        day_he = day_name_hebrew.get(dt.strftime("%A"), dt.strftime("%A"))
        formatted = dt.strftime("%d/%m")
        return formatted, day_he
    except:
        return date_str, ""

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "default_secret_key"

services_prices = {
    "Men's Haircut": 80,
    "Women's Haircut": 120,
    "Blow Dry": 70,
    "Color": 250
}

def init_free_slots():
    today = datetime.today()
    times = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
             "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00"]
    free_slots = {}
    for i in range(7):
        date_str = (today + timedelta(days=i)).strftime("%d/%m")
        free_slots[date_str] = times.copy()
    return free_slots

# יטען פעם ראשונה או יאתחל קבצים אם לא קיימים
if not os.path.exists("free_slots.json"):
    free_slots = init_free_slots()
    save_json("free_slots.json", free_slots)
else:
    free_slots = load_json("free_slots.json")

if not os.path.exists("disabled_slots.json"):
    disabled_slots = {}
    save_json("disabled_slots.json", disabled_slots)
else:
    disabled_slots = load_json("disabled_slots.json")

chat_history = []
custom_knowledge = []

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    error = None
    admin_user = os.environ.get('ADMIN_USERNAME')
    admin_password = os.environ.get('ADMIN_PASSWORD') or "1234"

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form.get('password', '')

        if not username:
            error = "יש להזין שם משתמש"
            return render_template('login.html', error=error, admin_user=admin_user)

        if username == admin_user:
            if password == admin_password:
                session['username'] = username
                session['is_admin'] = True
                return redirect('/admin_command')
            else:
                error = "סיסמה שגויה"
                return render_template('login.html', error=error, admin_user=admin_user)

        session['username'] = username
        session['is_admin'] = False
        return redirect('/')

    return render_template('login.html', error=error, admin_user=admin_user)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/admin_command", methods=["GET", "POST"])
def admin_command():
    if 'username' not in session or session['username'] != os.environ.get("ADMIN_USERNAME"):
        return redirect("/login")

    global free_slots, disabled_slots
    free_slots = load_json("free_slots.json")
    disabled_slots = load_json("disabled_slots.json")

    if request.method == "POST":
        action = request.form.get("action")
        date = request.form.get("date", "").strip()
        time = request.form.get("time", "").strip()
        day = request.form.get("day", "").strip()
        new_time = request.form.get("new_time", "").strip()

        if action == "delete":
            if date in free_slots and time in free_slots[date]:
                free_slots[date].remove(time)
                if not free_slots[date]:
                    del free_slots[date]
                save_json("free_slots.json", free_slots)
            if date in disabled_slots and time in disabled_slots[date]:
                disabled_slots[date].remove(time)
                if not disabled_slots[date]:
                    del disabled_slots[date]
                save_json("disabled_slots.json", disabled_slots)

        elif action == "disable":
            if date in free_slots and time in free_slots[date]:
                if date not in disabled_slots:
                    disabled_slots[date] = []
                if time not in disabled_slots[date]:
                    disabled_slots[date].append(time)
                    save_json("disabled_slots.json", disabled_slots)

        elif action == "edit" and new_time:
            if date in free_slots and time in free_slots[date]:
                free_slots[date].remove(time)
                free_slots[date].append(new_time)
                free_slots[date] = sorted(list(set(free_slots[date])))
                save_json("free_slots.json", free_slots)
            if date in disabled_slots and time in disabled_slots[date]:
                disabled_slots[date].remove(time)
                disabled_slots[date].append(new_time)
                disabled_slots[date] = sorted(list(set(disabled_slots[date])))
                save_json("disabled_slots.json", disabled_slots)

        elif action == "disable_day" and day:
            if day in free_slots:
                if day not in disabled_slots:
                    disabled_slots[day] = []
                for t in free_slots[day]:
                    if t not in disabled_slots[day]:
                        disabled_slots[day].append(t)
                save_json("disabled_slots.json", disabled_slots)

    day_names = {}
    for d in sorted(set(list(free_slots.keys()) + list(disabled_slots.keys()))):
        try:
            formatted, heb_day = normalize_date(d)
            day_names[formatted] = heb_day
        except:
            day_names[d] = d

    return render_template("admin_command.html",
                           free_slots=free_slots,
                           disabled_slots=disabled_slots,
                           day_names=day_names)

# --- API JSON ---

@app.route("/availability")
def availability():
    global free_slots
    free_slots = load_json("free_slots.json")
    return jsonify(free_slots)

@app.route("/book", methods=["POST"])
def book():
    global free_slots
    free_slots = load_json("free_slots.json")

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
    save_json("free_slots.json", free_slots)

    try:
        send_email(name, phone, date, time, service, price)
    except Exception as e:
        print("Error sending email:", e)

    return jsonify({"message": f"Appointment booked for {date} at {time} for {service} ({price}₪)."})

@app.route("/slot", methods=["POST"])
def update_slot():
    if not session.get("is_admin"):
        return redirect("/login")

    global free_slots
    free_slots = load_json("free_slots.json")

    date = request.form.get("date")
    time = request.form.get("time")
    action = request.form.get("action")
    new_time = request.form.get("new_time")

    if not date or not time or not action:
        return "Invalid input", 400

    if date not in free_slots:
        return "Invalid date", 400

    if action == "remove" or action == "delete":
        if time in free_slots[date]:
            free_slots[date].remove(time)

    elif action == "disable":
        if time in free_slots[date]:
            free_slots[date].remove(time)

    elif action == "enable":
        if time not in free_slots[date]:
            free_slots[date].append(time)
            free_slots[date].sort()

    elif action == "add":
        if time not in free_slots[date]:
            free_slots[date].append(time)
            free_slots[date].sort()

    elif action == "edit":
        if time in free_slots[date] and new_time:
            free_slots[date].remove(time)
            if new_time not in free_slots[date]:
                free_slots[date].append(new_time)
                free_slots[date].sort()

    save_json("free_slots.json", free_slots)
    return redirect("/admin_command")

@app.route("/bot-knowledge", methods=["POST"])
def update_bot_knowledge():
    if not session.get("is_admin"):
        return redirect("/login")
    action = request.form.get("action")
    content = request.form.get("content")
    if action == "add" and content:
        custom_knowledge.append(content.strip())
    elif action == "remove" and content:
        custom_knowledge[:] = [item for item in custom_knowledge if item != content.strip()]
    return redirect("/admin_command")

@app.route("/admin/update_slot", methods=["POST"])
def admin_update_slot():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 403

    global free_slots
    free_slots = load_json("free_slots.json")

    data = request.get_json()
    date = data.get("date")
    time = data.get("time")
    action = data.get("action")
    new_time = data.get("new_time")

    if date not in free_slots:
        return jsonify({"error": "Invalid date"}), 400

    if action == "disable":
        if time in free_slots[date]:
            free_slots[date].remove(time)
        save_json("free_slots.json", free_slots)
        return jsonify({"status": "disabled"})

    elif action == "enable":
        if time not in free_slots[date]:
            free_slots[date].append(time)
            free_slots[date].sort()
        save_json("free_slots.json", free_slots)
        return jsonify({"status": "enabled"})

    elif action == "delete":
        if time in free_slots[date]:
            free_slots[date].remove(time)
        save_json("free_slots.json", free_slots)
        return jsonify({"status": "deleted"})

    elif action == "add":
        if time not in free_slots[date]:
            free_slots[date].append(time)
            free_slots[date].sort()
        save_json("free_slots.json", free_slots)
        return jsonify({"status": "added"})

    elif action == "edit":
        if time in free_slots[date] and new_time:
            free_slots[date].remove(time)
            if new_time not in free_slots[date]:
                free_slots[date].append(new_time)
                free_slots[date].sort()
            save_json("free_slots.json", free_slots)
            return jsonify({"status": "edited", "new_time": new_time})

    return jsonify({"error": "Invalid action"}), 400


@app.route("/ask", methods=["POST"])
def ask():
    global chat_history
    data = request.get_json()
    user_message = data.get("message", "")

    chat_history.append({"role": "user", "content": user_message})
    if len(chat_history) > 11:
        chat_history = chat_history[-11:]

    messages = [
        {"role": "system", "content": "You are a helpful bot for booking appointments at a hair salon."},
        *[{"role": "system", "content": f"Additional info: {info}"} for info in custom_knowledge],
        *chat_history
    ]

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
