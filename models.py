from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    users = db.relationship('User', backref='department_rel', lazy=True)

    def __repr__(self):
        return f'<Department {self.name}>'
    
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    surname = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), default='employee')  # บทบาทตำแหน่งงาน
    department = db.Column(db.String(100), default='')  # แผนก
    department_id = db.Column(db.Integer, db.ForeignKey('department.id')) # Foreign Key ไปที่ Department

    # โควต้าวันลาประจำปี
    sick_leave_quota = db.Column(db.Integer, default=30, nullable=True)
    personal_leave_quota = db.Column(db.Integer, default=10, nullable=True)
    vacation_leave_quota = db.Column(db.Integer, default=10, nullable=True)
    
    # จำนวนวันลาที่ใช้ไปแล้ว
    sick_used = db.Column(db.Integer, default=0)
    personal_used = db.Column(db.Integer, default=0)
    vacation_used = db.Column(db.Integer, default=0)
    
    # ความสัมพันธ์
    notes = db.relationship('Note', backref='user', lazy=True)
    leaves = db.relationship('Leave', foreign_keys='Leave.user_id', backref='employee', lazy=True)
    approved_leaves = db.relationship('Leave', foreign_keys='Leave.approved_by', backref='approver', lazy=True)
    
    def __repr__(self):
        return f'<User {self.email} ({self.role})>'

class Leave(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    leave_type = db.Column(db.String(20), nullable=False)  # sick, personal, vacation, other
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    contact_info = db.Column(db.String(255))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)  # เวลาที่อนุมัติ
    manager_comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    
    # ฟิลด์เพิ่มเติมสำหรับการมอบหมายงาน
    assign_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    work_details = db.Column(db.Text, nullable=True)
    
    # ความสัมพันธ์กับผู้รับมอบหมายงาน
    assigned_user = db.relationship('User', foreign_keys=[assign_to], backref='assigned_leaves')
    
    # ไฟล์แนบ
    attachment_filename = db.Column(db.String(255), nullable=True)
    attachment_path = db.Column(db.String(255), nullable=True)

    @hybrid_property
    def total_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    def __repr__(self):
        return f'<Leave {self.id}: {self.user_id} - {self.leave_type} ({self.status})>'

class LeaveHistory(db.Model):
    """บันทึกการเปลี่ยนแปลงสถานะการลา"""
    id = db.Column(db.Integer, primary_key=True)
    leave_id = db.Column(db.Integer, db.ForeignKey('leave.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # เพิ่มฟิลด์นี้
    action_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # เพิ่มฟิลด์นี้!
    comment = db.Column(db.Text, nullable=True)
    changed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    
    # ความสัมพันธ์
    leave = db.relationship('Leave', backref='history')
    
    # Explicitly specify foreign_keys for action_by and changed_by relationships
    user_action = db.relationship('User', foreign_keys=[action_by], backref='action_history')  # Explicit foreign key and backref
    user_changed = db.relationship('User', foreign_keys=[changed_by], backref='changed_history')  # Explicit foreign key and backref
    
    def __repr__(self):
        return f'<LeaveHistory {self.id}: Leave #{self.leave_id} -> {self.status}>'


class DepartmentLeaveStats(db.Model):
    """สถิติการลางานตามแผนก"""
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    sick_count = db.Column(db.Integer, default=0)
    personal_count = db.Column(db.Integer, default=0)
    vacation_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<DepartmentLeaveStats {self.department} ({self.year})>'

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(150), nullable=False)
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)