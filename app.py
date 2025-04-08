import os
import json
import re
from flask import Flask, request, jsonify, render_template, Response, send_file
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
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO

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
    Returns a score between 0 and 100.
    """
    try:
        score = 0
        max_score = 100

        # Basic information (20%)
        if parsed_data.get('name'):
            score += 7
        if parsed_data.get('email'):
            score += 7
        if parsed_data.get('phone'):
            score += 6

        # Skills (30%)
        skills = parsed_data.get('skills', [])
        skill_score = min(len(skills) * 3, 30)  # 3 points per skill, max 30
        score += skill_score

        # Education (20%)
        education = parsed_data.get('education', [])
        education_score = min(len(education) * 10, 20)  # 10 points per education, max 20
        score += education_score

        # Experience (30%)
        experience = parsed_data.get('experience', [])
        experience_score = min(len(experience) * 10, 30)  # 10 points per experience, max 30
        score += experience_score

        # Ensure score is between 0 and 100
        final_score = min(max(score, 0), 100)
        return final_score

    except Exception as e:
        print(f"Error calculating ATS score: {str(e)}")
        return 0  # Return 0 if there's an error


@app.route('/ats-score', methods=['POST'])
def get_ats_score():
    try:
        data = request.get_json()
        if not data or 'parsed_data' not in data:
            return jsonify({'error': 'No resume data provided'}), 400

        score = calculate_ats_score(data['parsed_data'])
        
        # Update the ATS score in the database
        if 'email' in data['parsed_data']:
            candidate = sqlalchemy_session.query(CandidateProfile).filter_by(
                email=data['parsed_data']['email']
            ).first()
            
            if candidate:
                candidate.ats_score = int(score)
                sqlalchemy_session.commit()

        return jsonify({'score': score})
    except Exception as e:
        print(f"Error calculating ATS score: {str(e)}")
        return jsonify({'error': 'Failed to calculate ATS score'}), 500


def get_job_recommendations(skills):
    """
    Generate job recommendations dynamically using Google's Gemini AI based on the candidate's skills.
    """
    skills_text = ", ".join(skills)

    prompt = f"""
    As an AI career advisor, analyze these skills: {skills_text}
    Generate exactly 5 job recommendations that best match these skills.
    
    Instructions:
    1. Consider current job market trends
    2. Match skills to relevant job roles
    3. Suggest complementary skills for each role
    4. Provide realistic match percentages
    5. Keep descriptions concise but informative

    Return the recommendations in this exact JSON format:
    [
        {{
            "title": "Job Title",
            "match_percentage": number between 0-100,
            "matching_skills": ["skill1", "skill2"],
            "recommended_skills": ["skill1", "skill2"],
            "description": "Brief job description"
        }},
        ... (total 5 items)
    ]

    Requirements:
    - Exactly 5 recommendations
    - Valid JSON format
    - No markdown formatting
    - No additional text
    - Match percentage must be a number
    - All fields must be present
    """

    try:
        response = model.generate_content(prompt)
        print("Raw Gemini Response:", response.text)  # Debug log
        
        # Clean the response text
        clean_response = response.text.strip()
        if clean_response.startswith('```json'):
            clean_response = clean_response[7:-3].strip()
        elif clean_response.startswith('```'):
            clean_response = clean_response[3:-3].strip()
            
        print("Cleaned Response:", clean_response)  # Debug log
        
        # Parse JSON
        recommendations = json.loads(clean_response)
        
        # Validate recommendations
        if not isinstance(recommendations, list):
            print("❌ Error: Response is not a list")
            return []
            
        if len(recommendations) != 5:
            print("❌ Error: Did not receive exactly 5 recommendations")
            return recommendations[:5] if len(recommendations) > 5 else recommendations
            
        # Validate each recommendation
        valid_recommendations = []
        required_fields = ['title', 'match_percentage', 'matching_skills', 'recommended_skills', 'description']
        
        for rec in recommendations:
            if all(field in rec for field in required_fields):
                # Ensure match_percentage is a number between 0 and 100
                try:
                    rec['match_percentage'] = min(100, max(0, float(rec['match_percentage'])))
                except (ValueError, TypeError):
                    rec['match_percentage'] = 0
                    
                # Ensure skills are lists
                if not isinstance(rec['matching_skills'], list):
                    rec['matching_skills'] = [str(rec['matching_skills'])]
                if not isinstance(rec['recommended_skills'], list):
                    rec['recommended_skills'] = [str(rec['recommended_skills'])]
                    
                valid_recommendations.append(rec)
                
        return valid_recommendations

    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {str(e)}")
        print("Invalid JSON response:", clean_response)
        return []
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
            candidate.ats_score = int(ats_score)  # Ensure ats_score is stored as integer
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
                ats_score=int(ats_score),  # Ensure ats_score is stored as integer
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


def generate_resume_improvements(parsed_data):
    """Generate suggested improvements for the resume using Google Gemini."""
    prompt = f"""
    As an expert resume reviewer, analyze this resume data and provide specific, actionable improvements.
    Focus on enhancing both ATS compatibility and human readability.

    Resume Data:
    - Name: {parsed_data.get('name', '')}
    - Skills: {', '.join(parsed_data.get('skills', []))}
    - Education: {json.dumps(parsed_data.get('education', []))}
    - Experience: {json.dumps(parsed_data.get('experience', []))}
    - Projects: {json.dumps(parsed_data.get('projects', []))}

    Provide exactly 5 specific improvements in a JSON array format. Each improvement should be:
    1. Clear and actionable
    2. Specific to the resume content
    3. Focused on either ATS optimization or content enhancement
    4. Explained in a single, concise sentence

    Return ONLY a JSON array of 5 string improvements, like:
    [
        "Add measurable achievements to your experience at [Company Name]",
        "Include specific versions of technical skills (e.g., Python 3.x, React 18)",
        "Add duration for each project to demonstrate time management",
        "Incorporate more industry-specific keywords from job descriptions",
        "Quantify project impacts with metrics and percentages"
    ]

    The improvements should be tailored to this specific resume and its content.
    """

    try:
        response = model.generate_content(prompt)
        print("Raw Improvements Response:", response.text)  # Debug log
        
        # Clean the response text
        clean_response = response.text.strip()
        if clean_response.startswith('```json'):
            clean_response = clean_response[7:-3].strip()
        elif clean_response.startswith('```'):
            clean_response = clean_response[3:-3].strip()
            
        print("Cleaned Improvements Response:", clean_response)  # Debug log
        
        # Parse JSON
        improvements = json.loads(clean_response)
        
        # Validate improvements
        if not isinstance(improvements, list):
            print("❌ Error: Improvements response is not a list")
            return []
            
        # Ensure exactly 5 improvements
        if len(improvements) > 5:
            improvements = improvements[:5]
        elif len(improvements) < 5:
            default_improvements = [
                "Add more measurable achievements to your work experience",
                "Include specific versions of technical skills",
                "Add more details to your project descriptions",
                "Incorporate relevant industry keywords",
                "Quantify your achievements with metrics"
            ]
            improvements.extend(default_improvements[len(improvements):5])
        
        return improvements

    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error in improvements: {str(e)}")
        print("Invalid JSON response:", clean_response)
        return []
    except Exception as e:
        print(f"❌ Error generating improvements: {str(e)}")
        return []


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'resume' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        parsed_data = parse_resume_with_gemini(filepath)
        if parsed_data is None:
            return jsonify({'error': 'Unable to parse resume'})

        # Calculate ATS score
        ats_score = calculate_ats_score(parsed_data)
        
        # Generate improvements
        improvements = generate_resume_improvements(parsed_data)
        
        # Store the data
        if not store_parsed_data(parsed_data, ats_score):
            return jsonify({'error': 'Failed to store resume data'})

        # Return success response with parsed data, ATS score, and improvements
        return jsonify({
            'success': True,
            'parsed_data': parsed_data,
            'ats_score': ats_score,
            'improvements': improvements
        })

    except Exception as e:
        print(f"Error in upload_file: {str(e)}")
        return jsonify({'error': str(e)})


@app.route('/job-recommendations', methods=['POST'])
def get_jobs():
    try:
        data = request.get_json()
        if not data or 'skills' not in data:
            return jsonify({'error': 'No skills provided'}), 400
            
        skills = data['skills']
        if not isinstance(skills, list) or not skills:
            return jsonify({'error': 'Invalid skills format'}), 400
            
        recommendations = get_job_recommendations(skills)
        if not recommendations:
            return jsonify({'error': 'Could not generate recommendations'}), 500
            
        return jsonify({'recommendations': recommendations})
        
    except Exception as e:
        print(f"❌ Error in /job-recommendations route: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

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

@app.route('/generate-report', methods=['POST'])
def generate_report():
    try:
        data = request.get_json()
        
        # Create a BytesIO buffer for the PDF
        buffer = BytesIO()
        
        # Create the PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30
        )
        
        # Create the story (content) for the PDF
        story = []
        
        # Add title
        story.append(Paragraph("Resume Analysis Report", title_style))
        story.append(Spacer(1, 12))
        
        # Add personal information
        if 'name' in data:
            story.append(Paragraph(f"Name: {data['name']}", styles['Normal']))
            story.append(Spacer(1, 12))
        
        # Add ATS Score
        story.append(Paragraph(f"ATS Score: {data.get('ats_score', 'N/A')}%", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        # Add Skills
        if 'skills' in data:
            story.append(Paragraph("Skills:", styles['Heading2']))
            skills_text = ", ".join(data['skills'])
            story.append(Paragraph(skills_text, styles['Normal']))
            story.append(Spacer(1, 12))
        
        # Add Education
        if 'education' in data:
            story.append(Paragraph("Education:", styles['Heading2']))
            for edu in data['education']:
                story.append(Paragraph(f"• {edu}", styles['Normal']))
            story.append(Spacer(1, 12))
        
        # Add Experience
        if 'experience' in data:
            story.append(Paragraph("Experience:", styles['Heading2']))
            for exp in data['experience']:
                story.append(Paragraph(f"• {exp}", styles['Normal']))
            story.append(Spacer(1, 12))
        
        # Add Suggested Improvements
        if 'improvements' in data:
            story.append(Paragraph("Suggested Improvements:", styles['Heading2']))
            for imp in data['improvements']:
                story.append(Paragraph(f"• {imp}", styles['Normal']))
            story.append(Spacer(1, 12))
        
        # Add Job Recommendations
        if 'recommendations' in data:
            story.append(Paragraph("Job Recommendations:", styles['Heading2']))
            for rec in data['recommendations']:
                story.append(Paragraph(f"• {rec}", styles['Normal']))
        
        # Build the PDF
        doc.build(story)
        
        # Get the value of the BytesIO buffer
        pdf = buffer.getvalue()
        buffer.close()
        
        return send_file(
            BytesIO(pdf),
            mimetype='application/pdf',
            as_attachment=True,
            download_name='resume_analysis.pdf'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("✅ ResuMind server is running on http://localhost:5000")
    app.run(debug=True)

