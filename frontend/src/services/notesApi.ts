import { NotesRequest, NotesResponse, OllamaStatus } from '../types';

const API_BASE = 'http://localhost:8000';

export const notesApi = {
  /**
   * Check Ollama health status
   */
  async checkHealth(): Promise<OllamaStatus> {
    const response = await fetch(`${API_BASE}/notes/health`);
    return response.json();
  },

  /**
   * Generate notes from transcript (non-streaming)
   */
  async generateNotes(request: NotesRequest): Promise<NotesResponse> {
    const response = await fetch(`${API_BASE}/notes/from-json`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to generate notes');
    }

    return response.json();
  },

  /**
   * Generate notes with streaming support
   * Returns an async generator for streaming chunks
   */
  async *generateNotesStream(request: NotesRequest): AsyncGenerator<string, void, unknown> {
    const response = await fetch(`${API_BASE}/notes/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to generate notes');
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      yield chunk;
    }
  },
};
