import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorNote, PageHeader, Spinner } from "../components/ui";

export default function Vendors() {
  const { data, isPending, error } = useQuery({ queryKey: ["vendors"], queryFn: api.vendors });
  if (isPending) return <Spinner label="Loading vendors…" />;
  if (error) return <ErrorNote error={error} />;
  return (
    <>
      <PageHeader title="Vendors" subtitle="Open a vendor to see the dossier Munshi has built from every decision." />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data!.map((v) => (
          <Link key={v.id} to={`/vendors/${v.id}`} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-brand-500">
            <div className="flex items-start justify-between gap-2">
              <div className="font-medium text-slate-900">{v.name}</div>
              {v.msme && <span className="shrink-0 rounded bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-800">MSME</span>}
            </div>
            <div className="mt-0.5 text-xs text-slate-500">{v.category} · {v.city}</div>
            <div className="mt-3 flex gap-4 text-xs text-slate-600">
              <span><b className="text-slate-900">{v.invoices}</b> invoices</span>
              <span><b className="text-slate-900">{v.exceptions}</b> exceptions</span>
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}
