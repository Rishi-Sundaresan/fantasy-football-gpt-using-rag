from flask import Flask, render_template, request, jsonify, session
from rag import reply
import uuid
import os

app = Flask(__name__)
app.secret_key = 'HIDDEN'  # Replace with a strong secret key

# In-memory storage for conversation history
conversation_store = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_prompt = data.get('prompt')
    
    # Ensure a conversation ID exists
    if 'conversation_id' not in session:
        session['conversation_id'] = str(uuid.uuid4())

    conversation_id = session['conversation_id']
    
    # Retrieve or initialize the conversation history
    conversation_history = conversation_store.get(conversation_id, [])
    
    # Append the user's prompt to the conversation history
    conversation_history.append({'role': 'user', 'content': user_prompt})
    
    bot_response = reply(user_prompt, conversation_history)
    
    # Append the bot's response to the conversation history
    conversation_history.append({'role': 'assistant', 'content': bot_response})
    conversation_store[conversation_id] = conversation_history
    
    return jsonify({'response': bot_response})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
