from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import os
from PIL import Image
import qrcode
import base64
import io
from functools import wraps
import math
from sqlalchemy import text


app = Flask(__name__, template_folder='app/templates',static_folder="app/static")
app.config['SECRET_KEY'] = 'savethebest123boom'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Create uploads directory if it doesn't exist
uploads_dir = os.path.abspath("uploads")  
print(f"Uploads directory: {uploads_dir}")  
os.makedirs(uploads_dir, exist_ok=True) 

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=True)
    fullname = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='instructor')
    courses = db.relationship('Course', backref='instructor', lazy=True)

    def set_password(self, password):  
        self.password = generate_password_hash(password)  

    def check_password(self, password):  
        return check_password_hash(self.password, password)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(10), nullable=False, unique=True)
    description = db.Column(db.Text)
    courses = db.relationship('Course', backref='department', lazy=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_name = db.Column(db.String(100), nullable=False)
    course_code = db.Column(db.String(10), nullable=False)
    class_location = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    max_distance = db.Column(db.Float, default=100.0)  # Maximum distance in meters
    year = db.Column(db.Integer, nullable=False)  # 100, 200, 300, 400, 500, 600
    session = db.Column(db.String(20), nullable=False)  # weekend, regular, evening
    
    def is_active(self):
        """Check if the course is currently active (within 30 minutes of start time)"""
        now = datetime.now()
        return self.start_time <= now <= (self.start_time + timedelta(minutes=30))
    
    def attendance_count(self):
        """Get the number of students who attended this course"""
        return Attendance.query.filter_by(course_id=self.id).count()

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    photo_path = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    distance_from_class = db.Column(db.Float)  # Distance from class location in meters
    location_verified = db.Column(db.Boolean, default=False)  # NEW: GPS verification status
    course = db.relationship('Course', backref='attendances')

    def is_within_class_location(self):
        """
        True if student's coordinates are within the course's max_distance.
        """
        if self.course and self.latitude and self.longitude \
           and self.course.latitude and self.course.longitude:
            d = haversine_distance(
                self.latitude,
                self.longitude,
                self.course.latitude,
                self.course.longitude
            )
            return d <= (self.course.max_distance or 100.0)
        return False

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Returns the distance in meters between two lat/lon points.
    """
    R = 6371000  # radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    from math import radians, cos, sin, asin, sqrt
    
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius of earth in meters
    return c * r

# Routes
@app.route('/')
def home():
    return render_template('base.html')

# ADMIN ROUTES
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard showing overview statistics"""
    stats = {
        'total_users': User.query.count(),
        'total_instructors': User.query.filter_by(role='instructor').count(),
        'total_departments': Department.query.count(),
        'total_courses': Course.query.count(),
        'total_students': Student.query.count(),
        'total_attendance': Attendance.query.count(),
        'active_courses': Course.query.filter(
            Course.start_time <= datetime.now(),
            Course.end_time >= datetime.now()
        ).count(),
        'verified_attendance': Attendance.query.filter_by(location_verified=True).count()
    }
    
    # Recent activities
    recent_attendance = Attendance.query.order_by(Attendance.timestamp.desc()).limit(5).all()
    recent_courses = Course.query.order_by(Course.id.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', stats=stats, 
                         recent_attendance=recent_attendance, recent_courses=recent_courses)

# USER MANAGEMENT
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/create', methods=['POST'])
@login_required
@admin_required
def admin_create_user():
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if not username or not password or not role:
            flash('All fields are required.', 'danger')
            return redirect(url_for('admin_users'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('admin_users'))
        
        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('User created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating user: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/update/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_update_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        username = request.form.get('username')
        role = request.form.get('role')
        
        if not username or not role:
            flash('Username and role are required.', 'danger')
            return redirect(url_for('admin_users'))
        
        user.username = username
        user.role = role
        
        if request.form.get('password'):
            user.set_password(request.form['password'])
        
        db.session.commit()
        flash('User updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating user: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            flash('Cannot delete your own account.', 'danger')
            return redirect(url_for('admin_users'))
        
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

# DEPARTMENT MANAGEMENT
@app.route('/admin/departments')
@login_required
@admin_required
def admin_departments():
    departments = Department.query.all()
    return render_template('admin/departments.html', departments=departments)

@app.route('/admin/departments/create', methods=['POST'])
@login_required
@admin_required
def admin_create_department():
    try:
        name = request.form.get('name')
        code = request.form.get('code')
        description = request.form.get('description', '')
        
        if not name or not code:
            flash('Department name and code are required.', 'danger')
            return redirect(url_for('admin_departments'))
        
        if Department.query.filter_by(code=code).first():
            flash('Department code already exists.', 'danger')
            return redirect(url_for('admin_departments'))
        
        department = Department(name=name, code=code, description=description)
        db.session.add(department)
        db.session.commit()
        flash('Department created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating department: {str(e)}', 'danger')
    
    return redirect(url_for('admin_departments'))

@app.route('/admin/departments/update/<int:dept_id>', methods=['POST'])
@login_required
@admin_required
def admin_update_department(dept_id):
    try:
        department = Department.query.get_or_404(dept_id)
        name = request.form.get('name')
        code = request.form.get('code')
        
        if not name or not code:
            flash('Department name and code are required.', 'danger')
            return redirect(url_for('admin_departments'))
        
        department.name = name
        department.code = code
        department.description = request.form.get('description', '')
        
        db.session.commit()
        flash('Department updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating department: {str(e)}', 'danger')
    
    return redirect(url_for('admin_departments'))

@app.route('/admin/departments/delete/<int:dept_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_department(dept_id):
    try:
        department = Department.query.get_or_404(dept_id)
        db.session.delete(department)
        db.session.commit()
        flash('Department deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting department: {str(e)}', 'danger')
    
    return redirect(url_for('admin_departments'))

# COURSE MANAGEMENT
@app.route('/admin/courses')
@login_required
@admin_required
def admin_courses():
    courses = Course.query.all()
    departments = Department.query.all()
    users = User.query.filter_by(role='instructor').all()
    return render_template('admin/courses.html', courses=courses, departments=departments, users=users)

@app.route('/admin/courses/create', methods=['POST'])
@login_required
@admin_required
def admin_create_course():
    try:
        course_name = request.form.get('course_name')
        course_code = request.form.get('course_code')
        class_location = request.form.get('class_location')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        instructor_id = request.form.get('instructor_id')
        department_id = request.form.get('department_id')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        max_distance = request.form.get('max_distance', 100.0)
        
        if not all([course_name, course_code, class_location, start_time_str, end_time_str, instructor_id, department_id]):
            flash('All required fields must be filled.', 'danger')
            return redirect(url_for('admin_courses'))
        
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        
        if start_time >= end_time:
            flash('End time must be after start time.', 'danger')
            return redirect(url_for('admin_courses'))
        
        course = Course(
            course_name=course_name,
            course_code=course_code,
            class_location=class_location,
            start_time=start_time,
            end_time=end_time,
            instructor_id=instructor_id,
            department_id=department_id,
            latitude=float(latitude) if latitude else None,
            longitude=float(longitude) if longitude else None,
            max_distance=float(max_distance)
        )
        
        db.session.add(course)
        db.session.commit()
        flash('Course created successfully!', 'success')
    except ValueError as e:
        flash(f'Invalid date/time format or number value: {str(e)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating course: {str(e)}', 'danger')
    
    return redirect(url_for('admin_courses'))

@app.route('/admin/courses/update/<int:course_id>', methods=['POST'])
@login_required
@admin_required
def admin_update_course(course_id):
    try:
        course = Course.query.get_or_404(course_id)
        
        course_name = request.form.get('course_name')
        course_code = request.form.get('course_code')
        class_location = request.form.get('class_location')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        instructor_id = request.form.get('instructor_id')
        department_id = request.form.get('department_id')
        
        if not all([course_name, course_code, class_location, start_time_str, end_time_str, instructor_id, department_id]):
            flash('All required fields must be filled.', 'danger')
            return redirect(url_for('admin_courses'))
        
        course.course_name = course_name
        course.course_code = course_code
        course.class_location = class_location
        course.start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        course.end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        course.instructor_id = instructor_id
        course.department_id = department_id
        
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        max_distance = request.form.get('max_distance', 100.0)
        
        course.latitude = float(latitude) if latitude else None
        course.longitude = float(longitude) if longitude else None
        course.max_distance = float(max_distance)
        
        db.session.commit()
        flash('Course updated successfully!', 'success')
    except ValueError as e:
        flash(f'Invalid date/time format or number value: {str(e)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating course: {str(e)}', 'danger')
    
    return redirect(url_for('admin_courses'))

@app.route('/admin/courses/delete/<int:course_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_course(course_id):
    try:
        course = Course.query.get_or_404(course_id)
        db.session.delete(course)
        db.session.commit()
        flash('Course deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting course: {str(e)}', 'danger')
    
    return redirect(url_for('admin_courses'))

# STUDENT MANAGEMENT
@app.route('/admin/students')
@login_required
@admin_required
def admin_students():
    students = Student.query.all()
    departments = Department.query.all()
    return render_template('admin/students.html', students=students, departments=departments)

@app.route('/admin/students/create', methods=['POST'])
@login_required
@admin_required
def admin_create_student():
    try:
        student_id = request.form.get('student_id')
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        department_id = request.form.get('department_id')
        
        if not student_id or not full_name:
            flash('Student ID and full name are required.', 'danger')
            return redirect(url_for('admin_students'))
        
        if Student.query.filter_by(student_id=student_id).first():
            flash('Student ID already exists.', 'danger')
            return redirect(url_for('admin_students'))
        
        student = Student(
            student_id=student_id,
            full_name=full_name,
            email=email,
            phone=phone,
            department_id=int(department_id) if department_id else None
        )
        
        db.session.add(student)
        db.session.commit()
        flash('Student created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating student: {str(e)}', 'danger')
    
    return redirect(url_for('admin_students'))

@app.route('/admin/students/update/<int:student_id>', methods=['POST'])
@login_required
@admin_required
def admin_update_student(student_id):
    try:
        student = Student.query.get_or_404(student_id)
        
        new_student_id = request.form.get('student_id')
        full_name = request.form.get('full_name')
        
        if not new_student_id or not full_name:
            flash('Student ID and full name are required.', 'danger')
            return redirect(url_for('admin_students'))
        
        student.student_id = new_student_id
        student.full_name = full_name
        student.email = request.form.get('email')
        student.phone = request.form.get('phone')
        
        department_id = request.form.get('department_id')
        student.department_id = int(department_id) if department_id else None
        
        db.session.commit()
        flash('Student updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating student: {str(e)}', 'danger')
    
    return redirect(url_for('admin_students'))

@app.route('/admin/students/delete/<int:student_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_student(student_id):
    try:
        student = Student.query.get_or_404(student_id)
        db.session.delete(student)
        db.session.commit()
        flash('Student deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'danger')
    
    return redirect(url_for('admin_students'))

# ATTENDANCE MANAGEMENT
@app.route('/admin/attendance')
@login_required
@admin_required
def admin_attendance():
    attendances = Attendance.query.join(Course).order_by(Attendance.timestamp.desc()).all()
    courses = Course.query.all()
    return render_template('admin/attendance.html', attendances=attendances, courses=courses)

@app.route('/admin/attendance/create', methods=['POST'])
@login_required
@admin_required
def admin_create_attendance():
    try:
        student_id = request.form.get('student_id')
        student_name = request.form.get('student_name')
        course_id = request.form.get('course_id')
        latitude = request.form.get('latitude', type=float)
        longitude = request.form.get('longitude', type=float)
        distance_from_class = request.form.get('distance_from_class', type=float)
        photo_file = request.files.get('photo')

        if not all([student_id, student_name, course_id]):
            flash('Student ID, name, and course are required.', 'danger')
            return redirect(url_for('admin_attendance'))

        # Save photo
        photo_filename = None
        if photo_file and photo_file.filename:
            photo_filename = secure_filename(photo_file.filename)
            photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
        else:
            flash('Photo is required.', 'danger')
            return redirect(url_for('admin_attendance'))

        # Verify location if course has GPS coordinates
        course = Course.query.get(course_id)
        location_verified = False
        if course and course.latitude and course.longitude and latitude and longitude:
            calculated_distance = calculate_distance(latitude, longitude, course.latitude, course.longitude)
            distance_from_class = calculated_distance
            location_verified = calculated_distance <= course.max_distance

        attendance = Attendance(
            student_id=student_id,
            student_name=student_name,
            course_id=course_id,
            latitude=latitude,
            longitude=longitude,
            distance_from_class=distance_from_class,
            photo_path=photo_filename,
            location_verified=location_verified
        )
        db.session.add(attendance)
        db.session.commit()
        flash('Attendance record created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating attendance: {str(e)}', 'danger')
    return redirect(url_for('admin_attendance'))

@app.route('/admin/attendance/update/<int:attendance_id>', methods=['POST'])
@login_required
@admin_required
def admin_update_attendance(attendance_id):
    attendance = Attendance.query.get_or_404(attendance_id)
    try:
        student_id = request.form.get('student_id')
        student_name = request.form.get('student_name')
        course_id = request.form.get('course_id')
        
        if not all([student_id, student_name, course_id]):
            flash('Student ID, name, and course are required.', 'danger')
            return redirect(url_for('admin_attendance'))
        
        attendance.student_id = student_id
        attendance.student_name = student_name
        attendance.course_id = course_id
        attendance.latitude = request.form.get('latitude', type=float)
        attendance.longitude = request.form.get('longitude', type=float)
        attendance.distance_from_class = request.form.get('distance_from_class', type=float)

        # Recalculate location verification
        course = Course.query.get(course_id)
        if course and course.latitude and course.longitude and attendance.latitude and attendance.longitude:
            calculated_distance = calculate_distance(
                attendance.latitude, attendance.longitude, 
                course.latitude, course.longitude
            )
            attendance.distance_from_class = calculated_distance
            attendance.location_verified = calculated_distance <= course.max_distance

        # Optional photo update
        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename:
            # delete old photo
            if attendance.photo_path:
                old_photo = os.path.join(app.config['UPLOAD_FOLDER'], attendance.photo_path)
                if os.path.exists(old_photo):
                    os.remove(old_photo)
            # save new photo
            photo_filename = secure_filename(photo_file.filename)
            photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
            attendance.photo_path = photo_filename

        db.session.commit()
        flash('Attendance record updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating attendance: {str(e)}', 'danger')
    return redirect(url_for('admin_attendance'))

@app.route('/admin/attendance/delete/<int:attendance_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_attendance(attendance_id):
    try:
        attendance = Attendance.query.get_or_404(attendance_id)

        # Delete photo file if it exists
        if attendance.photo_path:
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], attendance.photo_path)
            if os.path.exists(photo_path):
                os.remove(photo_path)

        db.session.delete(attendance)
        db.session.commit()
        flash('Attendance record deleted successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting attendance: {str(e)}', 'danger')

    return redirect(url_for('admin_attendance'))

# EXISTING ROUTES
@app.route('/departments', methods=['GET', 'POST'])
def departments():
    """Show all departments for students to choose from"""
    departments = Department.query.all()
    return render_template('departments.html', departments=departments)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        title = request.form.get('title')
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username:
            flash('Username is required.', 'danger')
            return redirect(url_for('register'))
        if not title:
            flash('Title is required.', 'danger')
            return redirect(url_for('register'))
        if not fullname:
            flash('fullname is required.', 'danger')
            return redirect(url_for('register'))        
        if not email:
            flash('Email is required.', 'danger')
            return redirect(url_for('register'))
        if not password:
            flash('Password is required.', 'danger')
            return redirect(url_for('register'))
    
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('register'))
    
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, title=title, fullname=fullname, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])  
def login():  
    if request.method == 'POST':  
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=username).first()  

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            
            # Redirect based on user role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('add_course'))
        
        flash('Invalid username or password.', 'danger')  

    return render_template('login.html')

@app.route('/add_course', methods=['GET', 'POST'])  
@login_required  
def add_course():  
    departments = Department.query.all()
    
    if request.method == 'POST':  
        course_name = request.form.get('course_name')
        course_code = request.form.get('course_code')
        class_location = request.form.get('class_location')
        department_id = request.form.get('department_id')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        max_distance = request.form.get('max_distance', 100.0)
        year = request.form.get('year')
        session = request.form.get('session')

        # Validation
        if not course_name:
            flash('Course name is required.', 'danger')
            return render_template('add_course.html', departments=departments)
        if not course_code:
            flash('Course code is required.', 'danger')
            return render_template('add_course.html', departments=departments)
        if not class_location:
            flash('Class location is required.', 'danger')
            return render_template('add_course.html', departments=departments)
        if not department_id:
            flash('Department selection is required.', 'danger')
            return render_template('add_course.html', departments=departments)
        if not year:
            flash('Year/Level is required.', 'danger')
            return render_template('add_course.html', departments=departments)
        if not session:
            flash('Session is required.', 'danger')
            return render_template('add_course.html', departments=departments)
        if not start_time_str or not end_time_str:
            flash('Start and end time are required.', 'danger')
            return render_template('add_course.html', departments=departments)
        
        # Validate year
        valid_years = [100, 200, 300, 400, 500, 600]
        try:
            year_int = int(year)
            if year_int not in valid_years:
                flash('Invalid year/level selected.', 'danger')
                return render_template('add_course.html', departments=departments)
        except ValueError:
            flash('Invalid year/level format.', 'danger')
            return render_template('add_course.html', departments=departments)
        
        # Validate session
        valid_sessions = ['regular', 'weekend', 'evening']
        if session.lower() not in valid_sessions:
            flash('Invalid session selected.', 'danger')
            return render_template('add_course.html', departments=departments)
        
        try:
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Invalid date/time format.', 'danger')
            return render_template('add_course.html', departments=departments)
        
        if start_time >= end_time:
            flash('End time must be after start time.', 'danger')
            return render_template('add_course.html', departments=departments)

        try:
            # Create a new Course instance  
            new_course = Course(  
                course_name=course_name,  
                course_code=course_code,  
                class_location=class_location,
                department_id=department_id,
                start_time=start_time,  
                end_time=end_time,  
                instructor_id=current_user.id,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
                max_distance=float(max_distance) if max_distance else 100.0,
                year=year_int,
                session=session.lower()
            )  

            db.session.add(new_course)  
            db.session.commit()    

            flash('Course added successfully!', 'success')  
            return redirect(url_for('view_course'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding course: {str(e)}', 'danger')
            return render_template('add_course.html', departments=departments)

    return render_template('add_course.html', departments=departments)

@app.route("/view_course", methods=["GET"])
@login_required
def view_course():
    courses = (
        Course.query.filter_by(instructor_id=current_user.id)
        .order_by(Course.start_time)
        .all()
    )

    now = datetime.utcnow()
    course_views = []
    for course in courses:
        if course.is_active():
            status = "Active"
            badge_class = "status-active"
        elif course.start_time > now:
            status = "Upcoming"
            badge_class = "status-upcoming"
        else:
            status = "Ended"
            badge_class = "status-ended"

        course_views.append({
            "id": course.id,
            "course_name": course.course_name,
            "course_code": course.course_code,
            "department": course.department.name,
            "class_location": course.class_location,
            "start_time": course.start_time,
            "end_time": course.end_time,
            "attendees": course.attendance_count(),
            "status": status,
            "badge_class": badge_class,
            "latitude": course.latitude,
            "longitude": course.longitude,
            "is_active": course.is_active(),
        })

    return render_template('view_course.html', courses=course_views)

@app.route('/attend/<int:department_id>')
def attend(department_id):
    """Show courses for a specific department that are available today"""
    department = Department.query.get_or_404(department_id)
    today = date.today()
    
    # Get courses for today in this department
    courses = Course.query.filter(
        Course.department_id == department_id,
        db.func.date(Course.start_time) == today
    ).order_by(Course.start_time).all()

    return render_template('attend.html', courses=courses, department=department)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

@app.route('/mark_attendance/<int:course_id>', methods=['POST'])
def mark_attendance(course_id):
    course = Course.query.get_or_404(course_id)
    
    # Check if course is still active (within 30 minutes of start time)
    if not course.is_active():
        return jsonify({
            'success': False,
            'message': 'Attendance period has ended. You cannot mark attendance after 30 minutes from start time.'
        }), 400
    
    try:
        student_id = request.form.get('student_id')
        student_name = request.form.get('student_name')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        photo_data = request.form.get('photo_path')
        
        if not all([student_id, student_name, latitude, longitude, photo_data]):
            return jsonify({
                'success': False,
                'message': 'All fields are required (student ID, name, location, and photo).'
            }), 400
        
        latitude = float(latitude)
        longitude = float(longitude)
        
        # Check if student already marked attendance for this course
        existing_attendance = Attendance.query.filter_by(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if existing_attendance:
            return jsonify({
                'success': False,
                'message': 'You have already marked attendance for this course.'
            }), 400
        
        # Calculate distance from class location and verify GPS
        distance_from_class = None
        location_verified = False
        
        if course.latitude and course.longitude:
            distance_from_class = calculate_distance(
                latitude, longitude, course.latitude, course.longitude
            )
            
            # Verify if student is within acceptable range
            location_verified = distance_from_class <= course.max_distance
            
            if not location_verified:
                return jsonify({
                    'success': False,
                    'message': f'You are too far from the class location. Distance: {distance_from_class:.0f}m (Max allowed: {course.max_distance:.0f}m). Please move closer to mark attendance.',
                    'distance': f'{distance_from_class:.0f}m',
                    'verified': False
                }), 400
        
        # Handle photo processing
        photo_filename = None
        if photo_data and photo_data.startswith('data:image'):
            try:
                # Create uploads directory if it doesn't exist
                uploads_dir = os.path.join(app.root_path, 'uploads')
                os.makedirs(uploads_dir, exist_ok=True)
                
                # Generate unique filename
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                photo_filename = f"{student_id}_{course_id}_{timestamp}.png"
                photo_path = os.path.join(uploads_dir, photo_filename)
                
                # Decode base64 image
                image_data = photo_data.split(',')[1]
                image_binary = base64.b64decode(image_data)
                
                # Save and resize image using PIL
                with Image.open(io.BytesIO(image_binary)) as img:
                    if img.mode in ('RGBA', 'LA'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    
                    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                    img.save(photo_path, 'JPEG', quality=85)
                    
            except Exception as e:
                print(f"Error processing photo: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'Error processing photo: {str(e)}'
                }), 500
        else:
            return jsonify({
                'success': False,
                'message': 'No valid photo data received.'
            }), 400
        
        # Create new attendance record
        new_attendance = Attendance(
            student_id=student_id,
            student_name=student_name,
            course_id=course_id,
            photo_path=photo_filename,
            latitude=latitude,
            longitude=longitude,
            distance_from_class=distance_from_class,
            location_verified=location_verified
        )
        
        db.session.add(new_attendance)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Attendance marked successfully! Your location has been verified.',
            'distance': f'{distance_from_class:.0f}m' if distance_from_class else 'N/A',
            'verified': location_verified
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': f'Invalid data format: {str(e)}'
        }), 400
    except Exception as e:
        db.session.rollback()
        print(f"Error in mark_attendance: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred while processing your attendance: {str(e)}'
        }), 500

@app.route('/attendance_report/<int:course_id>')
@login_required
def attendance_report(course_id):
    """View attendance report for a specific course"""
    course = Course.query.get_or_404(course_id)

    # Check if current user is the instructor for this course or admin
    if course.instructor_id != current_user.id and current_user.role != 'admin':
        flash('You are not authorized to view this report.', 'danger')
        return redirect(url_for('view_course'))

    attendances = Attendance.query.filter_by(course_id=course_id)\
                                  .order_by(Attendance.timestamp).all()

    return render_template(
        'attendance_report.html',
        course=course,
        attendances=attendances,
        timedelta=timedelta
    )

@app.route('/view_attendee/<int:course_id>')
@login_required
def view_attendee(course_id):
    """View all attendees for a specific course with detailed information"""
    course = Course.query.get_or_404(course_id)
    
    # Check if current user is the instructor for this course or admin
    if course.instructor_id != current_user.id and current_user.role != 'admin':
        flash('You are not authorized to view this page.', 'danger')
        return redirect(url_for('view_course') if current_user.role == 'instructor' else url_for('admin_dashboard'))
    
    # Get all attendances for this course, ordered by timestamp
    attendances = Attendance.query.filter_by(course_id=course_id).order_by(Attendance.timestamp).all()
    
    # Calculate statistics
    total_attendees = len(attendances)
    verified_count = sum(1 for a in attendances if a.location_verified)
    
    # Count on-time attendance (within 15 minutes of start)
    on_time_count = 0
    for a in attendances:
        if a.timestamp and course.start_time:
            time_diff = (a.timestamp - course.start_time).total_seconds() / 60
            if 0 <= time_diff <= 15:
                on_time_count += 1
    
    # Calculate course status
    course_status = {
        'is_active': course.is_active(),
        'total_attendees': total_attendees,
        'verified_attendees': verified_count,
        'start_time': course.start_time,
        'end_time': course.end_time,
        'location': course.class_location
    }
    
    return render_template('view_attendee.html', 
                         course=course, 
                         attendances=attendances, 
                         course_status=course_status,
                         on_time_count=on_time_count,
                         in_range_count=verified_count)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('home'))

# Initialize database with sample departments and admin user
def init_db():
    with app.app_context():
        db.create_all()

        # Ensure 'email' column exists on user table (SQLite)
        try:
            result = db.session.execute(text("PRAGMA table_info(user)"))
            columns = [row[1] for row in result]
            if 'email' not in columns:
                db.session.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(120)"))
                db.session.commit()
        except Exception as e:
            print(f"Could not ensure email column on user table: {e}")
        
        # Create admin user if it doesn't exist
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(username='admin', title='Mr.', fullname= 'Administrator', email='superadmin@gmail.com', role='admin')

            admin_user.set_password('admin123')
            
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created! Username: admin, Password: admin123")
        
        # Add sample departments if they don't exist
        if Department.query.count() == 0:
            departments = [
                Department(name='Computer Science', code='CS', description='Department of Computer Science'),
                Department(name='Mathematics', code='MATH', description='Department of Mathematics'),
                Department(name='Physics', code='PHYS', description='Department of Physics'),
                Department(name='Chemistry', code='CHEM', description='Department of Chemistry'),
                Department(name='Biology', code='BIO', description='Department of Biology'),
                Department(name='Engineering', code='ENG', description='Department of Engineering'),
            ]
            
            for dept in departments:
                db.session.add(dept)
            
            db.session.commit()
            print("Sample departments added!")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0')

