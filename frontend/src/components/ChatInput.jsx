import { useState } from "react";
import authService from '../services/authService';

import { useProgramContext } from "../contexts/ProgramContext";
import { API_BASE_URL } from "../util";

import '../css/ChatInput.css'

function ChatInput() {
    const [question, setQuestion] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const { selectedProgram, chatHistory, addToChatHistory } = useProgramContext();

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!question.trim()) {
            setError("Please enter a question");
            return
        }
        if (loading) return
        setLoading(true);

        try {
            const requestMessage = {role: "user", content: question.trim()};

            const messages = (chatHistory?.[selectedProgram] ?? []);
            requestMessage.key = messages.length + 1;
            addToChatHistory(requestMessage);

            // build payload including the optimistic message
            const payloadMessages = [...messages, requestMessage].slice(-6).map(({ key, ...m }) => m);

            console.log("Sending messages to backend:", payloadMessages);
            const resp = await authService.apiRequest(`${API_BASE_URL}/chat/${selectedProgram}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: payloadMessages })
            });
            const chatResult = await resp.json();

            // Add assistant reply to history
            chatResult.message.key = requestMessage.key + 1;
            setError("");
            setQuestion("");
            addToChatHistory(chatResult.message);
        } catch (error) {
            console.log(error);
            setError("An error occurred while processing your question.");
        } finally {
            setLoading(false);
        }
    }

    return <div>

        <div className="chat-input-container">
            <h2>Chat with the program</h2>

            <form onSubmit={handleSubmit} className="chat-input-form">
                <div className="input-group">
                    <textarea
                        className={`input-box ${error ? 'error' : ''}`}
                        
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        placeholder="Type your message..."
                        rows="3"
                    />
                    <div className="submit-container">
                        <button type="submit" className="chat-btn">
                            Chat
                        </button>
                        {error && <p className="error-text">{error}</p>}

                    </div>
                </div>
            </form>
        </div>
    </div>

}

export default ChatInput