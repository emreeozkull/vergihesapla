const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const calculateButton = document.querySelector('.calculate-button');
const uploadButton = document.querySelector('.upload-button');

// Add this at the top with your other constants
let currentCalculatorId = null;

// Add this near the top with other constants
const calculateForm = document.getElementById('calculateForm');

// Handle click on upload button
uploadButton.addEventListener('click', () => {
    fileInput.click();
});

// Handle file selection
fileInput.addEventListener('change', handleFiles);

// Handle drag and drop
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    handleFiles({ target: { files } });
});

// Update validation feedback function
function showValidation(message, type = 'error') {
    // Remove any existing validation messages
    const existingMessages = document.querySelectorAll('.validation-message');
    existingMessages.forEach(msg => msg.remove());

    // Create new validation message
    const validationDiv = document.createElement('div');
    validationDiv.className = `validation-message ${type}`;
    validationDiv.innerHTML = `
        <i class="fas fa-${type === 'error' ? 'exclamation-circle' : 'check-circle'}"></i>
        ${message}
    `;
    document.body.appendChild(validationDiv);
    
    setTimeout(() => {
        validationDiv.style.animation = 'slideUp 0.3s ease reverse';
        setTimeout(() => validationDiv.remove(), 300);
    }, 5000);
}

// Add file upload progress
function updateProgress(file, progress) {
    const progressDiv = document.createElement('div');
    progressDiv.className = 'upload-progress';
    progressDiv.innerHTML = `<div class="progress-bar" style="width: ${progress}%"></div>`;
    return progressDiv;
}

// Update handleFiles function
function handleFiles(e) {
    const files = Array.from(e.target.files);
    const validFiles = files.filter(file => {
        if (file.type !== 'application/pdf') {
            showValidation('Sadece PDF dosyaları yükleyebilirsiniz.');
            return false;
        }
        if (file.size > 10 * 1024 * 1024) {
            showValidation('Dosya boyutu 10MB\'dan küçük olmalıdır.');
            return false;
        }
        return true;
    });

    validFiles.forEach(file => {
        const fileElement = document.createElement('div');
        fileElement.className = 'file-item';
        fileElement.innerHTML = `
            <i class="far fa-file-pdf"></i>
            <div class="file-details">
                <span class="file-name">${file.name}</span>
                <span class="file-size">${(file.size / 1024 / 1024).toFixed(2)} MB</span>
            </div>
            <button class="remove-file" onclick="this.parentElement.remove(); updateCalculateButton();">
                <i class="fas fa-times"></i>
            </button>
        `;
        fileList.appendChild(fileElement);

        // Upload the file immediately after validation
        uploadPDF(file);
    });

    if (validFiles.length > 0) {
        showValidation('Dosyalar başarıyla yüklendi.', 'success');
    }

    updateCalculateButton();
}

// Update uploadPDF function
async function uploadPDF(file) {
    const formData = new FormData();
    formData.append('pdf', file);
    
    // Add calculator_id to formData if we have one
    if (currentCalculatorId) {
        formData.append('calculator_id', currentCalculatorId);
    }
    
    try {
        const response = await fetch('upload-pdf/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        });

        if (!response.ok) {
            throw new Error('Upload failed');
        }

        const data = await response.json();
        console.log('Upload successful:', data);
        // Store the calculator_id for future uploads
        currentCalculatorId = data.calculator_id;
    } catch (error) {
        console.error('Upload error:', error);
        showValidation('Dosya yükleme başarısız oldu.', 'error');
    }
}

// Add function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function updateCalculateButton() {
    const hasFiles = fileList.children.length > 0;
    calculateButton.disabled = !hasFiles;
    
}

// Update the calculate button click handler
calculateButton.addEventListener('click', async () => {
    if (!currentCalculatorId) {
        showValidation('Lütfen önce PDF dosyası yükleyin.', 'error');
        return;
    }

    try {
        const response = await fetch('/calculator/results/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                calculator_id: currentCalculatorId
            })
        });

        if (response.ok) {
            // Redirect to results page with the response HTML
            document.open();
            document.write(await response.text());
            document.close();
        } else {
            throw new Error('Calculation failed');
        }
    } catch (error) {
        console.error('Calculation error:', error);
        showValidation('Hesaplama işlemi başarısız oldu.', 'error');
    }
});
