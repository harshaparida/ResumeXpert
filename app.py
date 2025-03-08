import os
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import PyPDF2
import docx
import spacy
import json
from pdf2image import convert_from_path
import re
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create uploads folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Load spaCy model
nlp = spacy.load('en_core_web_sm')

# Initialize Gemini AI
load_dotenv()
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')


def extract_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def extract_text_from_docx(docx_path):
    doc = docx.Document(docx_path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])

def extract_text_from_image(image_path):
    return pytesseract.image_to_string(Image.open(image_path))

def parse_resume(file_path):
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.pdf':
        text = extract_text_from_pdf(file_path)
    elif file_ext == '.docx':
        text = extract_text_from_docx(file_path)
    elif file_ext in ['.jpg', '.jpeg', '.png']:
        text = extract_text_from_image(file_path)
    else:
        return None

    doc = nlp(text)
    
    # Extract information using NLP
    parsed_data = {
        'name': extract_name(doc),
        'email': extract_email(text),
        'phone': extract_phone(text),
        'skills': extract_skills(doc),
        'education': extract_education(doc),
        'experience': extract_experience(doc)
    }
    
    return parsed_data

def extract_name(doc):
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    return ""

def extract_email(text):
    match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    return match.group(0) if match else ""

def extract_phone(text):
    match = re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', text)
    return match.group(0) if match else ""

def extract_skills(doc):
    skill_keywords = ["Python", "Java", "JavaScript", "HTML", "CSS", "SQL", "React", "Angular", "Node.js"]
    return list(set(token.text for token in doc if token.text in skill_keywords))

def extract_education(doc):
    edu_keywords = ["Bachelor", "Master", "PhD", "BSc", "MSc", "B.E.", "M.E.", "B.Tech", "M.Tech"]
    return [sent.text.strip() for sent in doc.sents if any(keyword in sent.text for keyword in edu_keywords)]

def extract_experience(doc):
    job_titles = ["engineer", "developer", "manager", "analyst"]
    return [sent.text.strip() for sent in doc.sents if any(job in sent.text.lower() for job in job_titles)]

def calculate_ats_score(parsed_data):
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
        
        print("Calculated ATS Score:", score)  # Debugging line
        return jsonify({'score': score})
    return jsonify({'error': 'No resume data provided'})

def get_job_recommendations(skills):
    """
    Generate job recommendations dynamically using Google's Gemini AI based on the candidate's skills.
    """
    skills_text = ", ".join(skills)

    prompt = f"""
    You are an AI career advisor. Given the following skills: {skills_text}, 
    provide **exactly 5 job recommendations** in **JSON format**.

    Each job should include:
    - "title": Job title
    - "match_percentage": A number between 0 and 100 indicating how well the candidate's skills match
    - "matching_skills": List of skills that match the candidate's existing skills
    - "recommended_skills": List of additional skills they should learn
    - "description": A short job description

    Return only **valid JSON output**, with no extra text, like this:
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

        # 🚨 Debugging: Print raw response
        print("Raw Gemini Response:", response.text)

        if response.text:
            # Strip unnecessary formatting (removes Markdown code blocks)
            clean_response = response.text.strip().strip('```json').strip('```').strip()
            
            # Parse JSON safely
            recommendations = json.loads(clean_response)

            # Validate and return recommendations
            if isinstance(recommendations, list) and all(
                all(key in rec for key in ["title", "match_percentage", "matching_skills", "recommended_skills", "description"])
                for rec in recommendations
            ):
                # Sort by match percentage
                recommendations.sort(key=lambda x: x["match_percentage"], reverse=True)
                return recommendations

    except json.JSONDecodeError:
        print("❌ JSON parsing error: Gemini returned invalid JSON.")
    except Exception as e:
        print(f"❌ Error generating recommendations: {str(e)}")

    # Fallback recommendations if Gemini fails
    return [
        {
            "title": "Software Developer",
            "match_percentage": 75,
            "matching_skills": [skill for skill in skills if skill.lower() in ["python", "java", "javascript"]],
            "recommended_skills": ["Docker", "Kubernetes", "CI/CD"],
            "description": "A software developer position requiring strong coding skills."
        },
        {
            "title": "Full Stack Developer",
            "match_percentage": 70,
            "matching_skills": [skill for skill in skills if skill.lower() in ["javascript", "html", "css", "python"]],
            "recommended_skills": ["React", "Node.js", "MongoDB"],
            "description": "A full-stack developer role with a focus on web technologies."
        }
    ]


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

    parsed_data = parse_resume(filepath)
    if parsed_data is None:
        return jsonify({'error': 'Unsupported file format'})

    return jsonify({'success': True, 'parsed_data': parsed_data})

@app.route('/job-recommendations', methods=['POST'])
def get_jobs():
    data = request.get_json()
    return jsonify({'recommendations': get_job_recommendations(data['skills'])}) if data and 'skills' in data else jsonify({'error': 'No skills provided'})

if __name__ == '__main__':
    app.run(debug=True)