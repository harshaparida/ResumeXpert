# CVXpert – AI-Powered Resume Analyzer & Job Matcher

CVXpert is a smart resume analyzer and job matcher web application built with **Flask (Python)**, **HTML/CSS/JavaScript**, and integrated with **Google Gemini AI**. It allows users to upload resumes, extract details, calculate ATS scores, and get personalized job recommendations.

---

## Features

- **Resume Parsing**: Extracts contact details, education, experience, skills, and projects.
- **Multi-Format Support**: Supports PDF, DOC, DOCX, TXT, PNG, JPG, and JPEG files.
- **ATS Score Calculation**: Matches resumes with job descriptions to compute a score.
- **AI-Powered Recommendations**: Suggests job roles using Google Gemini.
- **MySQL Database Integration**: Stores all parsed resume data.
- **User Authentication**: Login/Register system to keep user data secure.
- **Admin Dashboard**: View, search, filter, and export all candidate data.
- **Data Export**: Export resume data as CSV or PDF.

---

## Tech Stack

- **Frontend**: HTML, CSS, JavaScript
- **Backend**: Flask (Python)
- **Database**: MySQL with SQLAlchemy ORM
- **AI Integration**: Google Gemini (via Gemini API)
- **OCR**: Tesseract (for image-based resumes)
- **File Handling**: pdf2image, PyPDF2, python-docx
- **PDF Export**: ReportLab

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/cvxpert.git
cd cvxpert
```

### 2. Install required Python packages

```bash
pip install -r requirements.txt
```

### 3. Set up your `.env` file

Create a `.env` file with your Google Gemini API key and database credentials.

```env
GEMINI_API_KEY=your_api_key
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=cvxpert_db
DB_HOST=localhost
```

### 4. Run the Flask app

```bash
python app.py
```

Go to `http://localhost:5000` in your browser to access the app.

---

## Folder Structure

```
cvxpert/
├── static/               # CSS, JS, and file uploads
├── templates/            # HTML templates
├── app.py                # Main Flask app
├── models.py             # SQLAlchemy database models
├── requirements.txt      # Python dependencies
├── .env                  # API keys and DB config (not tracked by git)
└── README.md             # Project documentation
```

---

## SQLAlchemy Model Example

```python
class Candidate(Base):
    __tablename__ = 'candidates'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    phone = Column(String(20))
    education = Column(Text)
    experience = Column(Text)
    skills = Column(Text)
    projects = Column(Text)
    ats_score = Column(Integer)
    job_recommendations = Column(Text)
    uploaded_at = Column(String(100))
```
## License

This project is licensed under the **MIT License**.
