export interface Belief {
  subject: string;
  predicate: string;
  value: string;
  confidence: number;
  belief_type: string;
  is_hypothetical: boolean;
  category: string;
  source: string;
  source_quote: string;
  turn: number;
  resolution_note: string;
  created_at?: string;
}

export interface Conflict {
  id: string;
  session_id: string;
  existing_belief: Belief;
  new_belief: Belief;
  score: number;
  reason: string;
  resolution: string;
  resolution_note: string;
  created_at: string;
}

export interface SessionStats {
  total_beliefs: number;
  by_category: Record<string, number>;
  by_source: Record<string, number>;
  by_type: Record<string, number>;
  by_confidence_range: Record<string, number>;
  by_hypothetical: { yes: number; no: number };
  avg_confidence: number;
  latest_turn: number;
  entities: number;
  contradiction_count: number;
}

export interface SimulatorResult {
  context_prompt: string;
  extracted_beliefs: Belief[];
  would_inject: boolean;
  raw_llm: string | null;
  timing_ms: { context: number; extraction: number; total: number };
  token_estimate: number;
  total_beliefs_in_store: number;
}

export interface ActivityEntry {
  type: string;
  session_id: string;
  timestamp: string;
  data: Record<string, any>;
}

export interface CompareResult {
  session_a: string;
  session_b: string;
  only_in_a: Belief[];
  only_in_b: Belief[];
  changed: { subject: string; predicate: string; old: Belief; new: Belief }[];
  same: Belief[];
  summary: { total_a: number; total_b: number; only_in_a: number; only_in_b: number; changed: number; same: number };
}

export interface StoreStats {
  type: string;
  sessions: number;
  total_beliefs: number;
  healthy: boolean;
}

export interface ProviderInfo {
  internal?: { name: string; model?: string };
  app?: { name: string; model?: string };
  extractor?: { name: string; model?: string };
}

export interface DashboardConfig {
  max_beliefs: number;
  belief_budget_tokens: number;
  similarity_threshold: number;
  contradiction_threshold: number;
  entailment_threshold: number;
  resolution_strategy: string;
  respect_strategy_for_updates: boolean;
  enable_staleness_scoring: boolean;
  staleness_threshold: number;
  belief_sort_strategy: string;
  min_injection_confidence: number;
  include_hypothetical_in_context: boolean;
  store_type: string;
  enable_dashboard: boolean;
}

export type Tab = { id: string; label: string; icon: string };
export type Session = { id: string };
