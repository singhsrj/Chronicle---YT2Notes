import { 
  TranscribeRequest, 
  TranscribeResponse, 
  TranscriptionStatus, 
  TranscriptionResult 
} from '../types';

// Use empty string for Docker (nginx proxy), localhost for local dev
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

export const transcriptionApi = {
  /**
   * Start a new transcription job
   */
  async startTranscription(request: TranscribeRequest): Promise<TranscribeResponse> {
    const response = await fetch(`${API_BASE}/api/long-video/transcribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to start transcription');
    }
    
    return response.json();
  },

  /**
   * Get transcription status
   */
  async getStatus(sessionId: string): Promise<TranscriptionStatus> {
    const response = await fetch(`${API_BASE}/api/long-video/status/${sessionId}`);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get status');
    }
    
    return response.json();
  },

  /**
   * Get transcription result
   */
  async getResult(sessionId: string): Promise<TranscriptionResult> {
    const response = await fetch(`${API_BASE}/api/long-video/result/${sessionId}`);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get result');
    }
    
    return response.json();
  },

  /**
   * List all sessions
   */
  async listSessions(): Promise<string[]> {
    const response = await fetch(`${API_BASE}/api/long-video/sessions`);
    
    if (!response.ok) {
      return [];
    }
    
    return response.json();
  },
};
