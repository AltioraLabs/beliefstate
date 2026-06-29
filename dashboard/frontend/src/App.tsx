import React, { useEffect } from 'react';
import { Overview } from './components/Overview';
import { BeliefsTable } from './components/BeliefsTable';
import { ConflictsLog } from './components/ConflictsLog';
import { Simulator } from './components/Simulator';
import { Settings } from './components/Settings';
import { Timeline } from './components/Timeline';
import { ActivityLog } from './components/ActivityLog';
import { SessionCompare } from './components/SessionCompare';
import { Layout } from './components/Layout';
import { useDashboard } from './hooks/useDashboard';
import { useNotifications } from './hooks/useNotifications';

const TABS = [
  { id: 'overview', label: 'Overview', icon: 'layout-dashboard' },
  { id: 'beliefs', label: 'Beliefs', icon: 'brain' },
  { id: 'timeline', label: 'Timeline', icon: 'history' },
  { id: 'conflicts', label: 'Conflicts', icon: 'shield-alert' },
  { id: 'activity', label: 'Activity', icon: 'activity' },
  { id: 'compare', label: 'Compare', icon: 'git-compare' },
  { id: 'simulator', label: 'Simulator', icon: 'play-circle' },
  { id: 'settings', label: 'Settings', icon: 'settings' },
];

function App() {
  const {
    activeTab, setActiveTab, sessions, selectedSession,
    setSelectedSession, refreshData, loading, sseConnected, trackingStatus,
  } = useDashboard();

  const notif = useNotifications(selectedSession);

  useEffect(() => {
    if (sessions.length > 0 && !selectedSession) {
      setSelectedSession(sessions[0]);
    }
  }, [sessions, selectedSession, setSelectedSession]);

  const shared = {
    tabs: TABS, activeTab, setActiveTab,
    sessions, selectedSession, setSelectedSession,
    loading: false, refreshData, sseConnected, trackingStatus,
    notif,
  };

  return (
    <Layout {...shared}>
      {activeTab === 'overview' && selectedSession && <Overview sessionId={selectedSession} onRefresh={refreshData} />}
      {activeTab === 'beliefs' && selectedSession && <BeliefsTable sessionId={selectedSession} onRefresh={refreshData} />}
      {activeTab === 'timeline' && selectedSession && <Timeline sessionId={selectedSession} />}
      {activeTab === 'conflicts' && selectedSession && <ConflictsLog sessionId={selectedSession} onRefresh={refreshData} />}
      {activeTab === 'activity' && selectedSession && <ActivityLog sessionId={selectedSession} />}
      {activeTab === 'compare' && selectedSession && <SessionCompare sessionId={selectedSession} sessions={sessions} />}
      {activeTab === 'simulator' && selectedSession && <Simulator sessionId={selectedSession} />}
      {activeTab === 'settings' && <Settings alerts={notif.alerts} onUpdateAlerts={notif.setAlerts} />}
    </Layout>
  );
}

export default App;
