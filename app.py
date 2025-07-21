from flask import Flask, render_template, request, jsonify, redirect, session
from datetime import datetime, timedelta
import json
import os
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

DATA_FILE = 'appointments.json'

# הגדרות מהסביבה
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "1234")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# מצבים אדמיניים
booking_enabled = True
bot_enabled = True

# עוזר לטעינת נתונים
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({}, f)
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

# עוזר לשמירת נתונים
def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# עוזר ליצירת ימים עם זמינות
def get_available_days():
    data = load_data()
    days = {}
    today = datetime.now()
    for i in range(5):
        date = today + timedelta(days=i)
        date_str = date.strftime('%d/%m')
        if date_str not in data:
            data[date_str] = []
        taken = data[date_str]
        all_slots = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
                     "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00"]
        available = [slot for slot in all_slots if slot not in [appt["time"] for appt in taken]]
        days[date_str] = available
    save_data(data)
    return days

# דף ראשי
@app.route('/')
def index():
    return render_template('index.html', is_admin=session.get('is_admin', False),
                           bot_enabled=bot_enabled, booking_enabled=booking_enabled)

# דף התחברות
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session['is_admin'] = True
            return redirect('/admin-panel')
        else:
            return "Login failed", 403
    return '''
        <form method="post">
            <input name="username" placeholder="Username" required><br>
            <input name="password" type="password" placeholder="Password" required><br>
            <button type="submit">Login</button>
        </form>
    '''

# דף ליציאה
@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect('/')

# זמינות
@app.route('/availability')
def availability():
    if not booking_enabled:
        return jsonify({})
    return jsonify(get_available_days())

# שליחת בקשת הזמנה
@app.route('/book', methods=['POST'])
def book():
    if not booking_enabled:
        return jsonify({'error': 'Booking is disabled by admin.'})

    data = request.get_json()
    name = data.get("name")
    phone = data.get("phone")
    date = data.get("date")
    time = data.get("time")
    service = data.get("service")

    if not all([name, phone, date, time, service]):
        return jsonify({"error": "Missing data"})

    db = load_data()
    appointments = db.get(date, [])

    if any(appt["time"] == time for appt in appointments):
        return jsonify({"error": "This time is already booked"})

    appointments.append({"name": name, "phone": phone, "time": time, "service": service})
    db[date] = appointments
    save_data(db)

    # שליחת טלגרם אם אפשרי
    if BOT_TOKEN and CHAT_ID and bot_enabled:
        import requests
        msg = f"📅 New Appointment:\n👤 {name}\n📞 {phone}\n🕒 {date} {time}\n💇 {service}"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

    return jsonify({"message": "Appointment booked successfully!"})

# API של הבוט
@app.route('/ask', methods=['POST'])
def ask_bot():
    if not bot_enabled:
        return jsonify({"answer": "The bot is currently disabled."})
    message = request.json.get('message', '')
    if "hours" in message.lower():
        return jsonify({"answer": "We're open from 9:00 to 15:00 Sunday to Thursday."})
    elif "location" in message.lower():
        return jsonify({"answer": "We are located at HairBoss Street 123."})
    else:
        return jsonify({"answer": "I'm here to help! Try asking about hours or location."})

# דף אדמין
@app.route('/admin-panel')
def admin_panel():
    if not session.get('is_admin'):
        return "Access denied", 403
    return render_template("admin_command_panel.html")

# קומנד של אדמין
@app.route('/admin-command', methods=['POST'])
def admin_command():
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403

    global booking_enabled, bot_enabled

    data = request.get_json()
    command = data.get('command')

    if command == 'enable_booking':
        booking_enabled = True
        return jsonify({'message': 'Booking enabled'})
    elif command == 'disable_booking':
        booking_enabled = False
        return jsonify({'message': 'Booking disabled'})
    elif command == 'enable_bot':
        bot_enabled = True
        return jsonify({'message': 'Bot enabled'})
    elif command == 'disable_bot':
        bot_enabled = False
        return jsonify({'message': 'Bot disabled'})
    elif command == 'reset_day':
        today = datetime.now().strftime('%d/%m')
        db = load_data()
        db[today] = []
        save_data(db)
        return jsonify({'message': f"Appointments for {today} reset."})
    else:
        return jsonify({'error': 'Unknown command'}), 400

if __name__ == '__main__':
    app.run(debug=True)
