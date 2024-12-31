import React, { useState } from "react";
import axios from "axios";
import "./App.css";

interface AnalysisResult {
  matchPercentage: number;
  foundSkills: string[];
  missingSkills: string[];
}

const App: React.FC = () => {
  const [jobRole, setJobRole] = useState<string>("");
  const [jobDescription, setJobDescription] = useState<string>("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();  // Prevent the default form submission behavior

    // Ensure all required fields are filled
    if (!resumeFile || !jobRole || !jobDescription) {
      alert("Please fill all the fields and upload a resume.");
      return;
    }

    // Create a FormData object to send data as multipart/form-data
    const formData = new FormData();
    formData.append("resume", resumeFile);
    formData.append("jobRole", jobRole);
    formData.append("jobDescription", jobDescription);

    try {
      // Send the request to the backend
      const response = await axios.post("http://localhost:5000/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",  // Ensure the content type is correct for file uploads
        },
      });

      // Set the result received from the backend
      setResult(response.data.analysis);  // Update to match the response structure
      setError(null); // Clear any previous errors
    } catch (error) {
      console.error("Error analyzing resume:", error);
      if (axios.isAxiosError(error) && error.response) {
        // If the error is from the backend, show the error message
        setError(error.response.data.error || "An error occurred while analyzing the resume. Please try again.");
      } else {
        setError("An error occurred while analyzing the resume. Please try again.");
      }
    }
  };

  return (
    <div className="container">
      <h1>Resume Analyzer</h1>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Upload Resume (PDF/DOCX):</label>
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={(e) => setResumeFile(e.target.files ? e.target.files[0] : null)}
            required
          />
        </div>
        <div className="form-group">
          <label>Job Role:</label>
          <input
            type="text"
            value={jobRole}
            onChange={(e) => setJobRole(e.target.value)}
            placeholder="Enter job role"
            required
          />
        </div>
        <div className="form-group">
          <label>Job Description:</label>
          <textarea
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the job description here"
            required
          />
        </div>
        <button type="submit">Analyze Resume</button>
      </form>

      {error && <div className="error-message">{error}</div>}

      {result && (
        <div className="result-container">
          <h2>Analysis Result</h2>
          <p><strong>Match Percentage:</strong> {result.matchPercentage}%</p>
          <div className="skills-section">
            <h3>Skills Found</h3>
            <ul>
              {result.foundSkills.map((skill: string, index: number) => (
                <li key={index}>{skill}</li>
              ))}
            </ul>
            <h3>Missing Skills</h3>
            <ul>
              {result.missingSkills.map((skill: string, index: number) => (
                <li key={index}>{skill}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
