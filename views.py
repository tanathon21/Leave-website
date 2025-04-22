from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, current_app
from flask_login import current_user, login_required
from datetime import datetime, timedelta, date
from sqlalchemy import extract, func
from .models import User, Leave, LeaveHistory
from . import db
from werkzeug.utils import secure_filename
import os
import calendar
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, FileField, BooleanField
from wtforms.validators import DataRequired


views = Blueprint('views', __name__)

@views.route('/')
def home():
    return render_template('index.html')

@views.route('/admin')
def admin():
    users = User.query.all()  # ดึงข้อมูลผู้ใช้ทั้งหมด
    return render_template('Admin/Admin_Manage.html', users=users)

@views.route('/delete_user/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    user = User.query.get_or_404(id)
    
    if user.role == 'admin':
        flash('ไม่สามารถลบบัญชีผู้ดูแลระบบได้ ❌', 'danger')
        return redirect(url_for('views.admin'))
    
    db.session.delete(user)
    db.session.commit()
    flash('ลบผู้ใช้เรียบร้อยแล้ว', 'success')
    return redirect(url_for('views.admin'))

@views.route('/edit_user/<int:id>', methods=['POST'])
@login_required
def edit_user(id):
    user = User.query.get_or_404(id)

    if user.role == 'admin' and current_user.role != 'admin':
        flash('คุณไม่มีสิทธิ์แก้ไขข้อมูลผู้ดูแลระบบ ❌', 'danger')
        return redirect(url_for('views.admin'))

    user.title = request.form.get('title')
    user.first_name = request.form.get('first_name')
    user.surname = request.form.get('surname')
    user.email = request.form.get('email')
    user.role = request.form.get('role')
    user.department = request.form.get('department')

    try:
        db.session.commit()
        flash('อัปเดตข้อมูลเรียบร้อยแล้ว ✅', 'success')
    except:
        flash('เกิดข้อผิดพลาดในการอัปเดตข้อมูล ❌', 'danger')

    return redirect(url_for('views.admin'))

@views.route('/manager')
@login_required
def manager():
        # Create a CSRF-enabled form
    class SimpleForm(FlaskForm):
        pass
    
    form = SimpleForm()
    # รับข้อมูลจาก query parameters สำหรับปฏิทิน
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    page = request.args.get('page', 1, type=int)
    stat_year = request.args.get('stat_year', datetime.now().year, type=int)
    
    # สร้างข้อมูลปฏิทิน
    calendar_weeks = get_calendar_data(month, year)
    
    # คำนวณเดือนก่อนหน้าและเดือนถัดไป
    first_day = datetime(year, month, 1)
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year
    
    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year
    
    # รายการคำขอลารออนุมัติ (แบ่งหน้า)
    per_page = 10
    pending_leaves_query = Leave.query.filter_by(status='pending')
    
    # ถ้าเป็น manager ที่ไม่ใช่ admin, ให้แสดงเฉพาะแผนกของตัวเอง
    if current_user.role == 'manager' and current_user.role != 'admin':
        department_users = User.query.filter_by(department=current_user.department).all()
        dept_user_ids = [user.id for user in department_users]
        pending_leaves_query = pending_leaves_query.filter(Leave.user_id.in_(dept_user_ids))
    
    pending_count = pending_leaves_query.count()
    pending_leaves = pending_leaves_query.order_by(Leave.created_at.desc()) \
                      .paginate(page=page, per_page=per_page, error_out=False)
    
    # จำนวนพนักงานลาวันนี้
    today = datetime.now().date()
    on_leave_today_query = Leave.query.filter(
        Leave.status == 'approved',
        Leave.start_date <= today,
        Leave.end_date >= today
    )
    
    # กรองตามแผนกหากจำเป็น
    if current_user.role == 'manager' and current_user.role != 'admin':
        department_users = User.query.filter_by(department=current_user.department).all()
        dept_user_ids = [user.id for user in department_users]
        on_leave_today_query = on_leave_today_query.filter(Leave.user_id.in_(dept_user_ids))
    
    on_leave_today = on_leave_today_query.count()
    
    # จำนวนพนักงานทั้งหมด
    if current_user.role in ['admin', 'hr']:
        total_employees = User.query.filter(User.role != 'admin').count()
    else:
        total_employees = User.query.filter_by(department=current_user.department).count()
    
    # ข้อมูลสถิติการลาตามแผนก
    departments_data = get_department_stats(stat_year)
    
    # สมาชิกในทีม
    if current_user.role in ['admin', 'hr']:
        team_members = User.query.filter(User.role != 'admin').all()
    else:
        team_members = User.query.filter_by(department=current_user.department).all()
    
    # ปีที่มีข้อมูลให้เลือกในหน้าสถิติ
    available_years = get_available_years()
    
    # ชื่อเดือนปัจจุบัน
    current_month_name = calendar.month_name[month]
    
    return render_template(
        'Manager/manager.html',
        form=form,  # Pass the form to the template
        pending_leaves=pending_leaves.items,
        page=page,
        pages=pending_leaves.pages,
        pending_count=pending_count,
        on_leave_today=on_leave_today,
        total_employees=total_employees,
        team_members=team_members,
        departments_data=departments_data,
        calendar_weeks=calendar_weeks,
        current_month_name=current_month_name,
        current_year=year,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        available_years=available_years
    )
    
def get_calendar_data(month, year):
    # สร้างข้อมูลปฏิทิน
    cal = calendar.monthcalendar(year, month)
    today = date.today()
    
    # สร้างรูปแบบข้อมูลสำหรับส่งไปที่เทมเพลต
    calendar_weeks = []
    
    for week in cal:
        week_data = []
        for day_num in week:
            if day_num == 0:
                # วันที่ไม่อยู่ในเดือนปัจจุบัน
                week_data.append({'day': '', 'current_month': False, 'is_today': False, 'leaves': []})
            else:
                current_date = date(year, month, day_num)
                
                # ดึงข้อมูลการลาในวันนี้
                leaves = Leave.query.filter(
                    Leave.status == 'approved',
                    Leave.start_date <= current_date,
                    Leave.end_date >= current_date
                ).all()
                
                # กรองเฉพาะแผนกของคนที่ login (ถ้าเป็น manager)
                if current_user.role == 'manager' and current_user.role != 'admin':
                    department_users = User.query.filter_by(department=current_user.department).all()
                    dept_user_ids = [user.id for user in department_users]
                    leaves = [leave for leave in leaves if leave.user_id in dept_user_ids]
                
                week_data.append({
                    'day': day_num,
                    'current_month': True,
                    'is_today': current_date == today,
                    'leaves': leaves
                })
        
        calendar_weeks.append(week_data)
    
    return calendar_weeks

def get_department_stats(year):
    # ดึงข้อมูลสถิติการลาตามแผนก
    departments = []
    sick_counts = []
    personal_counts = []
    vacation_counts = []
    
    # ถ้าเป็น admin หรือ hr ให้ดึงข้อมูลทุกแผนก
    if current_user.role in ['admin', 'hr']:
        department_list = db.session.query(User.department).distinct().all()
        department_list = [dept[0] for dept in department_list if dept[0] != 'ยังไม่ได้ระบุ']
    else:
        # ถ้าเป็น manager ให้ดึงเฉพาะแผนกตัวเอง
        department_list = [current_user.department]
    
    for department in department_list:
        departments.append(department)
        
        # ดึงรายชื่อ user ในแผนก
        users = User.query.filter_by(department=department).all()
        user_ids = [user.id for user in users]
        
        # ดึงข้อมูลการลาที่อนุมัติแล้วในปีที่เลือก
        sick_count = 0
        personal_count = 0
        vacation_count = 0
        
        for user_id in user_ids:
            sick_leaves = Leave.query.filter_by(
                user_id=user_id,
                leave_type='sick',
                status='approved'
            ).filter(extract('year', Leave.start_date) == year).all()
            
            personal_leaves = Leave.query.filter_by(
                user_id=user_id,
                leave_type='personal',
                status='approved'
            ).filter(extract('year', Leave.start_date) == year).all()
            
            vacation_leaves = Leave.query.filter_by(
                user_id=user_id,
                leave_type='vacation',
                status='approved'
            ).filter(extract('year', Leave.start_date) == year).all()
            
            sick_count += sum(leave.total_days for leave in sick_leaves)
            personal_count += sum(leave.total_days for leave in personal_leaves)
            vacation_count += sum(leave.total_days for leave in vacation_leaves)
        
        sick_counts.append(sick_count)
        personal_counts.append(personal_count)
        vacation_counts.append(vacation_count)
    
    return {
        'departments': departments,
        'sick': sick_counts,
        'personal': personal_counts,
        'vacation': vacation_counts
    }

def get_available_years():
    # ดึงปีที่มีข้อมูลการลา
    years = db.session.query(extract('year', Leave.start_date)).distinct().all()
    years = [int(year[0]) for year in years if year[0] is not None]
    
    # เพิ่มปีปัจจุบันถ้ายังไม่มี
    current_year = datetime.now().year
    if current_year not in years:
        years.append(current_year)
    
    return sorted(years, reverse=True)

@views.route('/manager_leave_request', methods=['GET', 'POST'])
@login_required
def manager_leave_request():

            # Create a CSRF-enabled form
    class SimpleForm(FlaskForm):
        pass
    
    form = SimpleForm()
    
    leave_type = request.form.get('leave_type')
    start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
    reason = request.form.get('reason')
    contact_info = request.form.get('contact_info')
    assign_to = request.form.get('assign_to')
    work_details = request.form.get('work_details')
    
    # คำนวณจำนวนวันลาที่ขอ
    delta = end_date - start_date
    requested_days = delta.days + 1
    
    # ตรวจสอบโควต้าการลา
    current_year = datetime.now().year
    approved_leaves = Leave.query.filter_by(
        user_id=current_user.id,
        status='approved',
        leave_type=leave_type
    ).filter(
        extract('year', Leave.start_date) == current_year
    ).all()
    
    # คำนวณจำนวนวันลาที่ถูกใช้ไปแล้ว
    used_leave_days = sum(leave.total_days for leave in approved_leaves)
    
    # ตรวจสอบโควต้าการลา
    if leave_type == 'sick':
        sick_leave_quota = current_user.sick_leave_quota or 0
        if requested_days > (sick_leave_quota - used_leave_days):
            flash('คุณมีวันลาป่วยไม่เพียงพอ', 'danger')
            return redirect(url_for('views.manager'))
    elif leave_type == 'personal':
        personal_leave_quota = current_user.personal_leave_quota or 0
        if requested_days > (personal_leave_quota - used_leave_days):
            flash('คุณมีวันลากิจไม่เพียงพอ', 'danger')
            return redirect(url_for('views.manager'))
    elif leave_type == 'vacation':
        vacation_leave_quota = current_user.vacation_leave_quota or 0
        if requested_days > (vacation_leave_quota - used_leave_days):
            flash('คุณมีวันลาพักร้อนไม่เพียงพอ', 'danger')
            return redirect(url_for('views.manager'))
    
    # ตรวจสอบไฟล์แนบ
    attachment_filename = None
    attachment_path = None
    
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            attachment_filename = filename
            
            # สร้างโฟลเดอร์เก็บไฟล์แนบ (ถ้ายังไม่มี)
            uploads_dir = os.path.join(current_app.root_path, 'static/uploads')
            if not os.path.exists(uploads_dir):
                os.makedirs(uploads_dir)
            
            # สร้างชื่อไฟล์พร้อม timestamp เพื่อป้องกันชื่อซ้ำ
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            new_filename = f"{current_user.id}_{timestamp}_{filename}"
            
            file_path = os.path.join(uploads_dir, new_filename)
            file.save(file_path)
            attachment_path = f"uploads/{new_filename}"
    
    # สร้างคำขอลาใหม่
    new_leave = Leave(
        form=form,
        user_id=current_user.id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        contact_info=contact_info,
        status='pending',
        assign_to=assign_to if assign_to else None,
        work_details=work_details,
        attachment_filename=attachment_filename,
        attachment_path=attachment_path
    )
    
    db.session.add(new_leave)
    db.session.commit()
    
    flash('ส่งคำขอลางานเรียบร้อยแล้ว', 'success')
    return redirect(url_for('views.manager'))

@views.route('/approve_leave/<int:leave_id>', methods=['POST'])
@login_required
def approve_leave(leave_id):
    leave = Leave.query.get_or_404(leave_id)
    
    # Check if the current user has permission to approve
    if current_user.role not in ['admin', 'hr', 'manager']:
        flash('คุณไม่มีสิทธิ์อนุมัติการลานี้', 'danger')
        return redirect(url_for('views.manager'))
    
    # If manager, check if leave is from their department
    if current_user.role == 'manager':
        employee = User.query.get(leave.user_id)
        if employee.department != current_user.department:
            flash('คุณไม่มีสิทธิ์อนุมัติการลาของพนักงานแผนกอื่น', 'danger')
            return redirect(url_for('views.manager'))
    
    # Update leave status
    leave.status = 'approved'
    leave.approved_by = current_user.id
    leave.approved_at = datetime.now()
    
    # Create leave history record
    history = LeaveHistory(
        leave_id=leave.id,
        action='approved',
        action_by=current_user.id
    )
    
    db.session.add(history)
    db.session.commit()
    
    flash('อนุมัติการลาเรียบร้อยแล้ว', 'success')
    return redirect(url_for('views.manager'))

@views.route('/reject_leave/<int:leave_id>', methods=['POST'])
@login_required
def reject_leave(leave_id):
    leave = Leave.query.get_or_404(leave_id)
    
    # Check if the current user has permission to reject
    if current_user.role not in ['admin', 'hr', 'manager']:
        flash('คุณไม่มีสิทธิ์ปฏิเสธการลานี้', 'danger')
        return redirect(url_for('views.manager'))
    
    # If manager, check if leave is from their department
    if current_user.role == 'manager':
        employee = User.query.get(leave.user_id)
        if employee.department != current_user.department:
            flash('คุณไม่มีสิทธิ์ปฏิเสธการลาของพนักงานแผนกอื่น', 'danger')
            return redirect(url_for('views.manager'))
    
    # Update leave status
    leave.status = 'rejected'
    leave.approved_by = current_user.id
    leave.approved_at = datetime.now()
    
    # Create leave history record
    history = LeaveHistory(
        leave_id=leave.id,
        action='rejected',
        action_by=current_user.id,
        note='ปฏิเสธโดย ' + current_user.first_name + ' ' + current_user.surname
    )
    
    db.session.add(history)
    db.session.commit()
    
    flash('ปฏิเสธการลาเรียบร้อยแล้ว', 'danger')
    return redirect(url_for('views.manager'))

@views.route('/leave_detail/<int:leave_id>')
@login_required
def leave_detail(leave_id):
    page = request.args.get('page', 1, type=int)
    leave = Leave.query.get_or_404(leave_id)
    employee = User.query.get(leave.user_id)
    
    # ตรวจสอบสิทธิ์ผู้จัดการ
    if current_user.role == 'manager' and current_user.role != 'admin':
        if employee.department != current_user.department:
            abort(403)

    # ประวัติการลา
    history = LeaveHistory.query.filter_by(leave_id=leave.id).order_by(LeaveHistory.created_at) \
                            .paginate(page=page, per_page=10, error_out=False)

    # พนักงานที่รับมอบหมาย (ถ้ามี)
    assigned_to = User.query.get(leave.assign_to) if leave.assign_to else None

    # ทีมของผู้จัดการ (ใช้ในฟอร์ม)
    team_members = User.query.filter_by(department=current_user.department).all()

    return render_template('Manager/manager.html',
                            leave=leave,
                            mployee=employee,
                            history=history.items,
                            pages=history.pages,  # ส่งจำนวนหน้ามา
                            assigned_to=assigned_to,
                            team_members=team_members)

# ฟังก์ชัน helper สำหรับการแบ่งหน้า (ถ้าจำเป็น)
def paginate(items, page, per_page):
    start = (page - 1) * per_page
    end = start + per_page
    total = len(items)
    pages = (total + per_page - 1) // per_page
    return {
        'items': items[start:end],
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages
    }

@views.route('/detailed_report')
@login_required
def detailed_report():
    if current_user.role not in ['manager', 'admin', 'hr']:
        flash('คุณไม่มีสิทธิ์เข้าถึงรายงานนี้', 'danger')
        return redirect(url_for('views.employee'))
    
    # ปีที่ต้องการดูข้อมูล
    year = request.args.get('year', datetime.now().year, type=int)
    
    # ข้อมูลการลาตามประเภทและแผนก
    if current_user.role in ['admin', 'hr']:
        departments = db.session.query(User.department).distinct().all()
        departments = [dept[0] for dept in departments if dept[0] != 'ยังไม่ได้ระบุ']
    else:
        departments = [current_user.department]
    
    department_stats = {}
    for dept in departments:
        # ดึงรายชื่อพนักงานในแผนก
        users = User.query.filter_by(department=dept).all()
        user_stats = []
        
        for user in users:
            # ดึงข้อมูลการลาของแต่ละคน
            sick_leaves = Leave.query.filter_by(
                user_id=user.id,
                leave_type='sick',
                status='approved'
            ).filter(extract('year', Leave.start_date) == year).all()
            
            personal_leaves = Leave.query.filter_by(
                user_id=user.id,
                leave_type='personal',
                status='approved'
            ).filter(extract('year', Leave.start_date) == year).all()
            
            vacation_leaves = Leave.query.filter_by(
                user_id=user.id,
                leave_type='vacation',
                status='approved'
            ).filter(extract('year', Leave.start_date) == year).all()
            
            # คำนวณวันลาที่ใช้ไปแล้ว
            sick_used = sum(leave.total_days for leave in sick_leaves)
            personal_used = sum(leave.total_days for leave in personal_leaves)
            vacation_used = sum(leave.total_days for leave in vacation_leaves)
            
            # คำนวณวันลาคงเหลือ
            sick_remaining = (user.sick_leave_quota or 0) - sick_used
            personal_remaining = (user.personal_leave_quota or 0) - personal_used
            vacation_remaining = (user.vacation_leave_quota or 0) - vacation_used
            
            user_stats.append({
                'id': user.id,
                'name': f"{user.first_name} {user.surname}",
                'role': user.role,
                'sick_used': sick_used,
                'sick_remaining': sick_remaining,
                'personal_used': personal_used,
                'personal_remaining': personal_remaining,
                'vacation_used': vacation_used,
                'vacation_remaining': vacation_remaining,
                'total_used': sick_used + personal_used + vacation_used,
                'total_quota': (user.sick_leave_quota or 0) + (user.personal_leave_quota or 0) + (user.vacation_leave_quota or 0)
            })
        
        department_stats[dept] = user_stats
    
    # ปีที่มีข้อมูลให้เลือก
    available_years = get_available_years()
    
    return render_template(
        'Manager/manager.html',
        department_stats=department_stats,
        year=year,
        available_years=available_years
    )

@views.route('/employee', methods=['GET', 'POST'])
@login_required
def employee():
    if request.method == 'POST':
        leave_type = request.form.get('leave_type')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        reason = request.form.get('reason')
        contact_info = request.form.get('contact_info')

        # คำนวณจำนวนวันลาที่ขอ
        delta = end_date - start_date
        requested_days = delta.days + 1

        # ดึงข้อมูลการลาที่อนุมัติแล้วในปีปัจจุบัน
        current_year = datetime.now().year
        approved_leaves = Leave.query.filter_by(
            user_id=current_user.id,
            status='approved',
            leave_type=leave_type
        ).filter(
            extract('year', Leave.start_date) == current_year
        ).all()

        # คำนวณจำนวนวันลาที่ถูกใช้ไปแล้วสำหรับประเภทการลานั้นๆ
        used_leave_days = sum(leave.total_days for leave in approved_leaves)

        # ตรวจสอบโควต้าการลา
        if leave_type == 'sick':
            sick_leave_quota = current_user.sick_leave_quota if current_user.sick_leave_quota is not None else 0
            used_leave_days = sum(leave.total_days for leave in approved_leaves)
            print(f"ประเภทการลา: {leave_type}")
            print(f"โควต้าลาป่วยทั้งหมด: {sick_leave_quota}")
            print(f"จำนวนวันที่ลาป่วยที่ใช้ไปแล้ว: {used_leave_days}")
            print(f"จำนวนวันที่ขอลางาน: {requested_days}")
            if requested_days > (sick_leave_quota - used_leave_days):
                flash('คุณมีวันลาป่วยไม่เพียงพอ', 'danger')
                return redirect(url_for('views.employee'))

        elif leave_type == 'personal':
            personal_leave_quota = current_user.personal_leave_quota if current_user.personal_leave_quota is not None else 0
            if requested_days > (personal_leave_quota - used_leave_days):
                flash('คุณมีวันลากิจไม่เพียงพอ', 'danger')
                return redirect(url_for('views.employee'))

        elif leave_type == 'vacation':
            vacation_leave_quota = current_user.vacation_leave_quota if current_user.vacation_leave_quota is not None else 0
            if requested_days > (vacation_leave_quota - used_leave_days):
                #เดี๋ยวต้องแก้เป็นแบบ sweetalert 2
                flash('คุณมีวันลาพักร้อนไม่เพียงพอ', 'danger')
                return redirect(url_for('views.employee'))
        
        

        # สร้างข้อมูลการลา
        new_leave = Leave(
            user_id=current_user.id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            contact_info=contact_info,
            status='pending'
        )

        db.session.add(new_leave)
        db.session.commit()
        #เดี๋ยวต้องแก้เป็นแบบ sweetalert 2
        flash('ส่งคำขอลางานเรียบร้อยแล้ว', 'success')
        return redirect(url_for('views.employee'))

    # ส่วนของการดึงข้อมูลสรุปการลา (ไม่มีการเปลี่ยนแปลง)
    current_year = datetime.now().year

    # ลาที่อนุมัติแล้ว
    approved_leaves_all = Leave.query.filter_by(
        user_id=current_user.id,
        status='approved'
    ).filter(
        extract('year', Leave.start_date) == current_year
    ).all()

    # ลารออนุมัติ
    pending_leaves = Leave.query.filter_by(
        user_id=current_user.id,
        status='pending'
    ).all()

    # ประวัติการลา
    leave_history = Leave.query.filter_by(
        user_id=current_user.id
    ).order_by(Leave.created_at.desc()).limit(5).all()

    # สถิติการลาแยกตามเดือน
    monthly_stats = {}
    for month in range(1, 13):
        monthly_stats[month] = {
            'sick': 0,
            'personal': 0,
            'vacation': 0
        }

    for leave in approved_leaves_all:
        if leave.start_date.year == current_year:
            month = leave.start_date.month
            monthly_stats[month][leave.leave_type] += leave.total_days

    # คำนวณวันลาที่ใช้ไปแล้ว
    used_sick_leave = sum(leave.total_days for leave in approved_leaves_all if leave.leave_type == 'sick')
    used_personal_leave = sum(leave.total_days for leave in approved_leaves_all if leave.leave_type == 'personal')
    used_vacation_leave = sum(leave.total_days for leave in approved_leaves_all if leave.leave_type == 'vacation')

    # คำนวณวันลาคงเหลือ
    sick_leave_quota = current_user.sick_leave_quota or 0
    personal_leave_quota = current_user.personal_leave_quota or 0
    vacation_leave_quota = current_user.vacation_leave_quota or 0

    used_sick_leave = used_sick_leave if used_sick_leave is not None else 0
    used_personal_leave = used_personal_leave if used_personal_leave is not None else 0
    used_vacation_leave = used_vacation_leave if used_vacation_leave is not None else 0

    remaining_sick_leave = sick_leave_quota - used_sick_leave
    remaining_personal_leave = personal_leave_quota - used_personal_leave
    remaining_vacation_leave = vacation_leave_quota - used_vacation_leave

    return render_template('Employee/employee.html',
                           remaining_sick_leave=remaining_sick_leave,
                           remaining_personal_leave=remaining_personal_leave,
                           remaining_vacation_leave=remaining_vacation_leave,
                           approved_leaves=approved_leaves_all,
                           pending_leaves=pending_leaves,
                           leave_history=leave_history,
                           monthly_stats=monthly_stats)