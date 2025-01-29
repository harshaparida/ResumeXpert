import os
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename
from pypdf import PdfReader
import json
from resumeparser import ats_extractor
import openai

app = Flask(__name__)

# Set up OpenAI API key
openai.api_key = os.environ.get("OPENAI_API_KEY")

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
            if filename.lower().endswith('.pdf'):
                data = _read_pdf_file(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = f.read()
            
            processed_data = ats_extractor(data)
            
            return jsonify({
                "message": "Application submitted successfully!",
                "processed_data": json.loads(processed_data),
                "job_description": job_description
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            # Clean up the uploaded file
            os.remove(file_path)
    
    return jsonify({"error": "File type not allowed"}), 400

def _read_pdf_file(path):
    reader = PdfReader(path) 
    data = ""

    for page in reader.pages:
        data += page.extract_text()

    return data 

if __name__ == "__main__":
    app.run(port=8000, debug=True)


