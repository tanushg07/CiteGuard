document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const form = document.getElementById('verifyForm');
    const submitBtn = document.getElementById('submitBtn');
    const btnText = submitBtn.querySelector('.btn-text');
    const loader = submitBtn.querySelector('.loader');
    
    const targetFile = document.getElementById('targetFile');
    const sourceFile = document.getElementById('sourceFile');
    const targetFileName = document.getElementById('targetFileName');
    const sourceFileName = document.getElementById('sourceFileName');
    
    const targetDropZone = document.getElementById('targetDropZone');
    const sourceDropZone = document.getElementById('sourceDropZone');
    
    const errorBanner = document.getElementById('errorBanner');
    const errorText = document.getElementById('errorText');
    
    const resultsSection = document.getElementById('resultsSection');
    const resultsContainer = document.getElementById('resultsContainer');
    
    // Stats elements
    const statSupported = document.getElementById('statSupported');
    const statContradicted = document.getElementById('statContradicted');
    const statInsufficient = document.getElementById('statInsufficient');

    // API URL
    const API_URL = 'http://127.0.0.1:8000/api/verify';

    // Setup Drag & Drop and File Selection
    function setupFileInput(input, dropZone, nameDisplay) {
        // Handle file selection via click
        input.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                const file = e.target.files[0];
                if (file.type !== "application/pdf") {
                    showError("Please upload PDF files only.");
                    input.value = "";
                    nameDisplay.textContent = "No file selected";
                    nameDisplay.classList.remove('selected');
                    return;
                }
                nameDisplay.textContent = file.name;
                nameDisplay.classList.add('selected');
                hideError();
            }
        });

        // Drag and drop events
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.remove('dragover');
            }, false);
        });

        dropZone.addEventListener('drop', (e) => {
            let dt = e.dataTransfer;
            let files = dt.files;
            
            if (files.length > 0) {
                if (files[0].type !== "application/pdf") {
                    showError("Please drop PDF files only.");
                    return;
                }
                input.files = files;
                // Trigger change event manually
                const event = new Event('change');
                input.dispatchEvent(event);
            }
        }, false);
    }

    setupFileInput(targetFile, targetDropZone, targetFileName);
    setupFileInput(sourceFile, sourceDropZone, sourceFileName);

    // Form Submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (!targetFile.files[0] || !sourceFile.files[0]) {
            showError("Please select both target and source PDFs.");
            return;
        }

        hideError();
        setLoadingState(true);
        resultsSection.classList.add('hidden');

        const formData = new FormData();
        formData.append('target_file', targetFile.files[0]);
        formData.append('source_file', sourceFile.files[0]);

        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.length === 0) {
                showError("No citation claims found in the target document.");
            } else {
                renderResults(data);
            }
        } catch (error) {
            console.error("Verification Error:", error);
            showError(error.message === "Failed to fetch" 
                ? "Could not connect to the backend server. Is it running on port 8000?" 
                : error.message);
        } finally {
            setLoadingState(false);
        }
    });

    // Helper functions
    function showError(message) {
        errorText.textContent = message;
        errorBanner.classList.remove('hidden');
    }

    function hideError() {
        errorBanner.classList.add('hidden');
    }

    function setLoadingState(isLoading) {
        submitBtn.disabled = isLoading;
        if (isLoading) {
            btnText.classList.add('hidden');
            loader.classList.remove('hidden');
        } else {
            btnText.classList.remove('hidden');
            loader.classList.add('hidden');
        }
    }

    function renderResults(results) {
        resultsContainer.innerHTML = '';
        
        let stats = {
            SUPPORTED: 0,
            CONTRADICTED: 0,
            INSUFFICIENT: 0
        };

        results.forEach((item, index) => {
            // Update stats
            stats[item.nli_label]++;

            // Create card
            const card = document.createElement('div');
            card.className = 'result-card';
            
            // Format confidence score
            const confidencePct = Math.round(item.nli_confidence * 100);
            
            // Handle numerical mismatch warning
            let numWarning = '';
            if (item.numerical_match === false) {
                numWarning = `<div class="numerical-warning">⚠️ Numerical Contradiction Detected (Numbers in claim don't match evidence)</div>`;
            }

            // Get the best evidence text
            const evidenceText = item.evidence.length > 0 ? item.evidence[0].evidence_text : "No relevant evidence chunk found in source.";

            card.innerHTML = `
                <div class="result-header">
                    <span class="status-label ${item.nli_label}">${item.nli_label}</span>
                    <span class="confidence-score">Confidence: ${confidencePct}%</span>
                </div>
                <div class="result-body">
                    <div class="text-block claim-block">
                        <h4>Claim (Target Paper)</h4>
                        <p>"${escapeHTML(item.claim_text)}"</p>
                    </div>
                    <div class="text-block evidence-block">
                        <h4>Evidence (Source Paper)</h4>
                        <p>"${escapeHTML(evidenceText)}"</p>
                        ${numWarning}
                    </div>
                </div>
            `;
            
            resultsContainer.appendChild(card);
        });

        // Update UI stats
        statSupported.textContent = stats.SUPPORTED;
        statContradicted.textContent = stats.CONTRADICTED;
        statInsufficient.textContent = stats.INSUFFICIENT;

        // Show results
        resultsSection.classList.remove('hidden');
        
        // Scroll to results
        setTimeout(() => {
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }

    function escapeHTML(str) {
        if (!str) return "";
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }
});
