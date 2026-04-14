import bcrypt
from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from .utils import query_db, execute_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = query_db("SELECT * FROM authentication WHERE email = ?", (email,), one=True)

        if user and bcrypt.checkpw(password.encode('utf-8'), user[7].encode('utf-8')):

            session['user_ID'] = user[0]
            session['user_name'] = user[2]
            return redirect(url_for('main.home'))
        return render_template('login.html', msg="Invalid email or password.")
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fname = request.form['first_name']
        lname = request.form['last_name']
        sex = request.form['sex']
        age = request.form['age']
        address = request.form['address']
        email = request.form['email']
        number = request.form['number']
        emergency_contact = request.form['emergency_contact']
        password = request.form['password']
        cpassword = request.form['con-password']

        if password != cpassword:
            return render_template('register.html', msg="Passwords do not match.")

        if query_db("SELECT email FROM authentication WHERE email = ?", (email,), one=True):
            return render_template('register.html', msg="Email already exists.")

        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        execute_db(
            """
            INSERT INTO authentication (Fname, Lname, sex, age,Address, Email, Password, PhoneNumber , emergency_contact)
            VALUES (?, ?, ?, ?, ?, ?, ?, ? , ?)
            """, (fname, lname, age ,sex, address, email, hashed_pw.decode('utf-8') , number, emergency_contact)
        )
        return render_template('login.html', msg="Registration submitted. Wait for admin approval.")
    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.home'))
