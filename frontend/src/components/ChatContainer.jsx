import { useProgramContext } from "../contexts/ProgramContext";
import ChatInput from "./chatInput";
import NoChatSelected from "./NoChatSelected";
import Message from "./Message";
import { useRef, useEffect } from "react";

import '../css/ChatContainer.css'


function ChatContainer() {

    // for retreaving chat history and adding new messages
    const { selectedProgram, setSelectedProgram, chatHistory, addToChatHistory } = useProgramContext();
    const selectedHistory = chatHistory[selectedProgram] || [];
    const messageExists = selectedHistory.length > 0;
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };


    useEffect(() => {
        scrollToBottom();
    }, [selectedHistory]);

    return (
        <div className='chat-container'>
            <div className='chat-header'>
                <h2>Chatting with: {selectedProgram}</h2>
            </div>

            <div className="chat-container__inner">

            {!messageExists ? <NoChatSelected /> : <div className='chat-messages-container'>
                {selectedHistory.map((message) => (
                    <div key={message.key} className={`chat-message ${message.role === 'user' ? 'user' : 'assistant'}`}>
                        <Message message={message} />
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>}



            <ChatInput />
            </div>
        </div>
    );
}

export default ChatContainer;
