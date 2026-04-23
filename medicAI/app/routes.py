from flask import Blueprint, render_template, session, request, jsonify
from datetime import datetime
import re
import google.generativeai as genai

main_bp = Blueprint('main', __name__)

GEMINI_API_KEY = "AIzaSyDRDdBCZZ9Gg7CEhr8392hbn3-t5CTqC50"

SYSTEM_PROMPT = """You are a medical support assistant. Follow these rules:
- Start your response naturally and vary your tone, avoid repeating "Okay, I understand"
- Provide 1-2 possible explanations (not diagnoses)
- Suggest general self-care options when appropriate
- Clearly state when professional care is recommended
- Ask only ONE relevant follow-up question if needed
- Keep responses under 3 sentences
- NEVER answer non-health questions
- Include a section titled 'Common Medications' listing 1-2 OTC meds that may help, with a disclaimer to consult a doctor first."""


def sanitize_input(text):
    return re.sub(r'[^\w\s,.?!-°]', '', text).strip()


@main_bp.route('/')
def home():
    return render_template('main.html', logged_in='user_ID' in session)


@main_bp.route('/diagnostic-support', methods=['GET', 'POST'])
def diagnostic_support():
    if 'conversation_history' not in session:
        session['conversation_history'] = []

    if request.method == 'POST':
        try:
            data = request.get_json()
            user_input = sanitize_input(data.get('message', ''))

            if not user_input:
                return jsonify({
                    "error": "Please enter your symptoms",
                    "conversation_history": session['conversation_history']
                }), 400

            session['conversation_history'].append({
                'role': 'user',
                'content': user_input,
                'timestamp': datetime.now().isoformat()
            })

            history = "\n".join(
                f"{msg['role']}: {msg['content']}"
                for msg in session['conversation_history'][:-1]
            )

            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            full_prompt = f"{SYSTEM_PROMPT}\n\nConversation History:\n{history}\n\nUser: {user_input}\nAssistant:"
            response = model.generate_content(full_prompt)
            ai_response = response.text.strip()

            if not ai_response:
                ai_response = "Could you please tell me more about your symptoms?"

            session['conversation_history'].append({
                'role': 'ai',
                'content': ai_response,
                'timestamp': datetime.now().isoformat()
            })
            session.modified = True

            return jsonify({
                "response": ai_response,
                "conversation_history": session['conversation_history']
            })

        except Exception as e:
            print(f"AI Error: {str(e)}")
            return jsonify({
                "error": "I'm having trouble responding. Please try again.",
                "response": "For urgent medical concerns, please contact a healthcare professional immediately."
            }), 500

    return render_template('diagnostic_support.html',
                           logged_in=True,
                           conversation_history=session['conversation_history'])


@main_bp.route('/nearest_doctor', methods=['GET', 'POST'])
def nearest_doctor():
    return render_template('nearest_doctor.html', logged_in='user_ID' in session)