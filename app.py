from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret")

# Mock database
availability = {}
appointments = []
BOT_ENABLED = True

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "adminpass")

# Auto-generate availability for the next 5 days
def generate_availability():
    today = datetime.date.today()
    for i in range(5):
        date = today + datetime.timedelta(days=i)
        slots = [
            "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
            "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00"
        ]
        availability[date.strftime("%d/%m")] = slots

generate_availability()

@app.route("/")
def home():
    username = session.get("username")
    is_admin = username == ADMIN_USERNAME
    return render_template("index.html", is_admin=is_admin, username=username)

@app.route("/availability")
def get_availability():
    return jsonify(availability)

@app.route("/book", methods=["POST"])
def book():
    data = request.get_json()
    name = data.get("name")
    phone = data.get("phone")
    date = data.get("date")
    time = data.get("time")
    service = data.get("service")

    if date not in availability or time not in availability[date]:
        return jsonify({"error": "Time slot unavailable"})

    appointments.append({"name": name, "phone": phone, "date": date, "time": time, "service": service})
    availability[date].remove(time)

    return jsonify({"message": "Appointment booked successfully!"})

@app.route("/ask", methods=["POST"])
def ask():
    if not BOT_ENABLED:
        return jsonify({"answer": "The bot is currently disabled."})
    data = request.get_json()
    message = data.get("message", "").lower()
    if "price" in message:
        return jsonify({"answer": "Haircuts start at $30. Coloring services vary by length and style."})
    elif "location" in message:
        return jsonify({"answer": "We're located at 123 HairBoss Blvd, Tel Aviv."})
    elif "hours" in message:
        return jsonify({"answer": "We're open 9am to 3pm, Sunday to Thursday."})
    else:
        return jsonify({"answer": "Sorry, I don't understand. Try asking about prices, location, or hours."})

@app.route("/admin-command", methods=["POST"])
def admin_command():
    username = session.get("username")
    if username != ADMIN_USERNAME:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    command = data.get("command")

    if command == "reset":
        generate_availability()
        return jsonify({"message": "Availability reset."})
    elif command == "disable_bot":
        global BOT_ENABLED
        BOT_ENABLED = False
        return jsonify({"message": "Bot disabled."})
    elif command == "enable_bot":
        BOT_ENABLED = True
        return jsonify({"message": "Bot enabled."})
    elif command == "shutdown":
        func = request.environ.get('werkzeug.server.shutdown')
        if func:
            func()
        return jsonify({"message": "Server shutting down..."})
    else:
        return jsonify({"error": "Unknown command."})

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME:
            if password == ADMIN_PASSWORD:
                session["username"] = username
                return redirect(url_for("home"))
            else:
                return render_template("login.html", error="Invalid password", username=username)
        else:
            session["username"] = username
            return redirect(url_for("home"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
