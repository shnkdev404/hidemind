import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bot } from "lucide-react";
import Markdown from "react-markdown";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { ActionBadge, Card, CodeChip, ErrorNote, Spinner } from "../components/ui";
import { inr, shortDate } from "../format";

export default function VendorDetail() {
  const id = useParams().id!;
  const { data, isPending, error } = useQuery({ queryKey: ["vendor", id], queryFn: () => api.vendor(id) });
  if (isPending) return <Spinner label="Loading vendor…" />;
  if (error || !data) return <ErrorNote error={error ?? "Not found"} />;
  const v = data.vendor;

  return (
    <div className="space-y-4">
      <Link to="/vendors" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft className="h-4 w-4" /> Vendors</Link>
      <div>
        <h1 className="font-serif text-2xl font-semibold text-slate-900">{v.name}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {v.category} · {v.city} · GSTIN {v.gstin} · {v.email_domain} · Bank {v.bank_ifsc} {v.bank_account} (verified {shortDate(v.bank_verified_on)})
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3" title="🧠 Dossier - what Munshi knows"
          action={data.dossier?.last_refreshed_at && <span className="text-xs text-slate-400">refreshed {shortDate(data.dossier.last_refreshed_at)}</span>}>
          {data.dossier?.content ? (
            <div className="prose-munshi text-sm text-slate-700"><Markdown>{data.dossier.content}</Markdown></div>
          ) : (
            <p className="text-sm text-slate-500">
              {data.dossier_error ? `Dossier unavailable: ${data.dossier_error}` : "Nothing consolidated yet. The dossier is a Hindsight mental model that refreshes automatically as decisions accumulate."}
            </p>
          )}
        </Card>
        <Card className="lg:col-span-2" title={`Decision history (${data.history.length})`}>
          {!data.history.length ? <p className="text-sm text-slate-500">No exceptions yet.</p> : (
            <ol className="space-y-3">
              {[...data.history].reverse().map((h) => (
                <li key={h.case_id} className="border-l-2 border-slate-200 pl-3 text-sm">
                  <Link to={`/cases/${h.case_id}`} className="flex flex-wrap items-center gap-2 hover:underline">
                    <span className="text-xs text-slate-400">W{h.week} · {shortDate(h.date)}</span>
                    <CodeChip label={h.code} />
                    {h.decision ? <ActionBadge action={h.decision} /> : <span className="text-xs text-amber-700">pending</span>}
                    {h.auto && <Bot className="h-3.5 w-3.5 text-brand-700" />}
                  </Link>
                  <div className="text-xs text-slate-500">{h.invoice_no} · {inr(h.total, true)}{h.decided_by && ` · ${h.decided_by}`}</div>
                  {h.reason && <p className="mt-0.5 text-xs italic text-slate-600">"{h.reason}"</p>}
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </div>
  );
}
