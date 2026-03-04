import { Plus, Trash2, Video, FileText, Loader2 } from 'lucide-react';
import { useSession } from '../../context';
import { Session, SessionStatus } from '../../types';
import './Sidebar.css';

function getStatusIcon(status: SessionStatus) {
  switch (status) {
    case 'downloading':
    case 'chunking':
    case 'transcribing':
    case 'generating_notes':
      return <Loader2 className="status-icon spinning" size={14} />;
    case 'completed':
      return <FileText className="status-icon completed" size={14} />;
    case 'error':
      return <span className="status-icon error">!</span>;
    default:
      return <Video className="status-icon" size={14} />;
  }
}

function getStatusLabel(status: SessionStatus): string {
  switch (status) {
    case 'downloading': return 'Downloading...';
    case 'chunking': return 'Chunking...';
    case 'transcribing': return 'Transcribing...';
    case 'generating_notes': return 'Generating notes...';
    case 'completed': return 'Completed';
    case 'error': return 'Error';
    default: return 'Ready';
  }
}

interface SessionItemProps {
  session: Session;
  isActive: boolean;
  onClick: () => void;
  onDelete: () => void;
}

function SessionItem({ session, isActive, onClick, onDelete }: SessionItemProps) {
  return (
    <div 
      className={`session-item ${isActive ? 'active' : ''}`}
      onClick={onClick}
    >
      <div className="session-icon">
        {getStatusIcon(session.status)}
      </div>
      <div className="session-info">
        <span className="session-title">{session.title}</span>
        <span className="session-status">{getStatusLabel(session.status)}</span>
      </div>
      <button 
        className="delete-btn"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        title="Delete session"
      >
        <Trash2 size={14} />
      </button>
    </div>
  );
}

export function Sidebar() {
  const { sessions, activeSessionId, setActiveSession, addSession, deleteSession } = useSession();

  const handleNewSession = () => {
    addSession('New Session', '');
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="logo">
          <span className="logo-icon">📝</span>
          Chronicle
        </h1>
        <button className="new-session-btn" onClick={handleNewSession}>
          <Plus size={18} />
          <span>New</span>
        </button>
      </div>

      <div className="sessions-list">
        {sessions.length === 0 ? (
          <div className="empty-state">
            <p>No sessions yet</p>
            <p className="hint">Click "New" to start</p>
          </div>
        ) : (
          sessions.map(session => (
            <SessionItem
              key={session.id}
              session={session}
              isActive={session.id === activeSessionId}
              onClick={() => setActiveSession(session.id)}
              onDelete={() => deleteSession(session.id)}
            />
          ))
        )}
      </div>

      <div className="sidebar-footer">
        <span className="version">v1.0.0</span>
      </div>
    </aside>
  );
}
