from flask import Blueprint, render_template, request, redirect, url_for, flash , session
from flask_login import login_user, current_user, login_required
from .models import User
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
import re

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    data = request.form
    print(data)
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            return render_template('login-page.html', message='Email and password cannot be empty.', category='error', email=email)

        # ดึงข้อมูลผู้ใช้จากฐานข้อมูล
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)  # ใช้ Flask-Login เพื่อล็อกอินผู้ใช้
            
            # เก็บข้อมูลใน session
            session['user.id'] = user.id  # เพิ่ม user.id ในกรณีที่ต้องการเช็คจาก template
            session['first_name'] = user.first_name
            session['surname'] = user.surname
            session['role'] = user.role  # อาจจะเป็นประโยชน์สำหรับการตรวจสอบสิทธิ์

            # Redirect based on role
            if user.role == "employee":
                return redirect(url_for('views.employee'))
            elif user.role == "manager":
                return redirect(url_for('views.manager'))
            elif user.role == "admin":
                return redirect(url_for('views.admin'))
            
        return render_template('login-page.html', message='Invalid email or password.', category='error', email=email)
    
    return render_template('login-page.html')

@auth.route('/logout')
def logout():
    # ลบ session ที่เกี่ยวกับผู้ใช้
    session.clear()
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    data = request.form
    print(data)
    if request.method == 'POST':
        title = request.form.get('title')
        first_name = request.form.get('first_name')
        surname = request.form.get('surname')
        email = request.form.get('email')
        password = request.form.get('password')

        # ตรวจสอบข้อมูล
        if not first_name or not surname:
            return render_template('login-page.html', message='First name and surname cannot be empty.', category='error',
                                   title=title, first_name=first_name, surname=surname, email=email, show_register=True)

        if len(password) < 8:
            return render_template('login-page.html', message='Password must be at least 8 characters long.', category='error',
                                   title=title, first_name=first_name, surname=surname, email=email, show_register=True)

        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_regex, email):
            return render_template('login-page.html', message='Invalid email address.', category='error',
                                   title=title, first_name=first_name, surname=surname, email=email, show_register=True)

        # หากข้อมูลถูกต้อง
        newuser = User(
            title=title,
            first_name=first_name,
            surname=surname,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            role='employee'  # ให้เป็นพนักงานเสมอ
        )
        
        # เพิ่ม user ใหม่ในฐานข้อมูล
        from . import db
        db.session.add(newuser)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('login-page.html', show_register=True)
