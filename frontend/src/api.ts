export type Action = "APPROVE" | "APPROVE_PARTIAL" | "REJECT" | "HOLD" | "ESCALATE";

export interface Health {
  memory: "on" | "off" | "degraded";
  memory_error: string | null;
  bank_id: string;
  llm: "on" | "off";
  model: string;
  week: number;
  business_date: string;
  last_week: number;
  history_weeks: number;
  simulating: boolean;
}

export interface CaseSummary {
  id: number;
  invoice_id: string;
  invoice_no: string;
  invoice_date: string;
  vendor_id: string;
  vendor: string;
  week: number;
  primary_code: string;
  label: string;
  codes: string[];
  amount_at_stake: number;
  total: number;
  status: string;
  proposal: { action: Action; confidence: number; mode: string; guard_overrode: boolean; novel_case: boolean } | null;
  decision: { action: Action; auto: boolean; decided_by: string; agreed: boolean | null } | null;
  trust_level: number;
}

export interface Receipt {
  id: string;
  text: string;
  type: string;
  date: string | null;
  document_id: string | null;
  metadata: Record<string, string>;
  tags: string[];
}

export interface Proposal {
  id: number;
  mode: string;
  action: Action;
  approved_amount: number | null;
  confidence: number;
  rationale: string;
  risk_flags: string[];
  precedents_used: string[];
  receipts: Receipt[];
  based_on: {
    memories?: { id: string; text: string; type: string }[];
    mental_models?: { id: string; name?: string }[];
    directives?: { id: string; name: string }[];
  };
  novel_case: boolean;
  guard_overrode: boolean;
  guard_reason: string | null;
  trust_level: number;
  trust_level_name: string;
  latency_ms: number;
}

export interface Line {
  sku: string;
  description: string;
  hsn?: string;
  unit?: string;
  qty: number;
  unit_price: number;
  gst_rate: number;
}

export interface Finding {
  code: string;
  summary: string;
  amount_at_stake: number;
  variance_pct: number | null;
  detail: Record<string, unknown>;
}

export interface CaseDetail {
  case: { id: number; primary_code: string; label: string; findings: Finding[]; status: string; week: number; amount_at_stake: number };
  invoice: {
    id: string; invoice_no: string; invoice_date: string; po_ref: string | null; gstin: string; bank_account: string;
    bank_ifsc: string; sender_email: string; lines: Line[]; charges: { description: string; amount: number }[];
    subtotal: number; gst_amount: number; total: number; pdf_path: string | null;
  };
  vendor: { id: string; name: string; city: string; gstin: string; msme: boolean; email_domain: string; bank_account: string; bank_ifsc: string };
  po: { id: string; po_date: string; lines: Line[] } | null;
  grn: { id: string; received_date: string; lines: { sku: string; qty_received: number }[] } | null;
  proposal: Proposal | null;
  amnesia: Proposal | null;
  decision: { action: Action; decided_by: string; role: string; reason: string; auto: boolean; agreed_with_agent: boolean | null } | null;
  trust: { level: number; name: string; n_decisions: number; n_agree: number };
}

export interface TrustGrid {
  vendors: { id: string; name: string }[];
  codes: { code: string; label: string }[];
  cells: { vendor_id: string; exc_code: string; level: number; level_name: string; n_decisions: number; n_agree: number }[];
}

export interface WeekRow {
  week: number;
  invoices: number;
  exceptions: number;
  auto_resolved: number;
  auto_rate: number;
  accuracy: number | null;
  agreement: number | null;
  avg_confidence: number | null;
  risk_blocked: number;
}

export interface Metrics {
  weeks: WeekRow[];
  trust_levels: { intern: number; associate: number; senior: number };
  total_exceptions: number;
  total_auto: number;
  risk_blocked: number;
}

export interface MentalModel {
  id: string;
  name: string;
  content: string | null;
  last_refreshed_at: string | null;
  is_stale?: boolean;
}

export interface VendorRow {
  id: string; name: string; city: string; gstin: string; msme: boolean; category: string;
  bank_account: string; invoices: number; exceptions: number;
}

export interface VendorDetail {
  vendor: VendorRow & { email_domain: string; bank_ifsc: string; bank_verified_on: string };
  history: { case_id: number; week: number; date: string; invoice_no: string; code: string; total: number;
             decision: Action | null; decided_by: string | null; reason: string | null; auto: boolean }[];
  dossier: MentalModel | null;
  dossier_error: string | null;
}

export interface MemoryItem {
  id: string;
  text: string;
  context: string | null;
  fact_type: string;
  document_id: string | null;
  mentioned_at: string | null;
  occurred_start: string | null;
  entities: unknown;
  tags: string[] | null;
  metadata: Record<string, string> | null;
  proof_count: number | null;
  consolidated_at: string | null;
  source_memory_ids: string[] | null;
}

export interface MemoryOverview {
  bank_id: string;
  profile: { name?: string; mission?: string; disposition?: Record<string, number>; error?: string };
  stats: {
    total_nodes?: number; total_links?: number; total_documents?: number; total_observations?: number;
    nodes_by_fact_type?: Record<string, number>; pending_operations?: number; failed_operations?: number;
    last_consolidated_at?: string | null; last_memory_write_at?: string | null; pending_consolidation?: number; error?: string;
  };
  directives: { items?: { id: string; name: string; content: string; priority: number; is_active: boolean }[]; error?: string };
  mental_models: { items?: MentalModel[]; error?: string };
  entities: { items?: { id: string; canonical_name: string; mention_count: number }[]; error?: string };
}

export interface MemoryOpRow { id: number; kind: string; ref: string; status: string; error: string | null; created_at: string }

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : msg;
    } catch { /* not json */ }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<Health>("/api/health"),
  queue: (status: string) => req<CaseSummary[]>(`/api/queue?status=${status}`),
  case: (id: number) => req<CaseDetail>(`/api/cases/${id}`),
  decide: (id: number, body: { action: Action; reason: string; decided_by: string; role: string; approved_amount?: number | null }) =>
    req(`/api/cases/${id}/decide`, { method: "POST", body: JSON.stringify(body) }),
  propose: (id: number, mode: "MEMORY" | "AMNESIA") => req<Proposal>(`/api/cases/${id}/propose?mode=${mode}`, { method: "POST" }),
  trust: () => req<TrustGrid>("/api/trust"),
  vendors: () => req<VendorRow[]>("/api/vendors"),
  vendor: (id: string) => req<VendorDetail>(`/api/vendors/${id}`),
  playbook: () => req<MentalModel>("/api/playbook"),
  playbookHistory: () => req<{ previous_content?: string; content?: string; changed_at?: string }[]>("/api/playbook/history"),
  fraud: () => req<MentalModel>("/api/fraud-watchlist"),
  refreshModels: () => req("/api/memory/refresh", { method: "POST" }),
  ask: (question: string) => req<{ text: string; based_on: Proposal["based_on"] }>("/api/ask", { method: "POST", body: JSON.stringify({ question }) }),
  metrics: () => req<Metrics>("/api/metrics"),
  memoryOverview: () => req<MemoryOverview>("/api/memory/overview"),
  memoryItems: (type: string, q: string, offset = 0) =>
    req<{ items: MemoryItem[]; total: number }>(`/api/memory/items?limit=50&offset=${offset}${type ? `&type=${type}` : ""}${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  memoryRecall: (q: string, vendor: string) =>
    req<(Receipt & { scores?: Record<string, number>; occurred_start?: string; mentioned_at?: string })[]>(
      `/api/memory/recall?q=${encodeURIComponent(q)}${vendor ? `&vendor=${vendor}` : ""}`),
  memoryLog: () => req<MemoryOpRow[]>("/api/memory/log"),
  simulate: () => req<{ started: boolean; week: number }>("/api/simulate/next-week", { method: "POST" }),
  snapshots: () => req<string[]>("/api/demo/snapshots"),
  reset: (to: string) => req(`/api/demo/reset?to=${to}`, { method: "POST" }),
};
