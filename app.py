from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename
import pdfplumber
from docx import Document
from transformers import pipeline
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load a pretrained NLP pipeline for job skills
job_skill_extractor = pipeline("ner", model="dslim/bert-base-NER")

app = Flask(__name__)
CORS(app)  # To allow cross-origin requests (for React frontend)

# Set the upload folder and allowed file extensions
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

logging.info(f"Upload folder path: {os.path.abspath(UPLOAD_FOLDER)}")

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Check if file is of allowed type
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Extract text from PDF using pdfplumber
def extract_text_from_pdf(filepath):
    try:
        with pdfplumber.open(filepath) as pdf:
            text = "".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        return text
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {e}")
        return ""

# Extract text from DOCX using python-docx
def extract_text_from_docx(filepath):
    try:
        doc = Document(filepath)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text
    except Exception as e:
        logging.error(f"Error extracting text from DOCX: {e}")
        return ""

# Analyze resume with AI
def analyze_resume_with_ai(resume_text, job_description):
    # Placeholder for AI analysis logic
    # This function should return the analysis result
    return {"skills": ["Python", "Machine Learning"], "match_percentage": 85}

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'resume' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['resume']
        job_description = request.form.get('jobDescription', '')
        job_role = request.form.get('jobRole', '')

        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Extract text based on file type
            if file.filename.endswith('.pdf'):
                resume_text = extract_text_from_pdf(file_path)
            elif file.filename.endswith('.docx'):
                resume_text = extract_text_from_docx(file_path)
            else:
                return jsonify({'error': 'Unsupported file format.'}), 400

            # Debugging: Print extracted resume text and job description
            logging.info("Extracted Resume Text: %s", resume_text)
            logging.info("Job Description: %s", job_description)

            # Analyze resume using AI
            analysis_result = analyze_resume_with_ai(resume_text, job_description)

            # Debugging: Print analysis result
            logging.info("Analysis Result: %s", analysis_result)

            # Optionally delete the uploaded file after processing
            # os.remove(file_path)

            return jsonify({
                'message': f'Resume uploaded and analyzed for job role: {job_role}',
                'analysis': analysis_result
            }), 200
        else:
            return jsonify({'error': 'Invalid file type. Please upload a PDF or Word document.'}), 400
    except Exception as e:
        logging.error(f"Error in upload_file: {e}")
        return jsonify({'error': 'An error occurred while processing the file. Please try again later.'}), 500

if __name__ == '__main__':
    app.run(debug=True)