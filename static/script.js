const recordButton = document.getElementById('record');
const stopButton = document.getElementById('stop');
const timerDisplay = document.getElementById('timer');

let mediaRecorder;
let audioChunks = [];
let startTime;

function formatTime(time) {
  const minutes = Math.floor(time / 60);
  const seconds = Math.floor(time % 60);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

recordButton.addEventListener('click', () => {
  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.start();
      
      startTime = Date.now();
      let timerInterval = setInterval(() => {
        const elapsedTime = Math.floor((Date.now() - startTime) / 1000);
        timerDisplay.textContent = formatTime(elapsedTime);
      }, 1000);
      
      audioChunks = [];
      mediaRecorder.ondataavailable = e => {
        audioChunks.push(e.data);
      };
      
      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const formData = new FormData();
        formData.append('audio_data', audioBlob, 'recorded_audio.wav');
        
        fetch('/upload', {
          method: 'POST',
          body: formData
        })
        .then(response => {
          if (!response.ok) {
            throw new Error('Network response was not ok');
          }
          location.reload(); // Refresh page to update file list
          return response.text();
        })
        .catch(error => {
          console.error('Error uploading audio:', error);
        });
      };
    })
    .catch(error => {
      console.error('Error accessing microphone:', error);
    });
  
  recordButton.disabled = true;
  stopButton.disabled = false;
});

stopButton.addEventListener('click', () => {
  if (mediaRecorder) {
    mediaRecorder.stop();
  }
  recordButton.disabled = false;
  stopButton.disabled = true;
});

// Initially disable the stop button
stopButton.disabled = true;

// Modal functionality for viewing text files
document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('textModal');
  const modalText = document.getElementById('modalText');
  const closeBtn = document.querySelector('.close');

  document.querySelectorAll('.view-text').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      const url = link.getAttribute('data-url');
      fetch(url)
        .then(response => response.text())
        .then(data => {
          modalText.textContent = data;
          modal.style.display = "block";
        })
        .catch(err => console.error('Error loading text file:', err));
    });
  });

  closeBtn.addEventListener('click', () => {
    modal.style.display = "none";
  });

  window.addEventListener('click', event => {
    if (event.target == modal) {
      modal.style.display = "none";
    }
  });
});
