import { useState, useEffect, useCallback } from 'react';

const API_BASE = '/api';
const STORAGE_KEY_SESSION = 'beliefstate_selected_session';

export function useDashboard() {
  const [sessions, setSessions] = useState<string[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(
    () => localStorage.getItem(STORAGE_KEY_SESSION)
  );
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [sseConnected, setSseConnected] = useState(false);
  const [trackingStatus, setTrackingStatus] = useState<string>('idle');
  const [lastSseEvent, setLastSseEvent] = useState<number>(Date.now());
  const [refreshSignal, setRefreshSignal] = useState(0);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`);
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch (e) {
      console.error('Failed to fetch sessions:', e);
    }
  }, []);

  const refreshData = useCallback(async () => {
    setLoading(true);
    await fetchSessions();
    setRefreshSignal(n => n + 1);
    setLoading(false);
  }, [fetchSessions]);

  const handleSetSelectedSession = useCallback((session: string | null) => {
    setSelectedSession(session);
    if (session) {
      localStorage.setItem(STORAGE_KEY_SESSION, session);
    } else {
      localStorage.removeItem(STORAGE_KEY_SESSION);
    }
  }, []);

  useEffect(() => {
    fetchSessions();

    const es = new EventSource(`${API_BASE}/events`);
    es.onopen = () => { setSseConnected(true); setTrackingStatus('connected'); };
    es.onerror = () => { setSseConnected(false); setTrackingStatus('disconnected'); };
    es.onmessage = () => {
      setLastSseEvent(Date.now());
      setTrackingStatus('active');
      fetchSessions();
    };

    return () => {
      es.close();
      setSseConnected(false);
      setTrackingStatus('idle');
    };
  }, [fetchSessions]);

  useEffect(() => {
    if (trackingStatus === 'active') {
      const timer = setTimeout(() => setTrackingStatus('connected'), 3000);
      return () => clearTimeout(timer);
    }
  }, [lastSseEvent, trackingStatus]);

  return {
    sessions,
    selectedSession,
    setSelectedSession: handleSetSelectedSession,
    activeTab,
    setActiveTab,
    loading,
    setLoading,
    sseConnected,
    trackingStatus,
    refreshData,
    refreshSignal,
  };
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiPost<T>(path: string, body: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
