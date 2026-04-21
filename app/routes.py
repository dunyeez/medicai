from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from datetime import datetime
import re

main_bp = Blueprint('main', __name__)


def create_chain():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key="AIzaSyD_WrHKk1rwDFB_izAKbPNsreYDwDs2V_c",
        temperature=0.6
    )

    prompt = PromptTemplate(
        input_variables=["history", "user_input"],
        template="""
        [System] You are a medical support assistant. Follow these rules:
        1. Consider previous conversation: {history}
        2. Respond to: {user_input}
        3. Guidelines:
           - Start your response naturally and vary your tone — avoid repeating "Okay, I understand "
             Examples: "Got it.", "Thanks for sharing that.", "Sorry you're going through this.", or jump right into the reply.
           - Provide 1-2 possible explanations (not diagnoses)
           - Suggest general self-care options when appropriate
           - Clearly state when professional care is recommended
           - Ask only ONE relevant follow-up question if needed
           - Keep responses under 3 sentences
           - NEVER answer non-health questions
           - include a section titled 'Common Medications' that lists 1-2 OTC meds that may help. Always include a disclaimer to consult a doctor first.
        Assistant:"""
    )

    chain = prompt | llm | StrOutputParser()
    return chain


def sanitize_input(text):
    """Clean user input while preserving medical terms"""
    return re.sub(r'[^\w\s,.?!-°]', '', text).strip()


@main_bp.route('/')
def home():
    return render_template('main.html', logged_in='user_ID' in session)


@main_bp.route('/diagnostic-support', methods=['GET', 'POST'])
def diagnostic_support():
    if 'user_ID' not in session:
        return jsonify({"error": "Please login first"}), 401

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

            chain = create_chain()
            ai_response = chain.invoke({
                "user_input": user_input,
                "history": history
            })

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