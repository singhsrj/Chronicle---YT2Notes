import { useState, useEffect } from 'react';
import { Youtube, Play, FileText, Loader2, Copy, Check, RefreshCw } from 'lucide-react';
import { NotesRenderer } from '../NotesRenderer';
import { useSession } from '../../context';
import { useTranscription, useNotesGeneration } from '../../hooks';
import './MainContent.css';

export function MainContent() {
  const { getActiveSession, updateSession } = useSession();
  const { startTranscription, isProcessing: isTranscribing, error: transcriptionError } = useTranscription();
  const { generateNotes, isGenerating, streamedNotes, error: notesError } = useNotesGeneration();
  
  const [videoUrl, setVideoUrl] = useState('');
  const [activeTab, setActiveTab] = useState<'transcript' | 'notes'>('transcript');
  const [copied, setCopied] = useState(false);

  const session = getActiveSession();

  // Sync video URL with active session
  useEffect(() => {
    if (session?.videoUrl) {
      setVideoUrl(session.videoUrl);
    } else {
      setVideoUrl('');
    }
  }, [session?.id, session?.videoUrl]);

  // Display notes from session or streaming
  const displayNotes = streamedNotes || session?.notes || '';

  if (!session) {
    return (
      <main className="main-content">
        <div className="empty-main">
          <div className="empty-icon">📺</div>
          <h2>Welcome to Chronicle</h2>
          <p>Create a new session to start converting YouTube videos to notes</p>
        </div>
      </main>
    );
  }

  const handleStartTranscription = async () => {
    if (!videoUrl.trim()) return;
    
    updateSession(session.id, { 
      videoUrl, 
      title: extractVideoTitle(videoUrl) 
    });
    
    await startTranscription(session.id, videoUrl);
  };

  const handleGenerateNotes = async () => {
    if (!session.transcript) return;
    await generateNotes(session.id, session.transcript, session.title);
    setActiveTab('notes');
  };

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isValidYoutubeUrl = (url: string) => {
    return url.includes('youtube.com') || url.includes('youtu.be');
  };

  return (
    <main className="main-content">
      {/* URL Input Section */}
      <section className="url-section">
        <div className="url-input-wrapper">
          <Youtube className="url-icon" size={20} />
          <input
            type="text"
            className="url-input"
            placeholder="Paste YouTube URL here..."
            value={videoUrl}
            onChange={(e) => setVideoUrl(e.target.value)}
            disabled={isTranscribing}
          />
          <button
            className="transcribe-btn"
            onClick={handleStartTranscription}
            disabled={!isValidYoutubeUrl(videoUrl) || isTranscribing}
          >
            {isTranscribing ? (
              <>
                <Loader2 className="spinning" size={18} />
                <span>Processing...</span>
              </>
            ) : (
              <>
                <Play size={18} />
                <span>Transcribe</span>
              </>
            )}
          </button>
        </div>
        
        {transcriptionError && (
          <div className="error-message">{transcriptionError}</div>
        )}
      </section>

      {/* Progress Section */}
      {(isTranscribing || session.status === 'transcribing') && (
        <section className="progress-section">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: '60%' }} />
          </div>
          <p className="progress-text">
            {session.status === 'downloading' && 'Downloading video...'}
            {session.status === 'chunking' && 'Splitting into chunks...'}
            {session.status === 'transcribing' && 'Transcribing audio...'}
          </p>
        </section>
      )}

      {/* Content Tabs */}
      {(session.transcript || displayNotes) && (
        <section className="content-section">
          <div className="tabs-header">
            <div className="tabs">
              <button
                className={`tab ${activeTab === 'transcript' ? 'active' : ''}`}
                onClick={() => setActiveTab('transcript')}
              >
                <FileText size={16} />
                Transcript
              </button>
              <button
                className={`tab ${activeTab === 'notes' ? 'active' : ''}`}
                onClick={() => setActiveTab('notes')}
              >
                <FileText size={16} />
                Notes
              </button>
            </div>

            <div className="tab-actions">
              {activeTab === 'transcript' && session.transcript && (
                <button
                  className="action-btn primary"
                  onClick={handleGenerateNotes}
                  disabled={isGenerating}
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="spinning" size={16} />
                      Generating...
                    </>
                  ) : (
                    <>
                      <RefreshCw size={16} />
                      Generate Notes
                    </>
                  )}
                </button>
              )}

              <button
                className="action-btn"
                onClick={() => handleCopy(activeTab === 'transcript' ? (session.transcript || '') : displayNotes)}
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? 'Copied!' : 'Copy'}
              </button>
            </div>
          </div>

          <div className="content-body">
            {activeTab === 'transcript' ? (
              <div className="transcript-content">
                {session.transcript || 'No transcript yet. Start by transcribing a video.'}
              </div>
            ) : (
              <div className="notes-content">
                {isGenerating && !displayNotes && (
                  <div className="generating-placeholder">
                    <Loader2 className="spinning" size={24} />
                    <p>Generating notes...</p>
                  </div>
                )}
                {displayNotes ? (
                  <NotesRenderer content={displayNotes} isStreaming={isGenerating} />
                ) : (
                  <p className="no-notes">
                    No notes generated yet. Click "Generate Notes" after transcription.
                  </p>
                )}
              </div>
            )}
          </div>

          {notesError && (
            <div className="error-message">{notesError}</div>
          )}
        </section>
      )}
    </main>
  );
}

function extractVideoTitle(url: string): string {
  // Simple extraction - in production you'd fetch from YT API
  const videoId = url.match(/(?:v=|\/)([\w-]{11})/)?.[1];
  return videoId ? `Video ${videoId.slice(0, 6)}...` : 'Untitled Video';
}
