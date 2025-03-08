document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const resultsSection = document.getElementById('resultsSection');
    const atsScoreBtn = document.getElementById('atsScoreBtn');
    const jobRecommendBtn = document.getElementById('jobRecommendBtn');
    const atsScoreSection = document.getElementById('atsScoreSection');
    const jobRecommendationsSection = document.getElementById('jobRecommendationsSection');

    let parsedData = null;

    // Drag and drop functionality
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        dropZone.classList.add('highlight');
    }

    function unhighlight(e) {
        dropZone.classList.remove('highlight');
    }

    dropZone.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length > 0) {
            const file = files[0];
            uploadFile(file);
        }
    }

    async function uploadFile(file) {
        const formData = new FormData();
        formData.append('resume', file);

        showLoading();

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.error) {
                alert(data.error);
                return;
            }

            parsedData = data.parsed_data;
            displayResults(parsedData);
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while processing the resume.');
        } finally {
            hideLoading();
        }
    }

    function displayResults(data) {
        // Display personal details
        document.getElementById('name').textContent = data.name || 'N/A';
        document.getElementById('email').textContent = data.email || 'N/A';
        document.getElementById('phone').textContent = data.phone || 'N/A';

        // Display skills
        const skillsContainer = document.getElementById('skills');
        skillsContainer.innerHTML = '';
        data.skills.forEach(skill => {
            const skillTag = document.createElement('span');
            skillTag.className = 'skill-tag';
            skillTag.textContent = skill;
            skillsContainer.appendChild(skillTag);
        });

        // Display education
        const educationContainer = document.getElementById('education');
        educationContainer.innerHTML = '';
        data.education.forEach(edu => {
            const p = document.createElement('p');
            p.textContent = edu;
            educationContainer.appendChild(p);
        });

        // Display experience
        const experienceContainer = document.getElementById('experience');
        experienceContainer.innerHTML = '';
        data.experience.forEach(exp => {
            const p = document.createElement('p');
            p.textContent = exp;
            experienceContainer.appendChild(p);
        });

        resultsSection.classList.remove('hidden');
        atsScoreSection.classList.add('hidden');
        jobRecommendationsSection.classList.add('hidden');
    }

    atsScoreBtn.addEventListener('click', async () => {
        if (!parsedData) return;
    
        showLoading();
    
        try {
            const response = await fetch('/ats-score', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ parsed_data: parsedData }) // Corrected the body format
            });
    
            const data = await response.json();
            document.getElementById('atsScoreValue').textContent = Math.round(data.score); // Corrected key to data.score
            atsScoreSection.classList.remove('hidden');
            jobRecommendationsSection.classList.add('hidden');
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while calculating the ATS score.');
        } finally {
            hideLoading();
        }
    });

    jobRecommendBtn.addEventListener('click', async () => {
        if (!parsedData) return;

        showLoading();

        try {
            const response = await fetch('/job-recommendations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ skills: parsedData.skills })
            });

            const data = await response.json();
            if (data.error) {
                alert(data.error);
                return;
            }

            displayJobRecommendations(data.recommendations);
            jobRecommendationsSection.classList.remove('hidden');
            atsScoreSection.classList.add('hidden');
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while fetching job recommendations.');
        } finally {
            hideLoading();
        }
    });

    function displayJobRecommendations(recommendations) {
        const container = document.getElementById('recommendationsList');
        container.innerHTML = '';

        recommendations.forEach(job => {
            const jobCard = document.createElement('div');
            jobCard.className = 'job-card';
            
            // Create HTML for recommended skills
            const recommendedSkills = job.recommended_skills 
                ? `<p class="recommended-skills">
                     <strong>Recommended Skills to Learn:</strong> 
                     ${job.recommended_skills.join(', ')}
                   </p>`
                : '';

            jobCard.innerHTML = `
                <h3>${job.title}</h3>
                <p class="match-percentage">Match: ${job.match_percentage}%</p>
                <p class="job-description">${job.description}</p>
                <p class="matching-skills">
                    <strong>Matching Skills:</strong> 
                    ${job.matching_skills.map(skill => `<span class="skill-tag">${skill}</span>`).join(' ')}
                </p>
                ${recommendedSkills}
            `;
            container.appendChild(jobCard);
        });
    }

    function showLoading() {
        loadingOverlay.classList.remove('hidden');
    }

    function hideLoading() {
        loadingOverlay.classList.add('hidden');
    }
});