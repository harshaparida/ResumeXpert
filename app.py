import os
import re
import json
import docx
import pdfplumber
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename
from resumeparser import ats_extractor

app = Flask(__name__)

UPLOAD_PATH = os.path.join(os.getcwd(), "__DATA__")
os.makedirs(UPLOAD_PATH, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/process", methods=["POST"])
def process():
    job_description = request.form.get('job-description')

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_PATH, filename)
        file.save(file_path)

        try:
            parsed_resume = parse_resume(file_path, filename)

            return jsonify({
                "message": "Application submitted successfully!",
                "parsed_resume": parsed_resume,
                "job_description": job_description
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    return jsonify({"error": "File type not allowed"}), 400

def parse_resume(file_path, filename):
    ext = filename.lower().split('.')[-1]

    # Attempt structured parsing using ats_extractor
    try:
        structured_data = ats_extractor(file_path)
        if structured_data and "name" in structured_data:  # Validate extraction success
            return structured_data
    except Exception as e:
        print(f"ATS Extractor failed: {e}")

    # Fallback: Extract raw text manually
    if ext == "pdf":
        resume_text = read_pdf_file(file_path)
    elif ext == "docx":
        resume_text = read_docx_file(file_path)
    elif ext == "txt":
        with open(file_path, 'r', encoding='utf-8') as f:
            resume_text = f.read()
    else:
        raise ValueError("Unsupported file format")

    # Process extracted text into structured sections
    return extract_resume_sections(resume_text)

def extract_resume_sections(text):
    """ Extract key details from resume text. """
    sections = {
        "name": extract_name(text),
        "contact": extract_contact(text),
        "skills": extract_skills(text),
        "education": extract_education(text),
        "experience": extract_experience(text)
    }
    return sections

def read_pdf_file(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()

def read_docx_file(path):
    doc = docx.Document(path)
    return "\n".join([para.text for para in doc.paragraphs]).strip()

### 🚀 Implemented Extraction Functions ###
def extract_name(text):
    """ Extracts the first line assuming it's the candidate's name. """
    lines = text.split("\n")
    return lines[0].strip() if lines else "Unknown"

def extract_contact(text):
    """ Extracts phone, email, and LinkedIn using regex. """
    phone_pattern = re.compile(r'\b\d{10,13}\b')  # Matches 10 to 13 digit phone numbers
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    linkedin_pattern = re.compile(r'linkedin\.com/in/[a-zA-Z0-9_-]+', re.IGNORECASE)

    phone = phone_pattern.findall(text)
    email = email_pattern.findall(text)
    linkedin = linkedin_pattern.findall(text)

    return {
        "phone": phone[0] if phone else "Not Found",
        "email": email[0] if email else "Not Found",
        "linkedin": f"https://{linkedin[0]}" if linkedin else "Not Found"
    }

def extract_education(text):
    """ Extracts education details from the resume using keyword-based search. """
    education_keywords = ["Bachelor", "Master", "BSc", "MSc", "PhD", "University", "College", "Institute"]
    education_lines = [line.strip() for line in text.split("\n") if any(word in line for word in education_keywords)]
    return education_lines if education_lines else "Not Found"

def extract_experience(text):
    """ Extracts work experience (job titles, company names, durations). """
    experience_keywords = ["Intern", "Engineer", "Developer", "Manager", "Analyst", "Consultant"]
    experience_lines = [line.strip() for line in text.split("\n") if any(word in line for word in experience_keywords)]
    return experience_lines if experience_lines else "Not Found"

def extract_skills(text):
    """ Matches predefined skills in resume text. """
    skills_db = ["Python", "Machine Learning", "Deep Learning", "SQL", "Pandas", "NumPy", "Data Visualization", "TensorFlow", "Keras", "Statistics"]
    found_skills = [skill for skill in skills_db if skill.lower() in text.lower()]
    return found_skills if found_skills else "Not Found"

if __name__ == "__main__":
    app.run(port=8000, debug=True)
