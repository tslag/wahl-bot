import '../css/NoChatSelected.css'
import { MessageSquare } from "lucide-react";

const NoChatSelected = () => {
  return (
    <div className="no-chat-container">
      <div className="no-chat-inner">
        {/* Icon Display */}
        <div className="icon-wrap">
          <div className="relative">
            <div className="icon-circle">
              <MessageSquare className="icon" />
            </div>
          </div>
        </div>

        {/* Welcome Text */}
        <h2 className="title">Welcome to Wahl Bot!</h2>
        <p className="text-muted">
          Select a program from the sidebar and start chatting
        </p>
      </div>
    </div>
  );
};

export default NoChatSelected;