from flask import Blueprint, render_template, session, request, jsonify
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from datetime import datetime
import re
from deepface import DeepFace
import cv2
import numpy as np
import base64
import os
import tempfile
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Secure API key loading
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

therapist_bp = Blueprint('therapist', __name__)


# ─────────────────────────────────────────────
#  AUDIO TRANSCRIPTION (Whisper)
# ─────────────────────────────────────────────
@therapist_bp.route('/api/upload-audio', methods=['POST'])
def upload_audio():
    """Receive a webm audio blob, transcribe it with Whisper, return the text."""
    try:
        audio_file = request.files.get('audio')
        if not audio_file:
            return jsonify({'error': 'No audio file received'}), 400

        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        import whisper
        model = whisper.load_model('base')
        result = model.transcribe(tmp_path)
        text = result.get('text', '').strip()

        os.remove(tmp_path)

        if not text:
            return jsonify({'text': '', 'warning': 'No speech detected'}), 200

        return jsonify({'text': text}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────
#  EMOTION ANALYSIS
# ─────────────────────────────────────────────
@therapist_bp.route('/analyze_emotion', methods=['POST'])
def analyze_emotion():
    """Analyze a base64-encoded image for emotion using DeepFace."""
    try:
        data = request.json
        image_data = data.get('image', '')
        should_flip = data.get('flip', False)

        encoded_data = image_data.split(',')[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if should_flip:
            img = cv2.flip(img, 1)

        result = DeepFace.analyze(img, actions=['emotion'], enforce_detection=False)
        emotion = result[0]['dominant_emotion']

        return jsonify({
            'emotion': emotion,
            'image_size': f"{img.shape[1]}x{img.shape[0]}",
            'flipped': should_flip
        })

    except Exception as e:
        print(f"Emotion analysis error: {e}")
        return jsonify({'emotion': 'neutral', 'error': str(e)}), 500


# ─────────────────────────────────────────────
#  LANGCHAIN / GEMINI CHAIN
# ─────────────────────────────────────────────
def create_chain():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GEMINI_API_KEY,
        temperature=0.6
    )

    prompt = PromptTemplate(
        input_variables=["history", "user_input", "emotion"],
        template="""
You are a helpful, thoughtful, and positive therapist designed to uplift and support individuals with their personal struggles.

Guidelines:
- Be thoughtful and understanding
- Ask one relevant follow-up question when needed
- Never diagnose, only suggest general advice
- Recommend professional care for serious symptoms
- Keep your answer brief
- NEVER answer non-health related questions. If asked, politely say you can only help with health and wellbeing concerns
- After 5 user messages, briefly rate emotional clarity out of 100 based on how well the user describes their feelings and whether their emotional tone has changed

Current detected emotion from facial recognition model: {emotion}

Conversation History:
{history}

User: {user_input}
Assistant:
"""
    )

    return LLMChain(llm=llm, prompt=prompt)


def sanitize_input(text):
    return re.sub(r'[^\w\s,.?!\-°]', '', text).strip()


# ─────────────────────────────────────────────
#  MAIN THERAPIST CHAT
# ─────────────────────────────────────────────
@therapist_bp.route('/', methods=['GET', 'POST'])
def therapist():
    if 'user_ID' not in session:
        return jsonify({"error": "Please login first"}), 401

    session.setdefault('conversation_history', [])
    session.setdefault('emotion_history', [])

    if request.method == 'POST':
        try:
            data = request.get_json()
            user_input = sanitize_input(data.get('message', ''))
            current_emotion = data.get('emotion', 'neutral')

            if not user_input:
                return jsonify({
                    "error": "Please enter your message",
                    "conversation_history": session['conversation_history'],
                    "emotion_history": session['emotion_history']
                }), 400

            session['emotion_history'].append(current_emotion)
            session['emotion_history'] = session['emotion_history'][-5:]
            emotion_history_str = ", ".join(session['emotion_history'])

            session['conversation_history'].append({
                'role': 'user',
                'content': user_input,
                'timestamp': datetime.now().isoformat()
            })

            history_str = "\n".join(
                f"{msg['role'].capitalize()}: {msg['content']}"
                for msg in session['conversation_history'][:-1]
            )

            chain = create_chain()
            response = chain.invoke({
                "user_input": user_input,
                "history": history_str,
                "emotion": f"{current_emotion} (Recent: {emotion_history_str})"
            })

            ai_response = response.get('text', '').strip() or "Could you tell me more about that?"

            session['conversation_history'].append({
                'role': 'ai',
                'content': ai_response,
                'timestamp': datetime.now().isoformat()
            })

            session.modified = True

            return jsonify({
                "response": ai_response,
                "conversation_history": session['conversation_history'],
                "emotion_history": session['emotion_history']
            })

        except Exception as e:
            print(f"Therapist error: {e}")
            return jsonify({
                "error": "I'm having trouble responding. Please try again.",
                "response": "For urgent concerns, please contact a healthcare professional."
            }), 500

    return render_template(
        'therapist.html',
        logged_in=True,
        conversation_history=session.get('conversation_history', []),
        emotion_history=session.get('emotion_history', [])
    )