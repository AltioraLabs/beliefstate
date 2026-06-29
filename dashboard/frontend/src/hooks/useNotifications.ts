import { useState, useEffect, useCallback, useRef } from 'react';

export interface Notification {
  id: string;
  type: 'alert' | 'conflict' | 'info';
  title: string;
  message: string;
  timestamp: number;
  read: boolean;
}

export interface AlertRule {
  id: string;
  name: string;
  metric: 'contradiction_count' | 'confidence_drop' | 'new_beliefs' | 'entity_count';
  condition: 'gt' | 'lt' | 'eq';
  value: number;
  target?: string;
  enabled: boolean;
}

const STORAGE_KEY = 'belifstate_alerts';
const NOTIFS_KEY = 'belifstate_notifications';

function loadAlerts(): AlertRule[] {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch { return []; }
}

function loadNotifs(): Notification[] {
  try { return JSON.parse(localStorage.getItem(NOTIFS_KEY) || '[]'); } catch { return []; }
}

export function useNotifications(sessionId: string | null) {
  const [alerts, setAlertsRaw] = useState<AlertRule[]>(loadAlerts);
  const [notifications, setNotifsRaw] = useState<Notification[]>(loadNotifs);
  const [unreadCount, setUnreadCount] = useState(0);
  const prevStats = useRef<Record<string, number>>({});

  const setAlerts = useCallback((a: AlertRule[]) => {
    setAlertsRaw(a);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(a));
  }, []);

  const addNotif = useCallback((n: Omit<Notification, 'id' | 'timestamp' | 'read'>) => {
    const full: Notification = { ...n, id: crypto.randomUUID(), timestamp: Date.now(), read: false };
    setNotifsRaw(prev => {
      const next = [full, ...prev].slice(0, 100);
      localStorage.setItem(NOTIFS_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const markRead = useCallback((id: string) => {
    setNotifsRaw(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
  }, []);

  const markAllRead = useCallback(() => {
    setNotifsRaw(prev => prev.map(n => ({ ...n, read: true })));
  }, []);

  const clearNotifs = useCallback(() => {
    setNotifsRaw([]);
    localStorage.removeItem(NOTIFS_KEY);
  }, []);

  useEffect(() => {
    setUnreadCount(notifications.filter(n => !n.read).length);
  }, [notifications]);

  useEffect(() => {
    if (!sessionId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/sessions/${sessionId}/stats`);
        const stats = await res.json();
        const p = prevStats.current;
        for (const rule of alerts) {
          if (!rule.enabled) continue;
          const current = stats[rule.metric] ?? 0;
          const prev = p[rule.metric] ?? current;
          let triggered = false;
          if (rule.condition === 'gt' && current > rule.value && prev <= rule.value) triggered = true;
          if (rule.condition === 'lt' && current < rule.value && prev >= rule.value) triggered = true;
          if (rule.condition === 'eq' && current === rule.value && prev !== rule.value) triggered = true;
          if (triggered) {
            addNotif({ type: 'alert', title: `Alert: ${rule.name}`, message: `${rule.metric} is now ${current} (threshold: ${rule.condition} ${rule.value})` });
          }
        }
        prevStats.current = { ...p, [rule.metric]: stats[rule.metric] ?? 0 };
      } catch {}
    }, 15000);
    return () => clearInterval(interval);
  }, [sessionId, alerts, addNotif]);

  return { notifications, unreadCount, alerts, setAlerts, addNotif, markRead, markAllRead, clearNotifs };
}
