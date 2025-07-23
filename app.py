from flask import Flask, render_template, request, redirect, session
import os

app = Flask(__name__)
app.secret_key = '123456'  # שים ב־Render בסודיות

# הדמיה לערכים סודיים מ־Render
os.environ['ADMIN_USERNAME'] = 'admin'
os.environ['ADMIN_PASSWORD'] = '1234'

@app.route("/login", methods=['GET', 'POST'])
def login():
    error = None
    admin_user = os.environ.get('ADMIN_USERNAME')
    admin_password = os.environ.get('ADMIN_PASSWORD')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username:
            error = "יש להזין שם משתמש"
            return render_template("login.html", error=error, admin_user=admin_user)

        # אם זה האדמין - דרוש סיסמה
        if username.lower() == admin_user.lower():
            if password == admin_password:
                session['username'] = username
                session['is_admin'] = True
                return redirect("/admin_command")
            else:
                error = "סיסמה שגויה"
                return render_template("login.html", error=error, admin_user=admin_user)

        # משתמש רגיל
        session['username'] = username
        session['is_admin'] = False
        return redirect("/")

    return render_template("login.html", error=error, admin_user=admin_user)


@app.route("/admin_command")
def admin_command():
    if session.get('is_admin'):
        return "ברוך הבא לפאנל האדמין!"
    return redirect("/login")
