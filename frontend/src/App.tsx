import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { BarChart3, BookOpen, Brain, Building2, ChevronRight, Database, Grid3x3, Inbox, MessageSquare, RotateCcw } from "lucide-react";
import { useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { toast } from "sonner";
import { api } from "./api";
import { Button } from "./components/ui";
import { shortDate } from "./format";
import Ask from "./pages/Ask";
import CaseDetail from "./pages/CaseDetail";
import MemoryInspector from "./pages/MemoryInspector";
import MetricsPage from "./pages/Metrics";
import Playbook from "./pages/Playbook";
import Queue from "./pages/Queue";
import Trust from "./pages/Trust";
import VendorDetail from "./pages/VendorDetail";
import Vendors from "./pages/Vendors";
import { useEvents } from "./useEvents";

const NAV = [
  { to: "/", label: "Exception queue", icon: Inbox, end: true },
  { to: "/trust", label: "Trust ladder", icon: Grid3x3 },
  { to: "/vendors", label: "Vendors", icon: Building2 },
  { to: "/playbook", label: "AP playbook", icon: BookOpen },
  { to: "/ask", label: "Ask Munshi", icon: MessageSquare },
  { to: "/metrics", label: "Learning curve", icon: BarChart3 },
  { to: "/memory", label: "Memory inspector", icon: Database },
];

function MemoryPill({ status }: { status?: string }) {
  const style = status === "on" ? "bg-emerald-50 text-emerald-700" : status === "degraded" ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-500";
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium", style)}>
      <Brain className="h-3.5 w-3.5" /> Hindsight {status ?? "…"}
    </span>
  );
}

function TopBar() {
  const qc = useQueryClient();
  const { data: h } = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 4000 });
  const { data: snaps } = useQuery({ queryKey: ["snapshots"], queryFn: api.snapshots });
  const [resetOpen, setResetOpen] = useState(false);

  const sim = useMutation({
    mutationFn: api.simulate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["health"] }),
    onError: (e) => toast.error(e.message),
  });
  const reset = useMutation({
    mutationFn: api.reset,
    onMutate: (to) => toast.loading(`Restoring ${to}…`, { id: "reset" }),
    onSuccess: (_, to) => { toast.success(`Restored ${to}`, { id: "reset" }); qc.invalidateQueries(); },
    onError: (e) => toast.error(e.message, { id: "reset" }),
    onSettled: () => setResetOpen(false),
  });

  const week = h?.week ?? 0;
  const live = week >= (h?.history_weeks ?? 12);
  const finished = week >= (h?.last_week ?? 14);

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/90 px-6 py-3 backdrop-blur">
      <div className="flex items-center gap-3">
        <span className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white">
          Week {week}{week > 0 && <span className="font-normal text-slate-300"> · {shortDate(h?.business_date)}</span>}
        </span>
        {week > 0 && (
          <span className={clsx("text-xs font-medium", live ? "text-brand-700" : "text-slate-500")}>
            {live ? "● Live weeks" : "Replaying history"}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <MemoryPill status={h?.memory} />
        {h?.llm === "off" && <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500">LLM off</span>}
        <div className="relative">
          <Button variant="secondary" onClick={() => setResetOpen((o) => !o)} disabled={h?.simulating || reset.isPending}>
            <RotateCcw className="h-4 w-4" /> Reset
          </Button>
          {resetOpen && (
            <div className="absolute right-0 mt-1 w-44 rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
              {Array.from(new Set(["week0", ...(snaps ?? [])])).map((s) => (
                <button key={s} onClick={() => reset.mutate(s)} className="block w-full rounded px-3 py-1.5 text-left text-sm hover:bg-slate-100">
                  {s === "week0" ? "Week 0 (empty memory)" : s.replace("week", "Week ")}
                </button>
              ))}
            </div>
          )}
        </div>
        <Button onClick={() => sim.mutate()} disabled={h?.simulating || sim.isPending || finished}>
          {h?.simulating ? "Simulating…" : finished ? "All weeks done" : <>Simulate next week <ChevronRight className="h-4 w-4" /></>}
        </Button>
      </div>
    </header>
  );
}

export default function App() {
  useEvents();
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="px-5 py-5">
          <div className="font-serif text-2xl font-bold text-brand-700">Munshi</div>
          <div className="text-xs text-slate-500">The AP clerk who never forgets</div>
        </div>
        <nav className="flex-1 space-y-0.5 px-3">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) => clsx("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium",
                isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-50")}>
              <Icon className="h-4 w-4" /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-100 px-5 py-4 text-xs text-slate-400">
          Charminar Foods Pvt Ltd<br />AP desk · Hyderabad
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-6">
          <Routes>
            <Route path="/" element={<Queue />} />
            <Route path="/cases/:id" element={<CaseDetail />} />
            <Route path="/trust" element={<Trust />} />
            <Route path="/vendors" element={<Vendors />} />
            <Route path="/vendors/:id" element={<VendorDetail />} />
            <Route path="/playbook" element={<Playbook />} />
            <Route path="/ask" element={<Ask />} />
            <Route path="/metrics" element={<MetricsPage />} />
            <Route path="/memory" element={<MemoryInspector />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
