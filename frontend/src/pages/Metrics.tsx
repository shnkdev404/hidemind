import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Card, Empty, ErrorNote, PageHeader, Spinner } from "../components/ui";

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
    </div>
  );
}

export default function MetricsPage() {
  const { data, isPending, error } = useQuery({ queryKey: ["metrics"], queryFn: api.metrics });
  if (isPending) return <Spinner label="Loading metrics…" />;
  if (error) return <ErrorNote error={error} />;
  const m = data!;
  const rows = m.weeks.map((w) => ({
    week: `W${w.week}`,
    accuracy: w.accuracy != null ? Math.round(w.accuracy * 100) : null,
    auto: Math.round(w.auto_rate * 100),
    confidence: w.avg_confidence != null ? Math.round(w.avg_confidence * 100) : null,
  }));

  return (
    <>
      <PageHeader title="Learning curve" subtitle="Measured from the audit tables - how often Munshi's proposal matched what the team actually decided, week by week." />
      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        <Stat label="Exceptions handled" value={m.total_exceptions} />
        <Stat label="Auto-resolved" value={m.total_auto} hint="Senior-level cells only" />
        <Stat label="Risky payments blocked" value={m.risk_blocked} hint="bank changes & duplicates" />
        <Stat label="Trust cells" value={`${m.trust_levels.senior} 🎓 · ${m.trust_levels.associate} 🧑‍💼 · ${m.trust_levels.intern} 🎒`} />
      </div>
      {!rows.length ? <Empty title="No data yet">Simulate a few weeks to draw the curve.</Empty> : (
        <Card title="Proposal accuracy, auto-resolution and confidence by week">
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v) => `${v}%`} />
                <Legend />
                <Line type="monotone" dataKey="accuracy" name="Matched the team" stroke="#0f766e" strokeWidth={3} dot connectNulls />
                <Line type="monotone" dataKey="auto" name="Auto-resolved" stroke="#6366f1" strokeWidth={2} dot />
                <Line type="monotone" dataKey="confidence" name="Avg confidence" stroke="#94a3b8" strokeDasharray="4 4" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}
    </>
  );
}
