import os
import json
import re
from flask import Flask, request, jsonify, render_template
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
    password='root',
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
        ]
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
    sql = """
    INSERT INTO resumes (name, email, phone, skills, education, experience, projects, ats_score)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        parsed_data['name'],
        parsed_data['email'],
        parsed_data['phone'],
        json.dumps(parsed_data['skills']),
        json.dumps(parsed_data['education']),
        json.dumps(parsed_data['experience']),
        json.dumps(parsed_data.get('projects', [])),
        ats_score
    )
    cursor.execute(sql, values)
    db.commit()


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

        cursor = db.cursor()
        cursor.execute("SELECT * FROM admin WHERE username=%s AND password=%s", (username, password))
        admin = cursor.fetchone()

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

    cursor.execute("SELECT * FROM resumes ORDER BY uploaded_at DESC")
    resumes = cursor.fetchall()
    return render_template('admin.html', resumes=resumes)

# Admin Logout Route
@app.route('/admin-logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('admin_login'))

@app.route('/candidate-shortlist')
def candidate_shortlist():
    cursor.execute("SELECT * FROM resumes WHERE ats_score >= 70")
    shortlisted_candidates = cursor.fetchall()
    return render_template('candidate_shortlist.html', candidates=shortlisted_candidates)




if __name__ == '__main__':
    print("✅ ResuMind server is running on http://localhost:5000")
    app.run(debug=True)

