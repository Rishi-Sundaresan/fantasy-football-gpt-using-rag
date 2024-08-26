const messages = [];

function renderChatlog() {
    const chatlog = document.getElementById('chatlog');
    chatlog.innerHTML = messages.map(message => {
        const bubbleClass = message.type === 'user' ? 'user-bubble' : 'bot-bubble';
        const iconClass = message.type === 'user' ? 'user-icon' : 'bot-icon';
        return `
            <div class="${message.type}-message">
                <div class="${iconClass}"></div>
                <div class="message-bubble ${bubbleClass}">
                    ${message.text}
                </div>
            </div>`;
    }).join('');
    chatlog.scrollTop = chatlog.scrollHeight; // Auto-scroll to bottom
}

function sendMessage() {
    const inputField = document.getElementById('user-input');
    const userInput = inputField.value.trim();
    if (userInput === '') return;
    inputField.value = '';

    messages.push({ type: 'user', text: userInput });
    renderChatlog();

    messages.push({ type: 'bot', text: 'Generating response...' });
    renderChatlog();

    fetch('/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt: userInput })
    })
    .then(response => response.json())
    .then(data => {
        // Replace the "Generating response..." message with the actual response
        const lastIndex = messages.findIndex(msg => msg.type === 'bot' && msg.text === 'Generating response...');
        if (lastIndex !== -1) {
            messages[lastIndex].text = data.response;
            renderChatlog();
        }
    })
    .catch(error => {
        const lastIndex = messages.findIndex(msg => msg.type === 'bot' && msg.text === 'Generating response...');
        if (lastIndex !== -1) {
            messages[lastIndex].text = 'Sorry, there was an error processing your request.';
            renderChatlog();
        }
    });
}

// Add event listener for Enter key press
document.getElementById('user-input').addEventListener('keydown', function(event) {
    if (event.key === 'Enter') {
        event.preventDefault(); // Prevent default Enter key behavior (new line)
        sendMessage();
    }
});

// Add event listener for Send button touch events
const sendButton = document.getElementById('send-button');
sendButton.addEventListener('click', sendMessage);
sendButton.addEventListener('touchend', function(event) {
    event.preventDefault(); // Prevents default touch event behavior
    sendMessage();
});
