import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Bot, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type CaseSummary } from "../api";
import { ActionBadge, CodeChip, ConfidenceBar, Empty, ErrorNote, PageHeader, Spinner, TrustBadge } from "../components/ui";
import { inr, shortDate } from "../format";

const TABS = [
  { key: "open", label: "Needs review" },
  { key: "resolved", label: "Resolved" },
  { key: "all", label: "All" },
];

function Row({ c }: { c: CaseSummary }) {
  const p = c.proposal;
  return (
    <Link to={`/cases/${c.id}`}
      className="grid grid-cols-12 items-center gap-3 border-b border-slate-100 px-4 py-3 text-sm last:border-0 hover:bg-slate-50">
      <div className="col-span-3 min-w-0">
        <div className="truncate font-medium text-slate-900">{c.vendor}</div>
        <div className="text-xs text-slate-500">{c.invoice_no} · {shortDate(c.invoice_date)}</div>
      </div>
      <div className="col-span-2 flex flex-wrap gap-1">
        <CodeChip label={c.label} />
        {c.codes.length > 1 && <span className="text-xs text-slate-400">+{c.codes.length - 1}</span>}
      </div>
      <div className="col-span-2 text-right tabular-nums">
        <div className="font-medium">{inr(c.total, true)}</div>
        <div className="text-xs text-slate-500">at stake {inr(c.amount_at_stake, true)}</div>
      </div>
      <div className="col-span-3">
        {p ? (
          <div className="flex items-center gap-2">
            <ActionBadge action={p.action} />
            <ConfidenceBar value={p.confidence} />
            {p.guard_overrode && <ShieldAlert className="h-4 w-4 text-rose-500" aria-label="Guard fired" />}
          </div>
        ) : <span className="text-xs text-slate-400">no proposal yet</span>}
        {p && p.mode !== "MEMORY" && <div className="mt-0.5 text-[11px] text-slate-400">{p.mode.toLowerCase()} (no memory)</div>}
      </div>
      <div className="col-span-2 flex flex-col items-end gap-1">
        {c.decision ? (
          <span className={clsx("inline-flex items-center gap-1 text-xs", c.decision.auto ? "text-brand-700" : "text-slate-600")}>
            {c.decision.auto && <Bot className="h-3.5 w-3.5" />}
            {c.decision.auto ? "Auto" : c.decision.decided_by.split(" ")[0]}: <ActionBadge action={c.decision.action} />
          </span>
        ) : <TrustBadge level={c.trust_level} />}
        <span className="text-[11px] text-slate-400">Week {c.week}</span>
      </div>
    </Link>
  );
}

export default function Queue() {
  const [tab, setTab] = useState("open");
  const { data, isPending, error } = useQuery({ queryKey: ["queue", tab], queryFn: () => api.queue(tab) });
  const autoToday = tab === "open" ? null : data?.filter((c) => c.decision?.auto).length;

  return (
    <>
      <PageHeader
        title="Exception queue"
        subtitle="Invoices that failed the 3-way match. Munshi proposes; you decide - and every decision teaches it."
      />
      <div className="mb-3 flex items-center gap-1">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={clsx("rounded-lg px-3 py-1.5 text-sm font-medium",
              tab === t.key ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100")}>
            {t.label}
          </button>
        ))}
        {autoToday ? <span className="ml-3 text-sm text-brand-700"><Bot className="inline h-4 w-4" /> {autoToday} resolved by Munshi</span> : null}
      </div>
      {error && <ErrorNote error={error} />}
      {isPending ? <Spinner label="Loading queue…" /> : !data?.length ? (
        <Empty title={tab === "open" ? "Nothing waiting for review" : "No cases yet"}>
          Click <b>Simulate next week</b> to replay the next business week of invoices.
        </Empty>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="grid grid-cols-12 gap-3 border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            <div className="col-span-3">Vendor / invoice</div>
            <div className="col-span-2">Exception</div>
            <div className="col-span-2 text-right">Amount</div>
            <div className="col-span-3">Munshi recommends</div>
            <div className="col-span-2 text-right">Status</div>
          </div>
          {data.map((c) => <Row key={c.id} c={c} />)}
        </div>
      )}
    </>
  );
}
