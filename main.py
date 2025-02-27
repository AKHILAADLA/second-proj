from datetime import datetime
import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename

# Google Cloud imports
from google.cloud import speech
from google.cloud import texttospeech_v1
from google.cloud import language_v2

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for flashing messages

# Define directories for uploads and generated files
UPLOAD_FOLDER = 'uploads'
TRANSCRIPTS_FOLDER = 'transcripts'  # For audio transcriptions + sentiment
TTS_FOLDER = 'tts'
TTS_TEXT_FOLDER = 'tts_texts'  # For text input + sentiment

# Allowed audio file extension
ALLOWED_EXTENSIONS = {'wav'}

# Set app config
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure necessary directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TRANSCRIPTS_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)
os.makedirs(TTS_TEXT_FOLDER, exist_ok=True)

# ----- Helper Functions -----
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files(folder):
    """Return a sorted list of files in a given folder."""
    files = os.listdir(folder)
    files.sort(reverse=True)
    return files

# ----- Google Cloud API Functions -----
def sample_recognize(content):
    """Transcribe audio content using Google Cloud Speech-to-Text."""
    client = speech.SpeechClient()
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        language_code="en-US",
        model="latest_long",
        audio_channel_count=1,
        enable_word_confidence=True,
        enable_word_time_offsets=True,
    )
    operation = client.long_running_recognize(config=config, audio=audio)
    response = operation.result(timeout=90)

    transcript = ''
    for result in response.results:
        transcript += result.alternatives[0].transcript + '\n'
    return transcript

def sample_synthesize_speech(text=None, ssml=None):
    """Synthesize speech from text using Google Cloud Text-to-Speech."""
    client = texttospeech_v1.TextToSpeechClient()
    synthesis_input = texttospeech_v1.SynthesisInput(text=text) if text else texttospeech_v1.SynthesisInput(ssml=ssml)
    voice = texttospeech_v1.VoiceSelectionParams(
        language_code="en-GB",  # Using UK English as per assignment
    )
    audio_config = texttospeech_v1.AudioConfig(audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16)
    
    request_tts = texttospeech_v1.SynthesizeSpeechRequest(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )
    response = client.synthesize_speech(request=request_tts)
    return response.audio_content

def sample_analyze_sentiment(text_content):
    """Analyze sentiment using Google Cloud Natural Language API."""
    client = language_v2.LanguageServiceClient()
    document = {
        "content": text_content,
        "type_": language_v2.Document.Type.PLAIN_TEXT,
        "language_code": "en",
    }
    encoding_type = language_v2.EncodingType.UTF8

    response = client.analyze_sentiment(request={"document": document, "encoding_type": encoding_type})
    
    # Compute compound score (score * magnitude) for overall sentiment.
    compound = response.document_sentiment.score * response.document_sentiment.magnitude

    if compound > 0.75:
        overall_sentiment = "POSITIVE"
    elif compound < -0.75:
        overall_sentiment = "NEGATIVE"
    else:
        overall_sentiment = "NEUTRAL"

    # Build detailed sentiment analysis string.
    result_str = f"--- Sentiment Analysis ---\n"
    result_str += f"Overall Sentiment Score: {response.document_sentiment.score}\n"
    result_str += f"Overall Sentiment Magnitude: {response.document_sentiment.magnitude}\n"
    result_str += f"Compound Score: {compound}\n"
    result_str += f"Overall Sentiment: {overall_sentiment}\n\n"

    return result_str, overall_sentiment

# ----- Flask Routes -----
@app.route('/')
def index():
    # List files from folders for display on the homepage.
    recordings = get_files(UPLOAD_FOLDER)
    transcripts = get_files(TRANSCRIPTS_FOLDER)
    tts_files = get_files(TTS_FOLDER)
    tts_texts = get_files(TTS_TEXT_FOLDER)
    return render_template('index.html',
                           recordings=recordings,
                           transcripts=transcripts,
                           tts_files=tts_files,
                           tts_texts=tts_texts)

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio data provided.')
        return redirect(request.url)
    
    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file.')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Generate a unique base filename.
        base_filename = datetime.now().strftime("%Y%m%d-%I%M%S%p")
        audio_filename = base_filename + '.wav'
        audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)
        file.save(audio_path)

        # Transcribe the audio.
        with open(audio_path, 'rb') as audio_file:
            content = audio_file.read()
        transcript_text = sample_recognize(content)

        # Analyze sentiment on the transcription.
        sentiment_result, overall_sentiment = sample_analyze_sentiment(transcript_text)

        # Combine transcript and sentiment analysis.
        combined_text = (
            f"--- Transcript ---\n{transcript_text}\n\n" +
            sentiment_result
        )
        transcript_file = base_filename + '.txt'
        transcript_path = os.path.join(TRANSCRIPTS_FOLDER, transcript_file)
        with open(transcript_path, 'w') as f:
            f.write(combined_text)

        flash(f'Audio uploaded, transcribed, and sentiment analyzed successfully. Sentiment: {overall_sentiment}')
    else:
        flash('Invalid file type.')
    
    return redirect('/')

@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form['text']
    if not text:
        flash('Please enter some text.')
        return redirect(request.url)
    
    # Generate a unique base filename.
    base_filename = datetime.now().strftime("%Y%m%d-%I%M%S%p")
    
    # Analyze sentiment on the text.
    sentiment_result, overall_sentiment = sample_analyze_sentiment(text)
    
    # Combine original text and sentiment analysis.
    combined_text = (
        f"--- Original Text ---\n{text}\n\n" +
        sentiment_result
    )
    text_filename = base_filename + '.txt'
    text_path = os.path.join(TTS_TEXT_FOLDER, text_filename)
    with open(text_path, 'w') as text_file:
        text_file.write(combined_text)
    
    # Convert text to speech.
    audio_content = sample_synthesize_speech(text=text)
    audio_filename = base_filename + '.wav'
    tts_audio_path = os.path.join(TTS_FOLDER, audio_filename)
    with open(tts_audio_path, 'wb') as out:
        out.write(audio_content)
    
    flash(f'Text saved, converted to audio, and sentiment analyzed successfully. Sentiment: {overall_sentiment}')
    return redirect('/')

# Routes to serve files
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/transcripts/<filename>')
def transcript_file(filename):
    return send_from_directory(TRANSCRIPTS_FOLDER, filename)

@app.route('/tts/<filename>')
def tts_file(filename):
    return send_from_directory(TTS_FOLDER, filename)

@app.route('/tts_texts/<filename>')
def tts_text_file(filename):
    return send_from_directory(TTS_TEXT_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
