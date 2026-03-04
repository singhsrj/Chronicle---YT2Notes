import React, { createContext, useContext, useReducer, useCallback, useEffect } from 'react';
import { Session, SessionStatus } from '../types';

// Storage key
const STORAGE_KEY = 'chronicle_sessions';

interface SessionState {
  sessions: Session[];
  activeSessionId: string | null;
  isLoading: boolean;
}

type SessionAction =
  | { type: 'SET_SESSIONS'; sessions: Session[] }
  | { type: 'ADD_SESSION'; session: Session }
  | { type: 'UPDATE_SESSION'; sessionId: string; updates: Partial<Session> }
  | { type: 'DELETE_SESSION'; sessionId: string }
  | { type: 'SET_ACTIVE_SESSION'; sessionId: string | null }
  | { type: 'SET_LOADING'; isLoading: boolean };

interface SessionContextType extends SessionState {
  addSession: (title: string, videoUrl: string) => Session;
  updateSession: (sessionId: string, updates: Partial<Session>) => void;
  deleteSession: (sessionId: string) => void;
  setActiveSession: (sessionId: string | null) => void;
  getActiveSession: () => Session | undefined;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

function sessionReducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case 'SET_SESSIONS':
      return { ...state, sessions: action.sessions };
    
    case 'ADD_SESSION':
      return { ...state, sessions: [action.session, ...state.sessions] };
    
    case 'UPDATE_SESSION':
      return {
        ...state,
        sessions: state.sessions.map(s =>
          s.id === action.sessionId
            ? { ...s, ...action.updates, updatedAt: new Date().toISOString() }
            : s
        ),
      };
    
    case 'DELETE_SESSION':
      return {
        ...state,
        sessions: state.sessions.filter(s => s.id !== action.sessionId),
        activeSessionId: state.activeSessionId === action.sessionId ? null : state.activeSessionId,
      };
    
    case 'SET_ACTIVE_SESSION':
      return { ...state, activeSessionId: action.sessionId };
    
    case 'SET_LOADING':
      return { ...state, isLoading: action.isLoading };
    
    default:
      return state;
  }
}

function loadSessionsFromStorage(): Session[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveSessionsToStorage(sessions: Session[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch (e) {
    console.error('Failed to save sessions:', e);
  }
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(sessionReducer, {
    sessions: [],
    activeSessionId: null,
    isLoading: true,
  });

  // Load sessions from storage on mount
  useEffect(() => {
    const sessions = loadSessionsFromStorage();
    dispatch({ type: 'SET_SESSIONS', sessions });
    dispatch({ type: 'SET_LOADING', isLoading: false });
  }, []);

  // Save sessions to storage whenever they change
  useEffect(() => {
    if (!state.isLoading) {
      saveSessionsToStorage(state.sessions);
    }
  }, [state.sessions, state.isLoading]);

  const addSession = useCallback((title: string, videoUrl: string): Session => {
    const session: Session = {
      id: crypto.randomUUID(),
      title: title || 'Untitled Session',
      videoUrl,
      status: 'idle',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    dispatch({ type: 'ADD_SESSION', session });
    dispatch({ type: 'SET_ACTIVE_SESSION', sessionId: session.id });
    return session;
  }, []);

  const updateSession = useCallback((sessionId: string, updates: Partial<Session>) => {
    dispatch({ type: 'UPDATE_SESSION', sessionId, updates });
  }, []);

  const deleteSession = useCallback((sessionId: string) => {
    dispatch({ type: 'DELETE_SESSION', sessionId });
  }, []);

  const setActiveSession = useCallback((sessionId: string | null) => {
    dispatch({ type: 'SET_ACTIVE_SESSION', sessionId });
  }, []);

  const getActiveSession = useCallback((): Session | undefined => {
    return state.sessions.find(s => s.id === state.activeSessionId);
  }, [state.sessions, state.activeSessionId]);

  return (
    <SessionContext.Provider
      value={{
        ...state,
        addSession,
        updateSession,
        deleteSession,
        setActiveSession,
        getActiveSession,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within SessionProvider');
  }
  return context;
}
