from flask import Flask, request

import requests

app = Flask(__name__)

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Agent Tester</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f0f4f8;
                color: #333;
                margin: 0;
                padding: 20px;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }
            .container {
                background-color: white;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                padding: 30px;
                width: 100%;
                max-width: 800px;
            }
            h1 {
                text-align: center;
                color: #4a90e2;
                margin-bottom: 20px;
            }
            #chat {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
                height: 400px;
                overflow-y: auto;
                background-color: #fafafa;
                margin-bottom: 20px;
            }
            .message {
                margin-bottom: 15px;
                padding: 12px 18px;
                border-radius: 20px;
                max-width: 80%;
                word-wrap: break-word;
                position: relative;
            }
            .user {
                background-color: #4a90e2;
                color: white;
                align-self: flex-end;
                margin-left: auto;
            }
            .agent {
                background-color: #e0e0e0;
                color: #333;
                align-self: flex-start;
            }
            .error {
                background-color: #ffcccc;
                color: #cc0000;
                align-self: center;
                text-align: center;
            }
            #chat {
                display: flex;
                flex-direction: column;
            }
            form {
                display: grid;
                gap: 10px;
            }
            label {
                font-weight: bold;
                color: #555;
            }
            input[type="text"] {
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 16px;
            }
            button {
                background-color: #4a90e2;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 16px;
                transition: background-color 0.3s;
            }
            button:hover {
                background-color: #357abd;
            }
            button:disabled {
                background-color: #ccc;
                cursor: not-allowed;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Returns Warranty Insights Agent</h1>
            <div id="chat"></div>
            <form id="agentForm">
                <label for="model">Model:</label>
                <input type="text" id="model" value="gpt-4.1-mini">
                
                <label for="user_query">Message:</label>
                <input type="text" id="user_query" placeholder="Enter your message" required>
                
                <label for="session_id">Session ID:</label>
                <input type="text" id="session_id" value="default_session">
                
                <button type="submit">Send</button>
            </form>
        </div>
        
        <script>
            const chat = document.getElementById('chat');
            const form = document.getElementById('agentForm');
            const submitButton = form.querySelector('button');
            
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const model = document.getElementById('model').value;
                const user_query = document.getElementById('user_query').value;
                const encoded_query = encodeURIComponent(user_query);
                const session_id = document.getElementById('session_id').value;
                
                // Append user message to chat
                appendMessage('User: ' + user_query, 'user');
                
                // Clear the input field and disable button during request
                document.getElementById('user_query').value = '';
                submitButton.disabled = true;
                submitButton.textContent = 'Sending...';
                
                const url = `/proxy_run_agent?model=${model}&user_query=${encoded_query}&session_id=${session_id}`;
                
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 360000); // 6 minutes in milliseconds
                
                try {
                    const res = await fetch(url, {
                        method: 'POST',
                        signal: controller.signal
                    });
                    clearTimeout(timeoutId);
                    if (!res.ok) {
                        throw new Error(`HTTP error! status: ${res.status}`);
                    }
                    const data = await res.text();
                    appendMessage('Agent: ' + data, 'agent');
                } catch (error) {
                    clearTimeout(timeoutId);
                    if (error.name === 'AbortError') {
                        appendMessage('Error: Request timed out after 6 minutes', 'error');
                    } else {
                        appendMessage('Error: ' + error.message, 'error');
                    }
                } finally {
                    submitButton.disabled = false;
                    submitButton.textContent = 'Send';
                }
            });
            
            function appendMessage(text, type) {
                const div = document.createElement('div');
                div.classList.add('message', type);
                div.textContent = text;
                chat.appendChild(div);
                chat.scrollTop = chat.scrollHeight;
            }
        </script>
    </body>
    </html>
    """

@app.route('/proxy_run_agent', methods=['POST'])
def proxy_run_agent():
    # Forward the query params to the internal API URL
    api_url = f"http://main-ag:8000/run_agent?{request.query_string.decode()}"
    try:
        response = requests.post(api_url)
        return response.text, response.status_code
    except Exception as e:
        return f"Proxy error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)