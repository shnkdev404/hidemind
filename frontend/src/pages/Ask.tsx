import { useMutation } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useState } from "react";
import Markdown from "react-markdown";
import { api, type Proposal } from "../api";
import { Button, PageHeader, Spinner } from "../components/ui";

const SUGGESTIONS = [
  "Why do we pay Deccan Steel above the PO price, and has that rule changed?",
  "Which vendors have been involved in fraud attempts, and what were the warning signs?",
  "How do we handle freight charges from Sri Lakshmi Packaging?",
  "What should I know before paying Godavari Agro?",
];

type Msg = { role: "user" | "munshi"; text: string; based_on?: Proposal["based_on"] };

export default function Ask() {
  const [q, setQ] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const ask = useMutation({
    mutationFn: api.ask,
    onSuccess: (r) => setMsgs((m) => [...m, { role: "munshi", text: r.text, based_on: r.based_on }]),
    onError: (e) => setMsgs((m) => [...m, { role: "munshi", text: `⚠ ${e.message}` }]),
  });
  const send = (text: string) => {
    if (!text.trim() || ask.isPending) return;
    setMsgs((m) => [...m, { role: "user", text }]);
    setQ("");
    ask.mutate(text);
  };

  return (
    <>
      <PageHeader title="Ask Munshi" subtitle="Questions answered from the AP desk's memory (Hindsight reflect), with the evidence used." />
      <div className="mx-auto max-w-3xl space-y-4">
        {!msgs.length && (
          <div className="grid gap-2 sm:grid-cols-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => send(s)} className="rounded-xl border border-slate-200 bg-white p-3 text-left text-sm text-slate-700 hover:border-brand-500">{s}</button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            <div className={m.role === "user" ? "max-w-[80%] rounded-2xl bg-slate-900 px-4 py-2 text-sm text-white"
              : "rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm"}>
              {m.role === "user" ? m.text : <div className="prose-munshi text-slate-700"><Markdown>{m.text}</Markdown></div>}
              {m.based_on && (m.based_on.memories?.length ?? 0) > 0 && (
                <details className="mt-2 border-t border-slate-100 pt-2">
                  <summary className="cursor-pointer text-xs font-medium text-slate-500">🧾 Based on {m.based_on.memories!.length} memories
                    {(m.based_on.mental_models?.length ?? 0) > 0 && ` + ${m.based_on.mental_models!.length} mental model(s)`}</summary>
                  <ul className="mt-2 space-y-1.5">
                    {m.based_on.memories!.slice(0, 10).map((f) => <li key={f.id} className="rounded bg-slate-50 px-2 py-1 text-xs text-slate-600">{f.text}</li>)}
                  </ul>
                </details>
              )}
            </div>
          </div>
        ))}
        {ask.isPending && <Spinner label="Munshi is thinking through its memory…" />}
        <form onSubmit={(e) => { e.preventDefault(); send(q); }} className="flex gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about a vendor, a rule, a past decision…"
            className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5 text-sm focus:border-brand-600 focus:outline-none" />
          <Button type="submit" disabled={ask.isPending || !q.trim()}><Send className="h-4 w-4" /></Button>
        </form>
      </div>
    </>
  );
}
