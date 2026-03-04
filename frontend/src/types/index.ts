// Session related types
export interface Session {
  id: string;
  title: string;
  videoUrl: string;
  status: SessionStatus;
  createdAt: string;
  updatedAt: string;
  transcript?: string;
  notes?: string;
}

export type SessionStatus = 
  | 'idle'
  | 'downloading'
  | 'chunking'
  | 'transcribing'
  | 'generating_notes'
  | 'completed'
  | 'error';

// API request/response types
export interface TranscribeRequest {
  url: string;
  chunk_seconds?: number;
  model_name?: 'tiny' | 'base' | 'small' | 'medium' | 'large-v2' | 'large-v3';
  language?: string;
  session_id?: string;  // Optional: use existing session ID
}

export interface TranscribeResponse {
  session_id: string;
  status: string;
  message: string;
}

export interface TranscriptionStatus {
  session_id: string;
  status: SessionStatus;
  video_url: string;
  progress?: {
    current_chunk: number;
    total_chunks: number;
    completed_chunks: number;
    progress_percentage: number;
  };
  error?: string;
  total_segments?: number;
  total_duration?: number;
}

export interface TranscriptionResult {
  session_id: string;
  video_url: string;
  total_segments: number;
  total_duration: number;
  segments: TranscriptSegment[];
  full_text: string;
  source: 'youtube_captions' | 'whisper';
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface NotesRequest {
  transcript: string;
  title?: string;
}

export interface NotesResponse {
  status: 'ok' | 'error';
  notes?: string;
  title?: string;
  error?: string;
}

export interface OllamaStatus {
  ollama_status: 'running' | 'offline' | 'unreachable';
  models?: unknown;
  detail?: string;
}

// Session-based notes types
export interface BackendSession {
  session_id: string;
  video_url: string;
  total_segments?: number;
  total_duration?: number;
  status?: string;
  progress_percentage?: number;
}

export interface BackendSessionsResponse {
  sessions: BackendSession[];
}
