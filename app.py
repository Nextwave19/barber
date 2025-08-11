import os
import requests
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template as original_render_template, redirect, session, g
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret")

# תיקיות לשמירת קבצי JSON אישיים לכל משתמש
WEEKLY_SCHEDULE_DIR = "business_schedules"  # תיקייה לשגרות השבועיות של כל המשתמשים
OVERRIDES_DIR = "business_overrides"        # תיקייה לשינויים חד-פעמיים לכל משתמש
APPOINTMENTS_DIR = "business_appointments" # תיקייה להזמנות לכל משתמש
BOT_KNOWLEDGE_FILE = "bot_knowledge.txt"   # ידע משותף (אפשר להרחיב בעתיד)

# שירותים ומחירים - נניח שזה אחיד לכל המשתמשים, או אפשר לשנות בעתיד
services_prices = {
    "Men's Haircut": 80,
    "Women's Haircut": 120,
    "Blow Dry": 70,
    "Color": 250
}

# קובץ משתמשים עם סיסמאות, שמות משתמשים ועסקים
def load_users():
    if not os.path.exists("business_users.json"):
        return []
    with open("business_users.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("users", [])

users_data = load_users()

# -- פונקציות ניהול קבצי JSON אישיים לכל משתמש ---

def get_user_files(username):
    """
    מחזיר את הנתיבים לקבצי JSON האישיים של המשתמש
    יוצר תיקיות במידת הצורך
    """
    # צור תיקיות אם לא קיימות
    os.makedirs(WEEKLY_SCHEDULE_DIR, exist_ok=True)
    os.makedirs(OVERRIDES_DIR, exist_ok=True)
    os.makedirs(APPOINTMENTS_DIR, exist_ok=True)

    weekly_schedule_file = os.path.join(WEEKLY_SCHEDULE_DIR, f"{username}_weekly_schedule.json")
    overrides_file = os.path.join(OVERRIDES_DIR, f"{username}_overrides.json")
    appointments_file = os.path.join(APPOINTMENTS_DIR, f"{username}_appointments.json")

    # אם הקבצים לא קיימים, צור קבצי JSON ריקים ברירת מחדל
    if not os.path.exists(weekly_schedule_file):
        with open(weekly_schedule_file, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    if not os.path.exists(overrides_file):
        with open(overrides_file, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    if not os.path.exists(appointments_file):
        with open(appointments_file, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

    return weekly_schedule_file, overrides_file, appointments_file

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_text(filename):
    if not os.path.exists(filename):
        return ""
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()

def save_text(filename, content):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content.strip())

def load_json_with_default(filename, default_filename=None):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    elif default_filename and os.path.exists(default_filename):
        with open(default_filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        save_json(filename, data)
        return data
    else:
        return {}


# --- פונקציות עזר לניהול הזמנות ושעות ---

def load_appointments(username):
    _, _, appointments_file = get_user_files(username)
    return load_json(appointments_file)

def save_appointments(username, data):
    _, _, appointments_file = get_user_files(username)
    save_json(appointments_file, data)

def load_weekly_schedule(username):
    weekly_schedule_file, _, _ = get_user_files(username)
    return load_json(weekly_schedule_file)

def save_weekly_schedule(username, data):
    weekly_schedule_file, _, _ = get_user_files(username)
    save_json(weekly_schedule_file, data)

def load_overrides(username):
    _, overrides_file, _ = get_user_files(username)
    return load_json(overrides_file)

def save_overrides(username, data):
    _, overrides_file, _ = get_user_files(username)
    save_json(overrides_file, data)

# פונקציה שמוציאה את השעות התפוסות מתוך הפגישות
def get_booked_times(appointments):
    booked = {}
    for date, apps_list in appointments.items():
        times = []
        for app in apps_list:
            time = app.get('time')  # הנחה שמפתח הזמן נקרא 'time'
            if time:
                times.append(time)
        booked[date] = times
    return booked

# --- יצירת רשימת שעות שבועית עם שינויים ---

def get_source(t, scheduled, added, removed, edits, disabled_day, booked_times):
    if t in booked_times:
        return "booked"          # אדום - תפוס ע"י לקוח
    for edit in edits:
        if t == edit['to']:
            return "edited"      # כחול - ערוך
    if t in added and t not in scheduled:
        return "added"           # צהוב - חדש
    if t in scheduled and (t in removed or disabled_day):
        return "disabled"        # אפור - מושבת ע"י אדמין
    return "base"                # ירוק - בסיסי

def generate_week_slots(username, with_sources=False):
    weekly_schedule = load_weekly_schedule(username)
    overrides = load_overrides(username)
    appointments = load_appointments(username)
    bookings = get_booked_times(appointments)
    today = datetime.today()
    week_slots = {}
    heb_days = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]

    for i in range(7):
        current_date = today + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        weekday = current_date.weekday()
        day_name = heb_days[weekday]

        day_key = str(weekday)
        scheduled = weekly_schedule.get(day_key, [])
        override = overrides.get(date_str, {"add": [], "remove": [], "edit": []})
        added = override.get("add", [])
        removed = override.get("remove", [])
        edits = override.get("edit", [])
        disabled_day = removed == ["__all__"]

        # השעות שכבר מוזמנות בתאריך הזה מתוך appointments.json
        booked_times = bookings.get(date_str, [])

        edited_to_times = [edit['to'] for edit in edits]
        edited_from_times = [edit['from'] for edit in edits]

        all_times = sorted(set(scheduled + added + edited_to_times))

        final_times = []
        for t in all_times:
            if t in edited_to_times:
                if with_sources:
                    final_times.append({"time": t, "available": True, "source": "edited"})
                else:
                    final_times.append({"time": t, "available": True})
                continue

            if t in edited_from_times:
                continue

            available = not (disabled_day or t in removed or t in booked_times)
            if with_sources:
                source = get_source(t, scheduled, added, removed, edits, disabled_day, booked_times)
                final_times.append({"time": t, "available": available, "source": source})
            else:
                if available:
                    final_times.append({"time": t, "available": True})

        week_slots[date_str] = {"day_name": day_name, "times": final_times}

    return week_slots


def is_slot_available(username, date, time):
    week_slots = generate_week_slots(username)
    day_info = week_slots.get(date)
    if not day_info:
        return False
    for t in day_info["times"]:
        if t["time"] == time and t.get("available", True):
            return True
    return False

# --- לפני כל בקשה - העברת session ל-g ---

@app.before_request
def before_request():
    g.username = session.get('username')
    # אין צורך ב-is_admin כי כולם בעלי עסקים עצמאים
    # g.is_admin = session.get('is_admin')
    g.business = session.get('business')

# --- החלפת render_template ---

def render_template(template_name_or_list, **context):
    context['business'] = g.get('business')
    context['username'] = g.get('username')
    return original_render_template(template_name_or_list, **context)

# --- התחברות ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = next((u for u in users_data if u["username"] == username and u["password"] == password), None)
        if user:
            session["username"] = username
            session["business"] = user.get("business", "")
            # סמן שכנראה בעל עסק
            session["is_admin"] = True
            return redirect("/")
        else:
            # flash("שם משתמש או סיסמה שגויים")
            return render_template("login.html", error="שם משתמש או סיסמה שגויים")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# --- ניהול שגרה שבועית ---

@app.route("/weekly_schedule", methods=["POST"])
def update_weekly_schedule():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    action = data.get("action")
    day_key = data.get("day_key")
    time = data.get("time")
    new_time = data.get("new_time")

    username = g.username
    if not username:
        return jsonify({"error": "Unauthorized"}), 403

    if day_key not in [str(i) for i in range(7)]:
        return jsonify({"error": "Invalid day key"}), 400

    weekly_schedule = load_weekly_schedule(username)

    if action == "enable_day":
        if day_key not in weekly_schedule:
            weekly_schedule[day_key] = []
        save_weekly_schedule(username, weekly_schedule)
        return jsonify({"success": True})

    if action == "disable_day":
        weekly_schedule[day_key] = []
        save_weekly_schedule(username, weekly_schedule)
        return jsonify({"success": True})

    day_times = weekly_schedule.get(day_key, [])

    if action == "add" and time:
        if time not in day_times:
            day_times.append(time)
            day_times.sort()
            weekly_schedule[day_key] = day_times
    elif action == "remove" and time:
        if time in day_times:
            day_times.remove(time)
            weekly_schedule[day_key] = day_times
    elif action == "edit" and time and new_time:
        if time in day_times:
            day_times.remove(time)
            if new_time not in day_times:
                day_times.append(new_time)
                day_times.sort()
            weekly_schedule[day_key] = day_times
    else:
        return jsonify({"error": "Invalid action or missing time"}), 400

    save_weekly_schedule(username, weekly_schedule)
    return jsonify({"message": "Weekly schedule updated", "weekly_schedule": weekly_schedule})

@app.route("/weekly_toggle_day", methods=["POST"])
def toggle_weekly_day():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    day_key = data.get("day_key")
    enabled = data.get("enabled")

    username = g.username
    if not username:
        return jsonify({"error": "Unauthorized"}), 403

    if day_key not in [str(i) for i in range(7)]:
        return jsonify({"error": "Invalid day key"}), 400

    weekly_schedule = load_weekly_schedule(username)
    weekly_schedule[day_key] = [] if not enabled else weekly_schedule.get(day_key, [])
    save_weekly_schedule(username, weekly_schedule)

    return jsonify({"message": "Day updated", "weekly_schedule": weekly_schedule})

# --- ניהול שינויים חד פעמיים (overrides) ---

@app.route("/overrides", methods=["POST"])
def update_overrides():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    action = data.get("action")
    date = data.get("date")
    time = data.get("time")
    new_time = data.get("new_time")

    username = g.username
    if not username:
        return jsonify({"error": "Unauthorized"}), 403

    overrides = load_overrides(username)

    if date not in overrides:
        overrides[date] = {"add": [], "remove": [], "edit": []}

    if action == "remove_many":
        times = data.get("times", [])
        for t in times:
            if t not in overrides[date]["remove"]:
                overrides[date]["remove"].append(t)
            if t in overrides[date]["add"]:
                overrides[date]["add"].remove(t)
        save_overrides(username, overrides)
        return jsonify({"message": "Multiple times removed", "overrides": overrides})

    elif action == "add" and time:
        if time not in overrides[date]["add"]:
            overrides[date]["add"].append(time)
        if time in overrides[date]["remove"]:
            overrides[date]["remove"].remove(time)
        save_overrides(username, overrides)
        return jsonify({"message": "Time added", "overrides": overrides})

    elif action == "remove" and time:
        if time not in overrides[date]["remove"]:
            overrides[date]["remove"].append(time)
        if time in overrides[date]["add"]:
            overrides[date]["add"].remove(time)
        if "edit" in overrides[date]:
            overrides[date]["edit"] = [
                e for e in overrides[date]["edit"] if e.get("from") != time and e.get("to") != time
            ]
            if not overrides[date]["edit"]:
                overrides[date].pop("edit", None)
        save_overrides(username, overrides)
        return jsonify({"message": "Time removed", "overrides": overrides})

    elif action == "edit" and time and new_time:
        if time == new_time:
            return jsonify({"message": "No changes made"})

        if "edit" not in overrides[date]:
            overrides[date]["edit"] = []

        overrides[date]["edit"] = [
            item for item in overrides[date]["edit"] if item.get("from") != time
        ]

        overrides[date]["edit"].append({
            "from": time,
            "to": new_time
        })

        if "remove" not in overrides[date]:
            overrides[date]["remove"] = []
        if time not in overrides[date]["remove"]:
            overrides[date]["remove"].append(time)

        if "add" not in overrides[date]:
            overrides[date]["add"] = []
        if new_time not in overrides[date]["add"]:
            overrides[date]["add"].append(new_time)

        save_overrides(username, overrides)
        return jsonify({"message": "Time edited", "overrides": overrides})

    elif action == "clear" and date:
        if date in overrides:
            overrides.pop(date)
        save_overrides(username, overrides)
        return jsonify({"message": "Day overrides cleared", "overrides": overrides})

    elif action == "disable_day" and date:
        overrides[date] = {"add": [], "remove": ["__all__"]}
        save_overrides(username, overrides)
        return jsonify({"message": "Day disabled", "overrides": overrides})

    elif action == "revert" and date and time:
        if date in overrides:
            if "add" in overrides[date] and time in overrides[date]["add"]:
                overrides[date]["add"].remove(time)

            if "remove" in overrides[date] and time in overrides[date]["remove"]:
                overrides[date]["remove"].remove(time)

            if "edit" in overrides[date]:
                overrides[date]["edit"] = [
                    e for e in overrides[date]["edit"] if e.get("to") != time and e.get("from") != time
                ]
                if not overrides[date]["edit"]:
                    overrides[date].pop("edit", None)

            if not overrides[date].get("add") and not overrides[date].get("remove") and not overrides[date].get("edit"):
                overrides.pop(date)

        save_overrides(username, overrides)
        return jsonify({"message": "Time reverted", "overrides": overrides})

    else:
        return jsonify({"error": "Invalid action or missing parameters"}), 400

@app.route("/overrides_toggle_day", methods=["POST"])
def toggle_override_day():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    date = data.get("date")
    enabled = data.get("enabled")

    username = g.username
    if not username:
        return jsonify({"error": "Unauthorized"}), 403

    overrides = load_overrides(username)

    if not enabled:
        overrides[date] = {"add": [], "remove": ["__all__"]}
    else:
        if date in overrides and overrides[date].get("remove") == ["__all__"]:
            overrides.pop(date)

    save_overrides(username, overrides)
    return jsonify({"message": "Day override toggled", "overrides": overrides})

# --- ניהול הזמנות ---

@app.route("/book", methods=["POST"])
def book_appointment():
    data = request.get_json()
    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    date = data.get("date", "").strip()
    time = data.get("time", "").strip()
    service = data.get("service", "").strip()

    username = g.username
    if not username:
        return jsonify({"error": "Unauthorized"}), 403

    if not all([name, phone, date, time, service]):
        return jsonify({"error": "Missing fields"}), 400

    if service not in services_prices:
        return jsonify({"error": "Unknown service"}), 400

    if not is_slot_available(username, date, time):
        return jsonify({"error": "This time slot is not available"}), 400

    appointments = load_appointments(username)
    date_appointments = appointments.get(date, [])

    for appt in date_appointments:
        if appt["time"] == time:
            return jsonify({"error": "This time slot is already booked"}), 400

    appointment = {
        "name": name,
        "phone": phone,
        "time": time,
        "service": service,
        "price": services_prices[service]
    }
    date_appointments.append(appointment)
    appointments[date] = date_appointments
    save_appointments(username, appointments)

    overrides = load_overrides(username)
    if date not in overrides:
        overrides[date] = {"add": [], "remove": [], "edit": [], "booked": []}
    elif "booked" not in overrides[date]:
        overrides[date]["booked"] = []

    overrides[date]["booked"].append({
        "time": time,
        "name": name,
        "phone": phone,
        "service": service
    })

    if time not in overrides[date]["remove"]:
        overrides[date]["remove"].append(time)
    if time in overrides[date]["add"]:
        overrides[date]["add"].remove(time)

    save_overrides(username, overrides)

    try:
        send_email(name, phone, date, time, service, services_prices[service])
    except Exception as e:
        print("Error sending email:", e)

    return jsonify({
        "message": f"Appointment booked for {date} at {time} for {service}.",
        "date": date,
        "time": time,
        "service": service,
        "can_cancel": True,
        "cancel_endpoint": "/cancel_appointment"
    })

@app.route('/cancel_appointment', methods=['POST'])
def cancel_appointment():
    data = request.get_json()
    date = data.get('date')
    time = data.get('time')
    name = data.get('name')
    phone = data.get('phone')

    username = g.username
    if not username:
        return jsonify({"error": "Unauthorized"}), 403

    appointments = load_appointments(username)
    day_appointments = appointments.get(date, [])

    new_day_appointments = [
        appt for appt in day_appointments
        if not (appt['time'] == time and appt['name'] == name and appt['phone'] == phone)
    ]

    if len(new_day_appointments) == len(day_appointments):
        return jsonify({'error': 'Appointment not found'}), 404

    appointments[date] = new_day_appointments
    save_appointments(username, appointments)

    overrides = load_overrides(username)

    if date not in overrides:
        overrides[date] = {"add": [], "remove": [], "edit": []}

    if time in overrides[date].get("remove", []):
        overrides[date]["remove"].remove(time)

    if time not in overrides[date].get("add", []):
        overrides[date]["add"].append(time)

    save_overrides(username, overrides)

    return jsonify({'message': f'Appointment on {date} at {time} canceled successfully.'})

# --- שליחת אימייל ---

def send_email(name, phone, date, time, service, price):
    EMAIL_USER = os.environ.get("EMAIL_USER")
    EMAIL_PASS = os.environ.get("EMAIL_PASS")
    if not EMAIL_USER or not EMAIL_PASS:
        print("Missing EMAIL_USER or EMAIL_PASS environment variables")
        return

    msg = EmailMessage()
    msg.set_content(f"""
New appointment booked:

Name: {name}
Phone: {phone}
Date: {date}
Time: {time}
Service: {service}
Price: {price}₪
""")
    msg['Subject'] = f'New Appointment - {name}'
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_USER

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print("Failed to send email:", e)

# --- דף הצגת זמינות שבועית (מנהל בלבד) ---

@app.route("/availability")
def availability():
    username = g.username
    if not username:
        return jsonify({"error": "Unauthorized"}), 403
    week_slots = generate_week_slots(username, with_sources=True)
    return jsonify(week_slots)

# --- דף הבית ---

@app.route("/")
def index():
    if "username" not in session:
        return redirect("/login")

    username = session["username"]
    week_slots = generate_week_slots(username, with_sources=True)
    return render_template("index.html", week_slots=week_slots, services=services_prices)

# --- ניהול טקסט ידע של הבוט ---

@app.route("/bot_knowledge", methods=["GET", "POST"])
def bot_knowledge():
    if not session.get("is_admin"):
        return redirect("/login")

    if request.method == "POST":
        content = request.form.get("content", "")
        save_text(BOT_KNOWLEDGE_FILE, content)
        return redirect("/main_admin")

    content = load_text(BOT_KNOWLEDGE_FILE)
    return render_template("bot_knowledge.html", content=content)

# --- API - שאלות לבוט ---

@app.route("/ask", methods=["POST"])
def ask_bot():
    data = request.get_json()
    question = data.get("message", "").strip()

    if not question:
        return jsonify({"answer": "אנא כתוב שאלה."})

    knowledge_text = load_text(BOT_KNOWLEDGE_FILE)

    messages = [
        {"role": "system", "content": "You are a helpful assistant for a hair salon booking system."},
        {"role": "system", "content": f"Additional info: {knowledge_text}"},
        {"role": "user", "content": question}
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
        "max_tokens": 200
    }

    try:
        response = requests.post(
            "https://models.github.ai/inference/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        output = response.json()
        answer = output["choices"][0]["message"]["content"].strip()
        return jsonify({"answer": answer})
    except Exception as e:
        print("Error calling GitHub AI API:", e)
        fallback_answer = "מצטער, לא הצלחתי לעבד את השאלה כרגע."
        return jsonify({"answer": fallback_answer})

# --- הפעלת השרת ---

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
