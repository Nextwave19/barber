import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "devkey")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "adminpass")

# זמינות יומית לדוגמה
availability = {}
enabled_dates = []
bot_enabled = True

def generate_availability():
    availability.clear()
    enabled_dates.clear()
    today = datetime.now()
    for i in range(7):
        day = today + timedelta(days=i)
        date_str = day.strftime("%d/%m")
        times = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
                 "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00"]
        availability[date_str] = times[:]
        enabled_dates.append(date_str)

generate_availability()

appointments = []

# --- הגנת אדמין ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def is_admin():
    return session.get("logged_in")

# --- ראוטים ---

@app.route('/')
def index():
    return render_template("index.html", is_admin=is_admin())

@app.route('/availability')
def get_availability():
    filtered = {date: slots for date, slots in availability.items() if date in enabled_dates}
    return jsonify(filtered)

@app.route('/book', methods=['POST'])
def book():
    data = request.get_json()
    name = data.get("name")
    phone = data.get("phone")
    date = data.get("date")
    time = data.get("time")
    service = data.get("service")

    if not name or not phone or not date or not time or not service:
        return jsonify({"error": "Missing required fields"}), 400

    if time not in availability.get(date, []):
        return jsonify({"error": "Time slot not available"}), 400

    appointments.append({
        "name": name,
        "phone": phone,
        "date": date,
        "time": time,
        "service": service
    })

    availability[date].remove(time)
    return jsonify({"message": f"Appointment booked for {date} at {time}!"})

@app.route('/ask', methods=['POST'])
def ask_bot():
    if not bot_enabled:
        return jsonify({"answer": "The bot is currently disabled."})
    data = request.get_json()
    question = data.get("message", "").strip()
    if not question:
        return jsonify({"answer": "Please ask a question."})
    # תשובה לדוגמה (כאן אפשר להוסיף API אמיתי)
    return jsonify({"answer": f"I'm a helpful bot. You asked: {question}"})


# --- התחברות לאדמין ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for('index'))
        return "Invalid credentials", 401
    return '''
        <form method="post">
            <input name="username" placeholder="Username" />
            <input name="password" placeholder="Password" type="password" />
            <button type="submit">Login</button>
        </form>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("index"))

# --- Admin Commands ---
@app.route('/admin-command', methods=['POST'])
@login_required
def admin_command():
    global bot_enabled
    data = request.get_json()
    command = data.get("command")

    if command == "reset":
        generate_availability()
        return jsonify({"message": "Availability reset"})
    elif command == "disable_bot":
        bot_enabled = False
        return jsonify({"message": "Bot disabled"})
    elif command == "enable_bot":
        bot_enabled = True
        return jsonify({"message": "Bot enabled"})
    elif command == "shutdown":
        func = request.environ.get('werkzeug.server.shutdown')
        if func:
            func()
            return jsonify({"message": "Server shutting down..."})
        return jsonify({"error": "Shutdown not supported"}), 500
    return jsonify({"error": "Invalid command"}), 400


if __name__ == "__main__":
    app.run(debug=True)
