import { useState, useCallback, useRef } from 'react';
import { transcriptionApi, notesApi } from '../services';
import { useSession } from '../context';
import { TranscriptionStatus } from '../types';

export function useTranscription() {
  const { updateSession, getActiveSession } = useSession();
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollingRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(async (sessionId: string, backendSessionId: string) => {
    try {
      const status: TranscriptionStatus = await transcriptionApi.getStatus(backendSessionId);
      
      updateSession(sessionId, {
        status: status.status,
      });

      if (status.status === 'completed') {
        stopPolling();
        // Fetch the full result
        const result = await transcriptionApi.getResult(backendSessionId);
        updateSession(sessionId, {
          transcript: result.full_text,
          status: 'completed',
        });
        setIsProcessing(false);
      } else if (status.status === 'error') {
        stopPolling();
        setError(status.error || 'Transcription failed');
        setIsProcessing(false);
      }
    } catch (err) {
      console.error('Polling error:', err);
    }
  }, [updateSession, stopPolling]);

  const startTranscription = useCallback(async (
    sessionId: string,
    videoUrl: string,
    options?: { model?: string; language?: string }
  ) => {
    setIsProcessing(true);
    setError(null);

    try {
      updateSession(sessionId, { status: 'downloading' });

      const response = await transcriptionApi.startTranscription({
        url: videoUrl,
        model_name: (options?.model as 'base') || 'base',
        language: options?.language || 'en',
      });

      const backendSessionId = response.session_id;

      // Start polling for status
      pollingRef.current = window.setInterval(() => {
        pollStatus(sessionId, backendSessionId);
      }, 2000);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start transcription');
      updateSession(sessionId, { status: 'error' });
      setIsProcessing(false);
    }
  }, [updateSession, pollStatus]);

  return {
    startTranscription,
    stopPolling,
    isProcessing,
    error,
  };
}

export function useNotesGeneration() {
  const { updateSession } = useSession();
  const [isGenerating, setIsGenerating] = useState(false);
  const [streamedNotes, setStreamedNotes] = useState('');
  const [error, setError] = useState<string | null>(null);

  const generateNotes = useCallback(async (
    sessionId: string,
    transcript: string,
    title?: string
  ) => {
    setIsGenerating(true);
    setStreamedNotes('');
    setError(null);

    let accumulatedNotes = '';

    try {
      updateSession(sessionId, { status: 'generating_notes' });

      // Try streaming first, fall back to regular if not available
      try {
        for await (const chunk of notesApi.generateNotesStream({ transcript, title })) {
          accumulatedNotes += chunk;
          setStreamedNotes(accumulatedNotes);
        }
      } catch {
        // Fall back to non-streaming
        const response = await notesApi.generateNotes({ transcript, title });
        if (response.status === 'ok' && response.notes) {
          accumulatedNotes = response.notes;
          setStreamedNotes(accumulatedNotes);
        } else {
          throw new Error(response.error || 'Failed to generate notes');
        }
      }

      // Save final notes
      updateSession(sessionId, {
        notes: accumulatedNotes,
        status: 'completed',
      });

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate notes');
      updateSession(sessionId, { status: 'error' });
    } finally {
      setIsGenerating(false);
    }
  }, [updateSession]);

  return {
    generateNotes,
    isGenerating,
    streamedNotes,
    error,
  };
}
