document.getElementById('upload-form').onsubmit = async function(event) {
    event.preventDefault();

    const formData = new FormData();
    const fileInput = document.getElementById('file');
    const directoryInput = document.getElementById('directory');

    if (fileInput.files.length > 0) {
        formData.append('file', fileInput.files[0]);
    }

    for (const file of directoryInput.files) {
        formData.append('directory', file);
    }

    const response = await fetch('/upload', {
        method: 'POST',
        body: formData
    });

    const result = await response.json();
    if (response.ok) {
        alert('Upload successful');
    } else {
        alert('Upload failed: ' + result.message);
    }
};

