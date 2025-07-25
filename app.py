import requests
from flask import Flask, request, jsonify, render_template, redirect, session
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta

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
    times = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
             "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00"]
    free_slots = {}
    for i in range(7):
        date_str = (today + timedelta(days=i)).strftime("%d/%m")
        free_slots[date_str] = times.copy()
    return free_slots

free_slots = init_free_slots()
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

        # משתמש רגיל - אין צורך בסיסמה
        session['username'] = username
        session['is_admin'] = False
        return redirect('/')

    return render_template('login.html', error=error, admin_user=admin_user)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/admin_command")
def admin_command():
    if not session.get("is_admin"):
        return redirect("/login")
    return render_template(
        "admin_command.html",
        free_slots=free_slots,
        services_prices=services_prices,
        custom_knowledge=custom_knowledge
    )

# --- API JSON ---

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

@app.route("/slot", methods=["POST"])
def update_slot():
    if not session.get("is_admin"):
        return redirect("/login")
    date = request.form.get("date")
    time = request.form.get("time")
    action = request.form.get("action")

    if not date or not time or action not in ["remove", "add"]:
        return "Invalid input", 400

    if action == "remove":
        if time in free_slots.get(date, []):
            free_slots[date].remove(time)
    elif action == "add":
        if time not in free_slots.get(date, []):
            free_slots[date].append(time)
            free_slots[date].sort()
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

@app.route('/admin/update_slot', methods=['POST'])
def update_slot_admin():
    try:
        data = request.get_json()
        date = data.get('date')
        time = data.get('time')
        action = data.get('action')

        if not date or not time or not action:
            return jsonify({"error": "Missing required fields"}), 400

        if action == 'delete':
            if date in free_slots and time in free_slots[date]:
                free_slots[date].remove(time)
                if not free_slots[date]:
                    del free_slots[date]
        elif action == 'disable':
            if date in free_slots and time in free_slots[date]:
                if ' (כבוי)' not in time:
                    index = free_slots[date].index(time)
                    free_slots[date][index] = f"{time} (כבוי)"
        elif action == 'enable':
            if date in free_slots:
                updated_times = []
                for t in free_slots[date]:
                    if t.replace(" (כבוי)", "") == time:
                        updated_times.append(time)
                    else:
                        updated_times.append(t)
                free_slots[date] = updated_times
        else:
            return jsonify({"error": "Invalid action"}), 400

        save_slots()  # אם יש לך פונקציה כזו
        return jsonify({"status": "success"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
