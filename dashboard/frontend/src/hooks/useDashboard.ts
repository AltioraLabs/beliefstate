import { useState, useEffect, useCallback } from 'react';

const API_BASE = '/api';

export function useDashboard() {
  const [sessions, setSessions] = useState<string[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [sseConnected, setSseConnected] = useState(false);
  const [trackingStatus, setTrackingStatus] = useState<string>('idle');
  const [lastSseEvent, setLastSseEvent] = useState<number>(Date.now());

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
    setLoading(false);
  }, [fetchSessions]);

  useEffect(() => {
    fetchSessions();

    const es = new EventSource(`${API_BASE}/events`);
    es.onopen = () => { setSseConnected(true); setTrackingStatus('connected'); };
    es.onerror = () => { setSseConnected(false); setTrackingStatus('disconnected'); };
    es.onmessage = (event) => {
      setLastSseEvent(Date.now());
      setTrackingStatus('active');
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'update') {
          fetchSessions();
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
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
    setSelectedSession,
    activeTab,
    setActiveTab,
    loading,
    setLoading,
    sseConnected,
    trackingStatus,
    refreshData,
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
