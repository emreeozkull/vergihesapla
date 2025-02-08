const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const calculateButton = document.querySelector('.calculate-button');
const uploadButton = document.querySelector('.upload-button');

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
    });

    if (validFiles.length > 0) {
        showValidation('Dosyalar başarıyla yüklendi.', 'success');
    }

    updateCalculateButton();
}

function updateCalculateButton() {
    const hasFiles = fileList.children.length > 0;
    calculateButton.disabled = !hasFiles;
}
