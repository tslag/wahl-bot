import { createContext, useState, useContext, useEffect } from "react";
import authService from '../services/authService';
import { API_BASE_URL } from "../util";

const ProgramContext = createContext()

export const useProgramContext = () => useContext(ProgramContext)

export const ProgramProvider = ({children}) => {
    const [programList, setProgramList] = useState([]);
    const [selectedProgram, setSelectedProgram] = useState(null);

    // chatHistory maps programName -> array of messages for that program
    const [chatHistory, setChatHistory] = useState({});

    const getProgramList = async () => {
        const resp = await authService.apiRequest(`${API_BASE_URL}/program/list`, { method: 'GET' });
        const response = await resp.json();
        setProgramList(response.programs.map(p => ({ name: p.name, key: p.name })));
    }


    const addToChatHistory = (message, program = selectedProgram) => {
        if (!program) return;
        setChatHistory(prev => {
            const existing = Array.isArray(prev[program]) ? prev[program] : [];
            return { ...prev, [program]: [...existing, message] };
        })
    }

    const removeFromChatHistory = (program) => {
        if (!program) return;
        setChatHistory(prev => {
            const newHistory = { ...prev };
            delete newHistory[program];
            return newHistory;
        });
    }

    useEffect(() => {
        getProgramList();
    }, []);

    return (
        <ProgramContext.Provider value={{
            programList,
            selectedProgram,
            setSelectedProgram,
            chatHistory,
            addToChatHistory,
            removeFromChatHistory,
            getProgramList
        }}>
            {children}
        </ProgramContext.Provider>
    );
}
