from flask import Blueprint, request, jsonify, session
import whisper
import tempfile
import os
from datetime import datetime
import os
os.environ["PATH"] += os.pathsep + r"C:\Users\douni\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"

speech_bp = Blueprint('speech', __name__)

# Load Whisper model once when starting the app
model = whisper.load_model("base")


@speech_bp.route('/api/upload-audio', methods=['POST'])
def upload_audio():
   

    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    tmp_path = None
    try:
        audio_file = request.files['audio']

        # Use .webm suffix to match what the browser actually sends
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp_path = tmp.name
            audio_file.save(tmp_path)  # ← pass the PATH string, not the file object

        result = model.transcribe(tmp_path)

        if 'conversation_history' not in session:
            session['conversation_history'] = []

        session['conversation_history'].append({
            'role': 'user',
            'content': result['text'],
            'timestamp': datetime.now().isoformat(),
            'from_speech': True
        })
        session.modified = True

        return jsonify({
            "text": result["text"],
            "language": result["language"]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()  # full error in your terminal
        return jsonify({"error": str(e)}), 500

    finally:
        # Always clean up the temp file even if transcription fails
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)