import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, Bot, Brain, BrainCircuit, FileText, ShieldAlert, Sparkles } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { api, type Action, type CaseDetail as Detail, type Proposal } from "../api";
import { ActionBadge, Button, Card, CodeChip, ConfidenceBar, ErrorNote, Spinner, TrustBadge } from "../components/ui";
import { ACTION_LABEL, inr, shortDate } from "../format";

const ACTIONS: Action[] = ["APPROVE", "APPROVE_PARTIAL", "REJECT", "HOLD", "ESCALATE"];
const PEOPLE = [
  { name: "Priya Reddy", role: "AP Lead" },
  { name: "Ravi Kumar", role: "Senior AP Accountant" },
  { name: "Anjali Rao", role: "AP Associate" },
];

function MatchTable({ d }: { d: Detail }) {
  const po = new Map((d.po?.lines ?? []).map((l) => [l.sku, l]));
  const grn = new Map((d.grn?.lines ?? []).map((l) => [l.sku, l.qty_received]));
  const bad = "bg-rose-50 font-semibold text-rose-700";
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs uppercase tracking-wide text-slate-500">
          <tr className="border-b border-slate-200">
            <th className="py-2 text-left">Line</th>
            <th className="py-2 text-right">PO qty</th><th className="py-2 text-right">Received</th><th className="py-2 text-right">Invoiced</th>
            <th className="py-2 text-right">PO rate</th><th className="py-2 text-right">Invoice rate</th><th className="py-2 text-right">GST</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {d.invoice.lines.map((l) => {
            const p = po.get(l.sku);
            const rec = grn.get(l.sku);
            const priceOff = p && Math.abs(l.unit_price - p.unit_price) / p.unit_price > 0.005;
            return (
              <tr key={l.sku} className="border-b border-slate-100">
                <td className="py-2 pr-2">{l.description}<div className="text-xs text-slate-400">{l.sku} · HSN {l.hsn}</div></td>
                <td className="py-2 text-right">{p ? `${p.qty} ${p.unit}` : <span className={bad}>not on PO</span>}</td>
                <td className={clsx("py-2 text-right", rec !== undefined && l.qty > rec && bad)}>{rec ?? "–"}</td>
                <td className="py-2 text-right">{l.qty} {l.unit}</td>
                <td className="py-2 text-right">{p ? inr(p.unit_price) : "–"}</td>
                <td className={clsx("py-2 text-right", priceOff && bad)}>{inr(l.unit_price)}</td>
                <td className="py-2 text-right">{l.gst_rate}%</td>
              </tr>
            );
          })}
          {d.invoice.charges.map((c) => (
            <tr key={c.description} className="border-b border-slate-100">
              <td className="py-2">{c.description}</td>
              <td className={clsx("py-2 text-right", bad)} colSpan={4}>not on PO</td>
              <td className={clsx("py-2 text-right", bad)}>{inr(c.amount)}</td><td />
            </tr>
          ))}
        </tbody>
        <tfoot className="tabular-nums">
          <tr><td colSpan={5} className="pt-3 text-right text-slate-500">Taxable</td><td className="pt-3 text-right" colSpan={2}>{inr(d.invoice.subtotal)}</td></tr>
          <tr><td colSpan={5} className="text-right text-slate-500">GST</td><td className="text-right" colSpan={2}>{inr(d.invoice.gst_amount)}</td></tr>
          <tr><td colSpan={5} className="text-right font-semibold">Total</td><td className="text-right font-semibold" colSpan={2}>{inr(d.invoice.total)}</td></tr>
        </tfoot>
      </table>
    </div>
  );
}

function Receipts({ p }: { p: Proposal }) {
  const facts = p.based_on?.memories ?? [];
  if (!p.receipts.length && !facts.length && !p.precedents_used.length) {
    return <p className="text-sm text-slate-500">No precedent in memory - this is a new situation for Munshi.</p>;
  }
  return (
    <div className="space-y-2">
      {p.receipts.map((r) => (
        <div key={r.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
          <div className="mb-0.5 flex items-center gap-2 text-xs text-slate-500">
            <span className={clsx("rounded px-1.5 py-0.5 font-medium", r.type === "observation" ? "bg-violet-100 text-violet-700" : "bg-slate-200 text-slate-700")}>
              {r.type === "observation" ? "learned pattern" : r.type}
            </span>
            {r.date && <span>{shortDate(r.date)}</span>}
            {r.metadata?.decided_by && <span>· {r.metadata.decided_by}</span>}
            {r.metadata?.decision && <ActionBadge action={r.metadata.decision} />}
          </div>
          <p className="text-slate-700">{r.text}</p>
        </div>
      ))}
      {!p.receipts.length && facts.slice(0, 6).map((f) => (
        <div key={f.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{f.text}</div>
      ))}
      {p.precedents_used.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-xs font-medium text-slate-500">Precedents Munshi cited ({p.precedents_used.length})</summary>
          <ul className="mt-1 list-disc pl-5 text-slate-600">{p.precedents_used.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </details>
      )}
      {(p.based_on?.directives?.length ?? 0) > 0 && (
        <p className="text-xs text-slate-500">Directives applied: {p.based_on.directives!.map((d) => d.name).join(", ")}</p>
      )}
    </div>
  );
}

function ProposalCard({ p, title, icon, muted }: { p: Proposal; title: string; icon: ReactNode; muted?: boolean }) {
  return (
    <Card className={clsx(muted && "bg-slate-50")} title={<span className="flex items-center gap-2">{icon}{title}</span>}
      action={<span className="text-xs text-slate-400">{(p.latency_ms / 1000).toFixed(1)}s</span>}>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <ActionBadge action={p.action} large />
        {p.approved_amount ? <span className="text-sm tabular-nums">for {inr(p.approved_amount)}</span> : null}
        <ConfidenceBar value={p.confidence} />
        {p.novel_case && <span className="rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-800">new situation</span>}
      </div>
      {p.guard_overrode && (
        <div className="mb-3 flex gap-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" /> <span><b>Guard:</b> {p.guard_reason}</span>
        </div>
      )}
      <p className="text-sm leading-relaxed text-slate-700">{p.rationale}</p>
      {p.risk_flags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">{p.risk_flags.map((f) => <span key={f} className="rounded bg-rose-50 px-2 py-0.5 text-xs text-rose-700">⚠ {f}</span>)}</div>
      )}
      {p.mode !== "AMNESIA" && (
        <div className="mt-4 border-t border-slate-100 pt-3">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">🧾 Receipts - why Munshi thinks so</h3>
          <Receipts p={p} />
        </div>
      )}
      {p.mode === "FALLBACK" && <p className="mt-3 text-xs text-amber-700">Memory was unavailable - this proposal was made without Hindsight.</p>}
    </Card>
  );
}

function DecisionForm({ d }: { d: Detail }) {
  const qc = useQueryClient();
  const [action, setAction] = useState<Action>(d.proposal?.action ?? "APPROVE");
  const [reason, setReason] = useState("");
  const [person, setPerson] = useState(0);
  const [amount, setAmount] = useState<string>(d.proposal?.approved_amount?.toString() ?? "");
  const m = useMutation({
    mutationFn: () => api.decide(d.case.id, {
      action, reason, decided_by: PEOPLE[person].name, role: PEOPLE[person].role,
      approved_amount: action === "APPROVE_PARTIAL" && amount ? Number(amount) : null,
    }),
    onSuccess: () => {
      toast.success(action === d.proposal?.action ? "Decision recorded - Munshi agreed with you" : "Decision recorded - Munshi will learn from this correction");
      qc.invalidateQueries();
    },
    onError: (e) => toast.error(e.message),
  });

  return (
    <Card title="Your decision" action={<span className="text-xs text-slate-500">Your reason teaches Munshi</span>}>
      <div className="mb-3 flex flex-wrap gap-2">
        {ACTIONS.map((a) => (
          <button key={a} onClick={() => setAction(a)}
            className={clsx("rounded-lg border px-3 py-1.5 text-sm font-medium",
              action === a ? "border-brand-700 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-600 hover:bg-slate-50")}>
            {ACTION_LABEL[a]}{d.proposal?.action === a && " ✦"}
          </button>
        ))}
      </div>
      {action === "APPROVE_PARTIAL" && (
        <input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Approved amount (₹)"
          className="mb-3 w-48 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
      )}
      <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3}
        placeholder='Why? e.g. "Freight of ₹1,200 is agreed in our 2024 contract."'
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none" />
      <div className="mt-3 flex items-center justify-between">
        <select value={person} onChange={(e) => setPerson(Number(e.target.value))} className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm">
          {PEOPLE.map((p, i) => <option key={p.name} value={i}>{p.name} · {p.role}</option>)}
        </select>
        <Button onClick={() => m.mutate()} disabled={m.isPending}>{m.isPending ? "Saving…" : "Record decision"}</Button>
      </div>
    </Card>
  );
}

export default function CaseDetail() {
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const { data: d, isPending, error } = useQuery({ queryKey: ["case", id], queryFn: () => api.case(id) });
  const [compare, setCompare] = useState(false);

  const amnesia = useMutation({
    mutationFn: () => api.propose(id, "AMNESIA"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case", id] }),
    onError: (e) => toast.error(e.message),
  });
  const rerun = useMutation({
    mutationFn: () => api.propose(id, "MEMORY"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case", id] }),
    onError: (e) => toast.error(e.message),
  });

  if (isPending) return <Spinner label="Loading case…" />;
  if (error || !d) return <ErrorNote error={error ?? "Not found"} />;

  const toggleCompare = () => {
    const next = !compare;
    setCompare(next);
    if (next && !d.amnesia && !amnesia.isPending) amnesia.mutate();
  };

  return (
    <div className="space-y-4">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft className="h-4 w-4" /> Queue</Link>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-serif text-2xl font-semibold text-slate-900">
            <Link to={`/vendors/${d.vendor.id}`} className="hover:underline">{d.vendor.name}</Link>
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {d.invoice.invoice_no} · {shortDate(d.invoice.invoice_date)} · PO {d.invoice.po_ref ?? "none"} · {d.invoice.sender_email}
            {d.vendor.msme && <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-800">MSME · 45-day rule</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <TrustBadge level={d.trust.level} />
          <span className="text-xs text-slate-500">{d.trust.n_agree}/{d.trust.n_decisions} agreed for this vendor × exception</span>
          {d.invoice.pdf_path && (
            <a href={`/api/invoices/${d.invoice.id}/pdf`} target="_blank" rel="noreferrer"><Button variant="secondary"><FileText className="h-4 w-4" /> PDF</Button></a>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-3">
          <Card title="What's wrong" action={<div className="flex gap-1">{d.case.findings.map((f) => <CodeChip key={f.code + f.summary} label={f.code} />)}</div>}>
            <ul className="mb-4 space-y-1.5 text-sm">
              {d.case.findings.map((f, i) => <li key={i} className="flex gap-2"><span className="text-rose-500">●</span>{f.summary}</li>)}
            </ul>
            <MatchTable d={d} />
          </Card>
          {d.decision ? (
            <Card title="Decision">
              <div className="flex items-center gap-2 text-sm">
                {d.decision.auto && <Bot className="h-4 w-4 text-brand-700" />}
                <b>{d.decision.decided_by}</b> <span className="text-slate-500">{d.decision.role}</span> <ActionBadge action={d.decision.action} />
                {d.decision.agreed_with_agent === false && <span className="text-xs text-amber-700">overrode Munshi</span>}
              </div>
              {d.decision.reason && <p className="mt-2 text-sm italic text-slate-600">"{d.decision.reason}"</p>}
            </Card>
          ) : <DecisionForm d={d} />}
        </div>

        <div className="space-y-4 lg:col-span-2">
          <div className="flex items-center justify-between">
            <button onClick={toggleCompare}
              className={clsx("inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium",
                compare ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-700")}>
              <Brain className="h-4 w-4" /> {compare ? "Comparing: memory ON vs OFF" : "Compare with memory OFF"}
            </button>
            {!d.decision && <Button variant="ghost" onClick={() => rerun.mutate()} disabled={rerun.isPending}><Sparkles className="h-4 w-4" />{rerun.isPending ? "Thinking…" : "Re-run"}</Button>}
          </div>
          {d.proposal ? <ProposalCard p={d.proposal} title="Munshi (with Hindsight memory)" icon={<BrainCircuit className="h-4 w-4 text-brand-700" />} />
            : <Card><p className="text-sm text-slate-500">No proposal yet.</p></Card>}
          {compare && (amnesia.isPending ? <Card><Spinner label="Asking the same LLM without memory…" /></Card>
            : d.amnesia ? <ProposalCard p={d.amnesia} title="Generic AI (no memory)" icon={<Brain className="h-4 w-4 text-slate-400" />} muted />
            : amnesia.error ? <ErrorNote error={amnesia.error} /> : null)}
        </div>
      </div>
    </div>
  );
}
