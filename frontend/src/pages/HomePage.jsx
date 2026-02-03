import '../css/HomePage.css'
import Sidebar from "../components/SideBar";
import NoChatSelected from "../components/NoChatSelected";
import ChatContainer from '../components/ChatContainer';
import { useProgramContext } from '../contexts/ProgramContext';

const HomePage = () => {
    const { selectedProgram } = useProgramContext();

    return (
        <div className="home-page">
            <div className="home-card">
                <div className="home-card__inner">
                    <Sidebar />
                    <div className='chat-container'>
                        <div className='chat-container__inner'>
                            {!selectedProgram ? <NoChatSelected /> : <ChatContainer />}
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
};
export default HomePage;
