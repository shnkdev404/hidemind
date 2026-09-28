import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Brain, Database, Search, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { api, type MemoryItem } from "../api";
import { Button, Card, Empty, ErrorNote, PageHeader, Spinner } from "../components/ui";
import { shortDate } from "../format";

const TYPES = [
  { key: "", label: "All" },
  { key: "world", label: "World facts" },
  { key: "experience", label: "Experiences" },
  { key: "observation", label: "Learned patterns" },
];

const TYPE_STYLE: Record<string, string> = {
  world: "bg-sky-100 text-sky-800",
  experience: "bg-amber-100 text-amber-800",
  observation: "bg-violet-100 text-violet-800",
};

function TypeBadge({ type }: { type: string }) {
  return (
    <span className={clsx("rounded px-1.5 py-0.5 text-[11px] font-medium", TYPE_STYLE[type] ?? "bg-slate-100 text-slate-600")}>
      {type === "observation" ? "learned pattern" : type}
    </span>
  );
}

function Stat({ label, value, hint }: { label: string; value: string | number | undefined; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value ?? "–"}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
    </div>
  );
}

function MemoryRow({ m }: { m: MemoryItem }) {
  return (
    <li className="border-b border-slate-100 py-2.5 last:border-0">
      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <TypeBadge type={m.fact_type} />
        {(m.occurred_start || m.mentioned_at) && <span>{shortDate(m.occurred_start ?? m.mentioned_at)}</span>}
        {m.fact_type === "observation" && m.proof_count ? <span>· backed by {m.proof_count} memories</span> : null}
        {m.metadata?.decided_by && <span>· {m.metadata.decided_by}</span>}
        {m.document_id && <span className="font-mono text-[11px] text-slate-400">{m.document_id}</span>}
      </div>
      <p className="text-sm text-slate-700">{m.text}</p>
      {!!m.tags?.length && (
        <div className="mt-1 flex flex-wrap gap-1">{m.tags.map((t) => <span key={t} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">{t}</span>)}</div>
      )}
    </li>
  );
}

function Browser() {
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, isPending, error } = useQuery({
    queryKey: ["memory-items", type, search, offset],
    queryFn: () => api.memoryItems(type, search, offset),
  });
  return (
    <Card title="Memory browser" action={data && <span className="text-xs text-slate-400">{data.total} memories</span>}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {TYPES.map((t) => (
          <button key={t.key} onClick={() => { setType(t.key); setOffset(0); }}
            className={clsx("rounded-lg px-2.5 py-1 text-xs font-medium", type === t.key ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100")}>
            {t.label}
          </button>
        ))}
        <form onSubmit={(e) => { e.preventDefault(); setSearch(q); setOffset(0); }} className="ml-auto flex gap-1">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter text…" className="w-48 rounded-lg border border-slate-300 px-2.5 py-1 text-sm" />
          <Button type="submit" variant="secondary"><Search className="h-3.5 w-3.5" /></Button>
        </form>
      </div>
      {error ? <ErrorNote error={error} /> : isPending ? <Spinner /> : !data?.items.length ? (
        <p className="py-6 text-center text-sm text-slate-500">No memories yet. Simulate a week, or decide a case, and they will appear here.</p>
      ) : (
        <>
          <ul className="max-h-[32rem] overflow-y-auto pr-1">{data.items.map((m) => <MemoryRow key={m.id} m={m} />)}</ul>
          <div className="mt-3 flex justify-between">
            <Button variant="ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>← Newer</Button>
            <Button variant="ghost" disabled={offset + 50 >= data.total} onClick={() => setOffset(offset + 50)}>Older →</Button>
          </div>
        </>
      )}
    </Card>
  );
}

function RecallPlayground({ vendors }: { vendors: { id: string; name: string }[] }) {
  const [q, setQ] = useState("How are freight charges handled?");
  const [vendor, setVendor] = useState("");
  const recall = useMutation({ mutationFn: () => api.memoryRecall(q, vendor) });
  return (
    <Card title={<span className="flex items-center gap-2"><Search className="h-4 w-4" /> Recall playground</span>}
      action={<span className="text-xs text-slate-400">semantic · keyword · graph · temporal</span>}>
      <p className="mb-3 text-xs text-slate-500">This is the exact retrieval Munshi runs before every recommendation. Scope it to a vendor to see tag filtering at work.</p>
      <form onSubmit={(e) => { e.preventDefault(); recall.mutate(); }} className="flex flex-wrap gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
        <select value={vendor} onChange={(e) => setVendor(e.target.value)} className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm">
          <option value="">All vendors</option>
          {vendors.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
        </select>
        <Button type="submit" disabled={recall.isPending || !q.trim()}>{recall.isPending ? "Recalling…" : "Recall"}</Button>
      </form>
      {recall.error && <div className="mt-3"><ErrorNote error={recall.error} /></div>}
      {recall.data && (
        recall.data.length ? (
          <ol className="mt-3 space-y-2">
            {recall.data.map((r, i) => (
              <li key={r.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                <div className="mb-0.5 flex items-center gap-2 text-xs text-slate-500">
                  <span className="font-semibold text-slate-400">#{i + 1}</span><TypeBadge type={r.type} />
                  {(r.occurred_start || r.mentioned_at) && <span>{shortDate(r.occurred_start ?? r.mentioned_at)}</span>}
                </div>
                <p className="text-slate-700">{r.text}</p>
              </li>
            ))}
          </ol>
        ) : <p className="mt-3 text-sm text-slate-500">Nothing recalled for that query.</p>
      )}
    </Card>
  );
}

export default function MemoryInspector() {
  const ov = useQuery({ queryKey: ["memory-overview"], queryFn: api.memoryOverview, refetchInterval: 15_000 });
  const log = useQuery({ queryKey: ["memory-log"], queryFn: api.memoryLog, refetchInterval: 10_000 });
  const vendors = useQuery({ queryKey: ["vendors"], queryFn: api.vendors });

  if (ov.isPending) return <Spinner label="Opening the memory bank…" />;
  if (ov.error) {
    return (
      <>
        <PageHeader title="Memory inspector" subtitle="What Munshi actually remembers, straight from Hindsight." />
        <Empty title="Hindsight is not connected"><ErrorNote error={ov.error} /></Empty>
      </>
    );
  }
  const o = ov.data!;
  if (o.profile.error && o.stats.error) {
    return (
      <>
        <PageHeader title="Memory inspector" subtitle="What Munshi actually remembers, straight from Hindsight." />
        <Empty title="Can't reach Hindsight">
          <p className="mb-2">{o.profile.error}</p>
          <p>Start it with <code className="rounded bg-slate-100 px-1">python scripts/start_hindsight.py</code> (local Docker) or check <code className="rounded bg-slate-100 px-1">HINDSIGHT_URL</code> in <code className="rounded bg-slate-100 px-1">.env</code>.</p>
        </Empty>
      </>
    );
  }
  const byType = o.stats.nodes_by_fact_type ?? {};
  const disposition = o.profile.disposition ?? {};

  return (
    <>
      <PageHeader title="Memory inspector"
        subtitle={<>What Munshi actually remembers, read live from Hindsight bank <code className="rounded bg-slate-100 px-1 text-xs">{o.bank_id}</code>.</>} />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Memories" value={o.stats.total_nodes} hint={`${byType.world ?? 0} world · ${byType.experience ?? 0} experience`} />
        <Stat label="Learned patterns" value={o.stats.total_observations ?? byType.observation} hint="consolidated observations" />
        <Stat label="Documents retained" value={o.stats.total_documents} hint="cases, emails, contracts" />
        <Stat label="Graph links" value={o.stats.total_links} hint="entity · temporal · semantic" />
        <Stat label="Pending" value={(o.stats.pending_operations ?? 0) + (o.stats.pending_consolidation ?? 0)}
          hint={o.stats.last_consolidated_at ? `last consolidated ${shortDate(o.stats.last_consolidated_at)}` : "not consolidated yet"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Browser />
          <RecallPlayground vendors={vendors.data ?? []} />
        </div>
        <div className="space-y-4">
          <Card title={<span className="flex items-center gap-2"><Brain className="h-4 w-4" /> Bank identity</span>}>
            <p className="text-sm leading-relaxed text-slate-700">{o.profile.mission ?? o.profile.error ?? "–"}</p>
            <div className="mt-3 space-y-1.5">
              {Object.entries(disposition).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2 text-xs">
                  <span className="w-20 capitalize text-slate-500">{k}</span>
                  <div className="flex gap-0.5">{[1, 2, 3, 4, 5].map((i) => <span key={i} className={clsx("h-2 w-5 rounded-sm", i <= v ? "bg-brand-600" : "bg-slate-200")} />)}</div>
                  <span className="tabular-nums text-slate-500">{v}/5</span>
                </div>
              ))}
            </div>
          </Card>

          <Card title={<span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> Directives (hard rules)</span>}>
            <ul className="space-y-2">
              {(o.directives.items ?? []).sort((a, b) => b.priority - a.priority).map((d) => (
                <li key={d.id} className="text-sm">
                  <div className="font-medium text-slate-800">{d.name} <span className="text-xs font-normal text-slate-400">priority {d.priority}</span></div>
                  <p className="text-xs text-slate-600">{d.content}</p>
                </li>
              ))}
            </ul>
          </Card>

          <Card title={`Mental models (${o.mental_models.items?.length ?? 0})`}>
            <ul className="space-y-1.5 text-sm">
              {(o.mental_models.items ?? []).map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-2">
                  <span className="truncate text-slate-700">{m.name}</span>
                  <span className="shrink-0 text-xs text-slate-400">{m.last_refreshed_at ? shortDate(m.last_refreshed_at) : "not built yet"}</span>
                </li>
              ))}
            </ul>
          </Card>

          {!!o.entities.items?.length && (
            <Card title="Top entities">
              <div className="flex flex-wrap gap-1.5">
                {o.entities.items.slice(0, 30).map((e) => (
                  <span key={e.id} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{e.canonical_name} <span className="text-slate-400">{e.mention_count}</span></span>
                ))}
              </div>
            </Card>
          )}

          <Card title={<span className="flex items-center gap-2"><Database className="h-4 w-4" /> Retain log</span>}>
            {!log.data?.length ? <p className="text-sm text-slate-500">Nothing sent to Hindsight yet.</p> : (
              <ul className="max-h-72 space-y-1 overflow-y-auto text-xs">
                {log.data.map((op) => (
                  <li key={op.id} className="flex items-center justify-between gap-2">
                    <span className="font-mono text-slate-600">{op.ref}</span>
                    <span className={clsx("rounded px-1.5 py-0.5", op.status === "FAILED" ? "bg-rose-50 text-rose-700" : op.status === "DONE" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500")}
                      title={op.error ?? ""}>{op.status.toLowerCase()}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
