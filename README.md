# AI Resume Analyzer

A modern web application that analyzes resumes using AI, calculates ATS scores, and provides job recommendations based on skills.

## Features

- Multi-format resume parsing (PDF, DOCX, JPG, PNG)
- OCR support for image-based resumes
- Accurate information extraction using NLP
- ATS (Applicant Tracking System) score calculation
- Job recommendations based on skills
- Modern, responsive UI with drag-and-drop support

## Prerequisites

- Python 3.8+
- Tesseract OCR (for image processing)
- Required Python packages (listed in requirements.txt)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-resume-analyzer
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

4. Install Tesseract OCR:
- Windows: Download and install from https://github.com/UB-Mannheim/tesseract/wiki
- Linux: `sudo apt-get install tesseract-ocr`
- Mac: `brew install tesseract`

5. Download the spaCy model:
```bash
python -m spacy download en_core_web_sm
```

## Usage

1. Start the Flask application:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. Upload a resume by either:
   - Dragging and dropping the file onto the upload area
   - Clicking "Browse Files" and selecting the file

4. View the parsed information, calculate the ATS score, and get job recommendations

## Supported File Formats

- PDF (.pdf)
- Microsoft Word (.docx)
- Images (.jpg, .jpeg, .png)

## Technical Details

- Backend: Flask (Python)
- Frontend: HTML5, CSS3, JavaScript
- NLP: spaCy
- OCR: Tesseract
- Document Processing: PyPDF2, python-docx
- Image Processing: Pillow, pdf2image

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 