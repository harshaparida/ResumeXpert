import os
import json
import re
from flask import Flask, request, jsonify, render_template, Response
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import PyPDF2
import docx
from pdf2image import convert_from_path
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import csv
from io import StringIO
import hashlib
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# Create the base class for SQLAlchemy
Base = declarative_base()

# Define the admin model
class Admin(Base):
    __tablename__ = 'admin'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(100), nullable=False)

    def __repr__(self):
        return f"<Admin(username={self.username})>"

# Define the candidate profile model
class CandidateProfile(Base):
    __tablename__ = 'candidate_profiles'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255))
    resume = Column(Text)  # Store the resume in text or file path
    skills = Column(Text)  # Skills can be stored as a comma-separated string or JSON
    phone = Column(String(20))
    education = Column(Text)
    experience = Column(Text)
    projects = Column(Text)
    ats_score = Column(Integer)
    uploaded_at = Column(String(50))
    city = Column(String(100))
    region = Column(String(100))

    def __repr__(self):
        return f"<CandidateProfile(name={self.name}, email={self.email})>"

# Set up the database connection
engine = create_engine("mysql://root:12345678@localhost/resume_analysis")

# Create the table in the database (if it doesn't already exist)
Base.metadata.create_all(engine)

# Create a session to interact with the database
Session = sessionmaker(bind=engine)
sqlalchemy_session = Session()

# Initialize admin user if not exists
def initialize_admin():
    admin = sqlalchemy_session.query(Admin).first()
    if not admin:
        # Create default admin user
        default_admin = Admin(
            username='admin',
            password='admin123'  # In production, this should be hashed
        )
        sqlalchemy_session.add(default_admin)
        sqlalchemy_session.commit()

# Call the initialization function
initialize_admin()

# Initialize Flask App
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

app.secret_key = '20233952'  # For session management

# Create uploads folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize Google Gemini API
load_dotenv()
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

# MySQL Database Configuration
db = mysql.connector.connect(
    host='localhost',
    user='root',
    password='12345678',
    database='resume_analysis'
)
cursor = db.cursor()

# Utility functions for text extraction
def extract_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
    return text.strip()


def extract_text_from_docx(docx_path):
    doc = docx.Document(docx_path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs]).strip()


def extract_text_from_image(image_path):
    return pytesseract.image_to_string(Image.open(image_path)).strip()


def parse_resume_with_gemini(file_path):
    file_ext = os.path.splitext(file_path)[1].lower()

    # Extract text based on file type
    if file_ext == '.pdf':
        text = extract_text_from_pdf(file_path)
    elif file_ext == '.docx':
        text = extract_text_from_docx(file_path)
    elif file_ext in ['.jpg', '.jpeg', '.png']:
        text = extract_text_from_image(file_path)
    else:
        return None

    if not text:
        return None

    # Updated prompt to include Projects
    prompt = f"""
    You are an AI resume parser. Extract the following details from the given resume text:
    - Full name
    - Email
    - Phone number
    - List of technical skills
    - Education (Degree, Institution, Year)
    - Work experience (Job title, Company, Duration)
    - Projects (Title, Description, Technologies Used, Duration)
    - Location (City, Region/State)

    Resume Text:
    {text}

    Return the results in **valid JSON format**:
    {{
        "name": "John Doe",
        "email": "johndoe@example.com",
        "phone": "+1-123-456-7890",
        "skills": ["Python", "Machine Learning", "SQL"],
        "education": [
            {{"degree": "B.Tech in CSE", "institution": "XYZ University", "year": "2023"}}
        ],
        "experience": [
            {{"title": "Software Engineer", "company": "ABC Corp", "duration": "2 years"}}
        ],
        "projects": [
            {{"title": "AI Resume Analyzer", "description": "Developed an AI-powered resume analyzer.", "technologies": ["Python", "Flask", "Gemini AI"], "duration": "3 months"}}
        ],
        "location": {{"city": "San Francisco", "region": "California"}}
    }}
    Ensure the JSON format is **valid and complete**.
    """

    try:
        response = model.generate_content(prompt)
        print("Raw Gemini Response:", response.text)

        if response.text:
            clean_response = response.text.strip().strip('```json').strip('```').strip()
            parsed_data = json.loads(clean_response)

            # Validate required fields
            if isinstance(parsed_data, dict) and all(
                key in parsed_data for key in ["name", "email", "phone", "skills", "education", "experience", "projects"]
            ):
                return parsed_data

    except json.JSONDecodeError:
        print("❌ JSON parsing error: Gemini returned invalid JSON.")
    except Exception as e:
        print(f"❌ Error parsing resume with Gemini: {str(e)}")

    return None



def calculate_ats_score(parsed_data):
    """
    Calculate ATS score based on extracted resume details.
    """
    print("Parsed Data for ATS Score Calculation:", parsed_data)  # Debugging line
    score = 0
    max_score = 100

    score += 10 if parsed_data['name'] else 0
    score += 10 if parsed_data['email'] else 0
    score += 10 if parsed_data['phone'] else 0
    score += min(len(parsed_data['skills']) * 5, 30)
    score += min(len(parsed_data['education']) * 10, 20)
    score += min(len(parsed_data['experience']) * 5, 20)

    return (score / max_score) * 100


@app.route('/ats-score', methods=['POST'])
def get_ats_score():
    data = request.get_json()
    if data and 'parsed_data' in data:
        score = calculate_ats_score(data['parsed_data'])
        return jsonify({'score': score})
    return jsonify({'error': 'No resume data provided'})


def get_job_recommendations(skills):
    """
    Generate job recommendations dynamically using Google's Gemini AI based on the candidate's skills.
    """
    skills_text = ", ".join(skills)

    prompt = f"""
    You are an AI career advisor. Given the following skills: {skills_text}, 
    provide **exactly 5 job recommendations** in **valid JSON format**.

    Each job should include:
    - "title": Job title
    - "match_percentage": A number between 0 and 100 indicating skill match
    - "matching_skills": List of matched skills
    - "recommended_skills": List of additional skills to learn
    - "description": Short job description

    Return output strictly in valid JSON format, like:
    [
        {{
            "title": "Software Engineer",
            "match_percentage": 85,
            "matching_skills": ["Python", "Django"],
            "recommended_skills": ["Docker", "Kubernetes"],
            "description": "A role focused on developing web applications using Python and Django."
        }}
    ]
    """

    try:
        response = model.generate_content(prompt)
        clean_response = response.text.strip().strip('```json').strip('```').strip()
        recommendations = json.loads(clean_response)
        return recommendations if isinstance(recommendations, list) else []
    except Exception as e:
        print(f"❌ Error generating job recommendations: {str(e)}")
        return []


def store_parsed_data(parsed_data, ats_score):
    """Store parsed resume data using SQLAlchemy."""
    try:
        # Check if a profile with the same email already exists
        candidate = sqlalchemy_session.query(CandidateProfile).filter_by(email=parsed_data['email']).first()

        location = parsed_data.get('location', {})
        city = location.get('city', 'Unknown')
        region = location.get('region', 'Unknown')

        if candidate:
            # Update existing profile
            candidate.name = parsed_data['name']
            candidate.phone = parsed_data['phone']
            candidate.skills = json.dumps(parsed_data['skills'])
            candidate.education = json.dumps(parsed_data['education'])
            candidate.experience = json.dumps(parsed_data['experience'])
            candidate.projects = json.dumps(parsed_data.get('projects', []))
            candidate.ats_score = ats_score
            candidate.uploaded_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            candidate.city = city
            candidate.region = region
        else:
            # Create new profile
            candidate = CandidateProfile(
                email=parsed_data['email'],
                name=parsed_data['name'],
                phone=parsed_data['phone'],
                skills=json.dumps(parsed_data['skills']),
                education=json.dumps(parsed_data['education']),
                experience=json.dumps(parsed_data['experience']),
                projects=json.dumps(parsed_data.get('projects', [])),
                ats_score=ats_score,
                uploaded_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                city=city,
                region=region
            )
            sqlalchemy_session.add(candidate)

        sqlalchemy_session.commit()
        return True
    except Exception as e:
        print(f"Error storing parsed data: {str(e)}")
        sqlalchemy_session.rollback()
        return False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'resume' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    parsed_data = parse_resume_with_gemini(filepath)
    if parsed_data is None:
        return jsonify({'error': 'Unable to parse resume'})

    ats_score = calculate_ats_score(parsed_data)
    store_parsed_data(parsed_data, ats_score)

    return jsonify({'success': True, 'parsed_data': parsed_data})


@app.route('/job-recommendations', methods=['POST'])
def get_jobs():
    data = request.get_json()
    return jsonify({'recommendations': get_job_recommendations(data['skills'])}) if data and 'skills' in data else jsonify({'error': 'No skills provided'})

# Admin Login Route
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Query admin using SQLAlchemy
        admin = sqlalchemy_session.query(Admin).filter_by(
            username=username,
            password=password  # In production, use proper password hashing
        ).first()

        if admin:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_page'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('admin_login.html')


@app.route('/admin-page')
def admin_page():
    if 'admin_logged_in' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('admin_login'))

    # Get all resumes ordered by upload date using SQLAlchemy
    resumes = sqlalchemy_session.query(CandidateProfile).order_by(
        CandidateProfile.uploaded_at.desc()
    ).all()

    # Convert to list of tuples for compatibility with existing template
    formatted_resumes = []
    for resume in resumes:
        # Format JSON data for better display
        skills = json.loads(resume.skills) if resume.skills else []
        education = json.loads(resume.education) if resume.education else []
        experience = json.loads(resume.experience) if resume.experience else []
        projects = json.loads(resume.projects) if resume.projects else []

        formatted_resumes.append((
            resume.id,
            resume.name,
            resume.email,
            resume.phone,
            format_json_for_display(skills),
            format_json_for_display(education),
            format_json_for_display(experience),
            format_json_for_display(projects),
            resume.ats_score,
            resume.uploaded_at
        ))

    return render_template('admin.html', resumes=formatted_resumes)

def format_json_for_display(data):
    """Format JSON data for HTML display."""
    if isinstance(data, list):
        if not data:
            return "No data available"
        if isinstance(data[0], dict):
            # Format list of dictionaries
            formatted = []
            for item in data:
                formatted.append("<div class='item'>")
                for key, value in item.items():
                    formatted.append(f"<strong>{key}:</strong> {value}<br>")
                formatted.append("</div>")
            return "".join(formatted)
        else:
            # Format simple list
            return "<br>".join(str(item) for item in data)
    elif isinstance(data, dict):
        # Format single dictionary
        formatted = []
        for key, value in data.items():
            formatted.append(f"<strong>{key}:</strong> {value}<br>")
        return "".join(formatted)
    else:
        return str(data)

# Admin Logout Route
@app.route('/admin-logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('admin_login'))

@app.route('/candidate-shortlist')
def candidate_shortlist():
    # Query candidates with ATS score >= 70 using SQLAlchemy
    shortlisted_candidates = sqlalchemy_session.query(CandidateProfile).filter(
        CandidateProfile.ats_score >= 70
    ).all()

    # Convert to list of tuples for compatibility with existing template
    formatted_candidates = [
        (c.id, c.name, c.email, c.phone, c.skills, c.education, c.experience, c.projects, c.ats_score, c.uploaded_at)
        for c in shortlisted_candidates
    ]

    return render_template('candidate_shortlist.html', candidates=formatted_candidates)

@app.route('/search-candidates', methods=['GET'])
def search_candidates():
    name = request.args.get('name', '')
    phone = request.args.get('phone', '')
    ats_score = request.args.get('ats_score', 0)
    skills = request.args.get('skills', '')

    # Start with base query
    query = sqlalchemy_session.query(CandidateProfile)

    # Apply filters
    if name:
        query = query.filter(CandidateProfile.name.ilike(f'%{name}%'))
    if phone:
        query = query.filter(CandidateProfile.phone.ilike(f'%{phone}%'))
    if ats_score:
        query = query.filter(CandidateProfile.ats_score >= int(ats_score))
    if skills:
        skill_list = skills.split(',')
        for skill in skill_list:
            query = query.filter(CandidateProfile.skills.ilike(f'%{skill.strip()}%'))

    # Execute query and get results
    results = query.all()

    # Convert results to list of tuples for compatibility with existing template
    formatted_results = [
        (r.id, r.name, r.phone, r.ats_score, r.uploaded_at)
        for r in results
    ]

    session['search_results'] = formatted_results
    return render_template('search_candidates.html', results=formatted_results)


@app.route('/export-data', methods=['GET'])
def export_data():
    results = session.get('search_results', [])

    if not results:
        return "No data available for export.", 400

    # Create CSV data
    output = StringIO()
    csv_writer = csv.writer(output)
    csv_writer.writerow(["ID", "Name", "Phone", "ATS Score", "Uploaded At"])

    for resume in results:
        csv_writer.writerow(resume)

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=filtered_results.csv'}
    )

# Add new routes for statistics
@app.route('/resume-statistics')
def resume_statistics():
    if 'admin_logged_in' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('admin_login'))

    # Get all resumes
    resumes = sqlalchemy_session.query(CandidateProfile).all()
    
    # Process statistics
    city_stats = {}
    region_stats = {}
    degree_stats = {}
    skill_stats = {}
    
    for resume in resumes:
        # City statistics
        city_stats[resume.city] = city_stats.get(resume.city, 0) + 1
        
        # Region statistics
        region_stats[resume.region] = region_stats.get(resume.region, 0) + 1
        
        # Education statistics
        education = json.loads(resume.education)
        for edu in education:
            degree = edu.get('degree', 'Unknown')
            degree_stats[degree] = degree_stats.get(degree, 0) + 1
        
        # Skills statistics
        skills = json.loads(resume.skills)
        for skill in skills:
            skill_stats[skill] = skill_stats.get(skill, 0) + 1
    
    # Sort statistics by count
    city_stats = dict(sorted(city_stats.items(), key=lambda x: x[1], reverse=True))
    region_stats = dict(sorted(region_stats.items(), key=lambda x: x[1], reverse=True))
    degree_stats = dict(sorted(degree_stats.items(), key=lambda x: x[1], reverse=True))
    # Get top 10 skills by converting sorted items to dict after slicing
    skill_stats = dict(sorted(skill_stats.items(), key=lambda x: x[1], reverse=True)[:10])
    
    return render_template('resume_statistics.html', 
                         city_stats=city_stats,
                         region_stats=region_stats,
                         degree_stats=degree_stats,
                         skill_stats=skill_stats)

if __name__ == '__main__':
    print("✅ ResuMind server is running on http://localhost:5000")
    app.run(debug=True)

