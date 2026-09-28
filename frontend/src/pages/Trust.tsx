import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../api";
import { Empty, ErrorNote, PageHeader, Spinner } from "../components/ui";
import { LEVEL_NAME } from "../format";

const CELL = [
  "bg-slate-100 text-slate-500",
  "bg-sky-100 text-sky-800",
  "bg-emerald-500 text-white",
];

export default function Trust() {
  const { data, isPending, error } = useQuery({ queryKey: ["trust"], queryFn: api.trust });
  if (isPending) return <Spinner label="Loading trust ladder…" />;
  if (error) return <ErrorNote error={error} />;
  const cells = new Map(data!.cells.map((c) => [`${c.vendor_id}|${c.exc_code}`, c]));
  const vendors = data!.vendors.filter((v) => data!.cells.some((c) => c.vendor_id === v.id));

  return (
    <>
      <PageHeader
        title="Trust ladder"
        subtitle="Munshi earns autonomy per vendor × exception type. Intern: suggests only. Associate: one-click accept. Senior: auto-resolves (with a daily digest). One override on a risky case sends it back to Intern."
      />
      <div className="mb-4 flex gap-3 text-xs">
        {LEVEL_NAME.map((n, i) => <span key={n} className={clsx("rounded px-2 py-1 font-medium", CELL[i])}>{["🎒", "🧑‍💼", "🎓"][i]} {n}</span>)}
      </div>
      {!vendors.length ? <Empty title="No decisions yet">Simulate a few weeks to watch Munshi earn trust.</Empty> : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <th className="px-4 py-2 text-left">Vendor</th>
                {data!.codes.map((c) => <th key={c.code} className="px-2 py-2 text-center font-medium">{c.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {vendors.map((v) => (
                <tr key={v.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-2 font-medium text-slate-800">{v.name}</td>
                  {data!.codes.map((c) => {
                    const cell = cells.get(`${v.id}|${c.code}`);
                    return (
                      <td key={c.code} className="px-2 py-2 text-center">
                        {cell ? (
                          <div className={clsx("mx-auto w-28 rounded-lg px-2 py-1.5 transition-colors duration-700", CELL[cell.level])}
                            title={`${cell.n_agree}/${cell.n_decisions} decisions agreed`}>
                            <div className="text-xs font-semibold">{LEVEL_NAME[cell.level]}</div>
                            <div className="text-[11px] opacity-80">{cell.n_agree}/{cell.n_decisions} agreed</div>
                          </div>
                        ) : <span className="text-slate-300">·</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
