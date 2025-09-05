from flask import Flask, request
from dotenv import load_dotenv
import os


import requests

load_dotenv()

MAIN_AG_URL = os.getenv("MAIN_AG_URL")

app = Flask(__name__)

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Agent Chat</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/4.3.0/marked.min.js"></script>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                background-color: #0f0f0f;
                color: #ececec;
                height: 100vh;
                display: flex;
                flex-direction: column;
            }
            
            .header {
                background-color: #171717;
                padding: 1rem 2rem;
                border-bottom: 1px solid #2d2d2d;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            
            .header h1 {
                font-size: 1.25rem;
                font-weight: 600;
                color: #ececec;
            }
            
            .settings-btn {
                background: #2d2d2d;
                border: none;
                color: #ececec;
                padding: 0.5rem 1rem;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.875rem;
                transition: background-color 0.2s;
            }
            
            .settings-btn:hover {
                background: #404040;
            }
            
            .settings-panel {
                display: none;
                position: absolute;
                top: 60px;
                right: 2rem;
                background: #1f1f1f;
                border: 1px solid #2d2d2d;
                border-radius: 8px;
                padding: 1rem;
                z-index: 100;
                min-width: 200px;
            }
            
            .settings-panel.show {
                display: block;
            }
            
            .settings-panel label {
                display: block;
                margin-bottom: 0.5rem;
                font-size: 0.875rem;
                color: #b3b3b3;
            }
            
            .settings-panel input {
                width: 100%;
                padding: 0.5rem;
                background: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 4px;
                color: #ececec;
                margin-bottom: 1rem;
            }
            
            .chat-container {
                flex: 1;
                display: flex;
                flex-direction: column;
                max-width: 800px;
                margin: 0 auto;
                width: 100%;
                padding: 0 1rem;
            }
            
            .messages {
                flex: 1;
                overflow-y: auto;
                padding: 2rem 0;
                scroll-behavior: smooth;
            }
            
            .message {
                margin-bottom: 2rem;
                animation: fadeIn 0.3s ease-in;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            .message-header {
                display: flex;
                align-items: center;
                margin-bottom: 0.5rem;
                font-weight: 600;
                font-size: 0.875rem;
            }
            
            .user-icon {
                width: 24px;
                height: 24px;
                background: #10a37f;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 0.75rem;
                color: white;
                font-size: 0.75rem;
            }
            
            .assistant-icon {
                width: 24px;
                height: 24px;
                background: #ab68ff;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 0.75rem;
                color: white;
                font-size: 0.75rem;
            }
            
            .message-content {
                margin-left: 2rem;
                line-height: 1.6;
                word-wrap: break-word;
            }
            
            .message-content pre {
                background: #1f1f1f;
                border: 1px solid #2d2d2d;
                border-radius: 6px;
                padding: 1rem;
                overflow-x: auto;
                margin: 1rem 0;
            }
            
            .message-content code {
                background: #1f1f1f;
                padding: 0.2rem 0.4rem;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 0.875rem;
            }
            
            .message-content pre code {
                background: none;
                padding: 0;
            }
            
            .message-content blockquote {
                border-left: 3px solid #404040;
                padding-left: 1rem;
                margin: 1rem 0;
                color: #b3b3b3;
            }
            
            .message-content ul, .message-content ol {
                margin: 1rem 0;
                padding-left: 1.5rem;
            }
            
            .message-content h1, .message-content h2, .message-content h3 {
                margin: 1.5rem 0 1rem 0;
                color: #ececec;
            }
            
            .error {
                color: #ff6b6b;
                background: #2d1a1a;
                padding: 1rem;
                border-radius: 6px;
                border-left: 3px solid #ff6b6b;
            }
            
            .input-area {
                padding: 1rem 0 2rem 0;
                border-top: 1px solid #2d2d2d;
                background: #0f0f0f;
            }
            
            .input-form {
                display: flex;
                gap: 0.75rem;
                align-items: flex-end;
                max-width: 800px;
                margin: 0 auto;
                padding: 0 1rem;
            }
            
            .input-wrapper {
                flex: 1;
                position: relative;
            }
            
            .input-field {
                width: 100%;
                background: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 12px;
                padding: 1rem 3rem 1rem 1rem;
                color: #ececec;
                font-size: 1rem;
                line-height: 1.4;
                resize: none;
                min-height: 48px;
                max-height: 200px;
                overflow-y: auto;
            }
            
            .input-field:focus {
                outline: none;
                border-color: #10a37f;
                box-shadow: 0 0 0 1px #10a37f;
            }
            
            .input-field::placeholder {
                color: #666;
            }
            
            .send-button {
                position: absolute;
                right: 8px;
                bottom: 8px;
                background: #10a37f;
                border: none;
                border-radius: 6px;
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: background-color 0.2s;
                color: white;
            }
            
            .send-button:hover:not(:disabled) {
                background: #0e906f;
            }
            
            .send-button:disabled {
                background: #404040;
                cursor: not-allowed;
            }
            
            .typing-indicator {
                display: none;
                margin-left: 2rem;
                color: #666;
                font-style: italic;
                font-size: 0.875rem;
                align-items: center;
            }
            
            .typing-indicator.show {
                display: flex;
            }
            
            .typing-dots {
                display: inline-flex;
                margin-left: 0.25rem;
            }
            
            .dot {
                width: 6px;
                height: 6px;
                background-color: #666;
                border-radius: 50%;
                margin: 0 2px;
                animation: bounce 1.2s infinite ease-in-out;
            }
            
            .dot:nth-child(2) {
                animation-delay: -0.4s;
            }
            
            .dot:nth-child(3) {
                animation-delay: -0.8s;
            }
            
            @keyframes bounce {
                0%, 80%, 100% {
                    transform: scale(0);
                }
                40% {
                    transform: scale(1);
                }
            }
            
            .welcome-message {
                text-align: center;
                color: #666;
                margin: 4rem 0;
            }
            
            .welcome-message h2 {
                margin-bottom: 1rem;
                color: #ececec;
            }
            
            @media (max-width: 768px) {
                .header {
                    padding: 1rem;
                }
                
                .chat-container {
                    padding: 0 0.5rem;
                }
                
                .input-form {
                    padding: 0 0.5rem;
                }
                
                .message-content {
                    margin-left: 1.5rem;
                }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Vincent Carter</h1>
            <button class="settings-btn" onclick="toggleSettings()">⚙️ Settings</button>
            <div class="settings-panel" id="settingsPanel">
                <label for="model">Model:</label>
                <input type="text" id="model" value="gpt-4.1-mini">
                
                <label for="session_id">Session ID:</label>
                <input type="text" id="session_id" value="default_session">
            </div>
        </div>
        
        <div class="chat-container">
            <div class="messages" id="messages">
                <div class="welcome-message">
                    <h2>Welcome to Warranty Agent</h2>
                    <p>Ask me anything and I'll help you with detailed responses.</p>
                </div>
            </div>
            
            <div class="typing-indicator" id="typingIndicator">
                AI is thinking
                <div class="typing-dots">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                </div>
            </div>
            
            <div class="input-area">
                <form class="input-form" id="chatForm">
                    <div class="input-wrapper">
                        <textarea 
                            class="input-field" 
                            id="userInput" 
                            placeholder="Send a message..." 
                            rows="1"
                            required
                        ></textarea>
                        <button type="submit" class="send-button" id="sendButton">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/>
                            </svg>
                        </button>
                    </div>
                </form>
            </div>
        </div>
        
        <script>
            const messages = document.getElementById('messages');
            const chatForm = document.getElementById('chatForm');
            const userInput = document.getElementById('userInput');
            const sendButton = document.getElementById('sendButton');
            const typingIndicator = document.getElementById('typingIndicator');
            const settingsPanel = document.getElementById('settingsPanel');
            
            // Auto-resize textarea
            userInput.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = Math.min(this.scrollHeight, 200) + 'px';
            });
            
            // Handle Enter key
            userInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    chatForm.dispatchEvent(new Event('submit'));
                }
            });
            
            // Toggle settings panel
            function toggleSettings() {
                settingsPanel.classList.toggle('show');
            }
            
            // Close settings when clicking outside
            document.addEventListener('click', function(e) {
                if (!e.target.closest('.settings-btn') && !e.target.closest('.settings-panel')) {
                    settingsPanel.classList.remove('show');
                }
            });
            
            // Handle form submission
            chatForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const message = userInput.value.trim();
                if (!message) return;
                
                const model = document.getElementById('model').value;
                const session_id = document.getElementById('session_id').value;
                
                // Clear welcome message if it exists
                const welcomeMsg = document.querySelector('.welcome-message');
                if (welcomeMsg) {
                    welcomeMsg.remove();
                }
                
                // Add user message
                addMessage(message, 'user');
                
                // Clear input and disable form
                userInput.value = '';
                userInput.style.height = 'auto';
                setLoading(true);
                
                try {
                    const response = await fetch(`/proxy_run_agent?model=${encodeURIComponent(model)}&user_query=${encodeURIComponent(message)}&session_id=${encodeURIComponent(session_id)}`, {
                        method: 'POST',
                        signal: AbortSignal.timeout(360000) // 6 minutes
                    });
                    
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    let data = await response.json();
                    if (typeof data === 'object' && data !== null) {
                        data = data.response || data.content || data.message || data.output || JSON.stringify(data);
                    }
                    addMessage(data, 'assistant');
                    
                } catch (error) {
                    if (error.name === 'TimeoutError') {
                        addMessage('Request timed out after 6 minutes. Please try again.', 'error');
                    } else {
                        addMessage(`Error: ${error.message}`, 'error');
                    }
                } finally {
                    setLoading(false);
                }
            });
            
            function addMessage(content, type) {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message';
                
                const icon = type === 'user' ? 
                    '<div class="user-icon">U</div>' : 
                    type === 'assistant' ? 
                    '<div class="assistant-icon">AI</div>' : 
                    '<div class="assistant-icon">!</div>';
                
                const header = type === 'user' ? 'You' : 
                              type === 'assistant' ? 'AI Agent' : 'Error';
                
                let processedContent;
                if (type === 'assistant') {
                    // Parse markdown for assistant responses
                    processedContent = marked.parse(content);
                } else if (type === 'error') {
                    processedContent = `<div class="error">${escapeHtml(content)}</div>`;
                } else {
                    processedContent = escapeHtml(content);
                }
                
                messageDiv.innerHTML = `
                    <div class="message-header">
                        ${icon}
                        ${header}
                    </div>
                    <div class="message-content">
                        ${processedContent}
                    </div>
                `;
                
                messages.appendChild(messageDiv);
                messages.scrollTop = messages.scrollHeight;
            }
            
            function setLoading(loading) {
                sendButton.disabled = loading;
                userInput.disabled = loading;
                
                if (loading) {
                    typingIndicator.classList.add('show');
                } else {
                    typingIndicator.classList.remove('show');
                }
            }
            
            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
            
            // Focus input on load
            userInput.focus();
        </script>
    </body>
    </html>
    """

@app.route('/proxy_run_agent', methods=['POST'])
def proxy_run_agent():
    # Forward the query params to the internal API URL
    api_url = f"{MAIN_AG_URL}/run_agent?{request.query_string.decode()}"
    try:
        response = requests.post(api_url)
        return response.text, response.status_code
    except Exception as e:
        return f"Proxy error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)