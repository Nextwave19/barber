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

def hebrew_day_name(date_obj):
    days = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון']
    return days[date_obj.weekday()]

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "default_secret_key"

# שירותים ומחירים
services_prices = {
    "Men's Haircut": 80,
    "Women's Haircut": 120,
    "Blow Dry": 70,
    "Color": 250
}

# אתחול תאריכים זמינים
def init_free_slots():
    today = datetime.today()
    free_slots = {}

    # שעות קבועות לכל יום, כולל שבת
    times = ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30",
             "11:00", "11:30", "12:00", "12:30", "13:00", "13:30",
             "14:00", "14:30", "15:00", "15:30", "16:00", "16:30",
             "17:00", "17:30", "18:00", "18:30", "19:00", "19:30"]

    for i in range(7):
        date_obj = today + timedelta(days=i)
        day_name = hebrew_day_name(date_obj)
        date_str = date_obj.strftime("%d/%m")
        key = f"{day_name} - {date_str}"
        free_slots[key] = times.copy()

    return free_slots

# בדיקת עדכון תאריכים אוטומטי
def update_free_slots_daily():
    today = datetime.today()
    today_str = today.strftime("%d/%m")
    free_slots = load_json("free_slots.json")

    if not free_slots or today_str not in free_slots:
        free_slots = init_free_slots()
        save_json("free_slots.json", free_slots)
    return free_slots

disabled_slots = defaultdict(list)
chat_history = []
custom_knowledge = []

# --- דפי HTML ---

@app.route("/")
def index():
    return render_template("index.html")
    
@app.route("/login", methods=['GET', 'POST'])
def login():
    error = None
    admin_user = os.environ.get('ADMIN_USERNAME')
    admin_password = os.environ.get('ADMIN_PASSWORD') 
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

        # משתמש רגיל - אין צורך בסיסמה
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

    # טען את כל הקבצים עם עדכון תאריכים
    free_slots = update_free_slots_daily()
    disabled_slots = load_json("disabled_slots.json")
    disabled_days = load_json("disabled_days.json")
    services_prices = load_json("services_prices.json")
    custom_knowledge = load_json("custom_knowledge.json")

    def format_date_key(date_str):
        try:
            date_obj = datetime.strptime(date_str, "%d/%m")
            return f"{hebrew_day_name(date_obj)} - {date_str}"
        except:
            return date_str

    if request.method == "POST":
        action = request.form.get("action")
        raw_date = request.form.get("date")
        hour = request.form.get("hour")
        date = format_date_key(raw_date)

        if action == "disable_slot":
            if date not in disabled_slots:
                disabled_slots[date] = []
            if hour not in disabled_slots[date]:
                disabled_slots[date].append(hour)
            save_json("disabled_slots.json", disabled_slots)

        elif action == "enable_slot":
            if date in disabled_slots and hour in disabled_slots[date]:
                disabled_slots[date].remove(hour)
                if not disabled_slots[date]:
                    del disabled_slots[date]
                save_json("disabled_slots.json", disabled_slots)

        elif action == "delete_slot":
            if date in free_slots and hour in free_slots[date]:
                free_slots[date].remove(hour)
                if not free_slots[date]:
                    del free_slots[date]
                save_json("free_slots.json", free_slots)
            if date in disabled_slots and hour in disabled_slots[date]:
                disabled_slots[date].remove(hour)
                if not disabled_slots[date]:
                    del disabled_slots[date]
                save_json("disabled_slots.json", disabled_slots)

        elif action == "add_slot":
            if date not in free_slots:
                free_slots[date] = []
            if hour not in free_slots[date]:
                free_slots[date].append(hour)
                free_slots[date].sort()
            save_json("free_slots.json", free_slots)

        elif action == "disable_day":
            if date not in disabled_days:
                disabled_days.append(date)
                save_json("disabled_days.json", disabled_days)

        elif action == "enable_day":
            if date in disabled_days:
                disabled_days.remove(date)
                save_json("disabled_days.json", disabled_days)

        return redirect("/admin_command")

    return render_template("admin_command.html",
                           free_slots=free_slots,
                           disabled_slots=disabled_slots,
                           services_prices=services_prices,
                           custom_knowledge=custom_knowledge,
                           disabled_days=disabled_days,
                           datetime_obj=datetime)

# --- API JSON ---

@app.route("/availability")
def availability():
    return jsonify(update_free_slots_daily())

@app.route("/book", methods=["POST"])
def book():
    data = request.get_json()
    name = data.get("name")
    phone = data.get("phone")
    date = data.get("date")
    time = data.get("time")
    service = data.get("service")

    free_slots = update_free_slots_daily()

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

    date = request.form.get("date")
    time = request.form.get("time")
    action = request.form.get("action")
    new_time = request.form.get("new_time")
    free_slots = update_free_slots_daily()

    if not date or not time or not action:
        return "Invalid input", 400

    if date not in free_slots:
        return "Invalid date", 400

    if action in ["remove", "delete"]:
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
    save_json("custom_knowledge.json", custom_knowledge)
    return redirect("/admin_command")

@app.route("/admin/update_slot", methods=["POST"])
def admin_update_slot():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    date = data.get("date")
    time = data.get("time")
    action = data.get("action")
    new_time = data.get("new_time")
    free_slots = update_free_slots_daily()

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
