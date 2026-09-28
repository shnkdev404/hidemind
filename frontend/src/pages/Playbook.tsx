import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import { toast } from "sonner";
import { api } from "../api";
import { Button, Card, Empty, ErrorNote, PageHeader, Spinner } from "../components/ui";
import { shortDate } from "../format";

export default function Playbook() {
  const qc = useQueryClient();
  const pb = useQuery({ queryKey: ["playbook"], queryFn: api.playbook });
  const hist = useQuery({ queryKey: ["playbook-history"], queryFn: api.playbookHistory });
  const fraud = useQuery({ queryKey: ["fraud"], queryFn: api.fraud });
  const refresh = useMutation({
    mutationFn: api.refreshModels,
    onMutate: () => toast.loading("Refreshing mental models…", { id: "refresh" }),
    onSuccess: () => { toast.success("Refresh requested - content updates in the background", { id: "refresh" }); qc.invalidateQueries(); },
    onError: (e) => toast.error(e.message, { id: "refresh" }),
  });

  // Versions oldest -> newest. History entries hold the content *before* each change; current content is last.
  const versions = [
    ...[...(hist.data ?? [])].reverse().map((h) => ({ content: h.previous_content ?? h.content ?? "", at: h.changed_at })),
    ...(pb.data?.content ? [{ content: pb.data.content, at: pb.data.last_refreshed_at ?? undefined }] : []),
  ].filter((v) => v.content);
  const [idx, setIdx] = useState(0);
  useEffect(() => setIdx(Math.max(0, versions.length - 1)), [versions.length]);
  const shown = versions[idx];

  return (
    <>
      <PageHeader
        title="AP playbook"
        subtitle="Nobody wrote this manual. Munshi consolidated it from the team's decisions (a Hindsight mental model that refreshes itself)."
        action={<Button variant="secondary" onClick={() => refresh.mutate()} disabled={refresh.isPending}><RefreshCw className="h-4 w-4" /> Refresh now</Button>}
      />
      {pb.error && <ErrorNote error={pb.error} />}
      {pb.isPending ? <Spinner label="Loading playbook…" /> : !versions.length ? (
        <Empty title="The playbook is still empty">It fills in as decisions are retained and Hindsight consolidates them into observations.</Empty>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2" title={`Version ${idx + 1} of ${versions.length}`}
            action={<span className="text-xs text-slate-400">{shown?.at ? shortDate(shown.at) : ""}</span>}>
            {versions.length > 1 && (
              <div className="mb-4">
                <input type="range" min={0} max={versions.length - 1} value={idx} onChange={(e) => setIdx(Number(e.target.value))}
                  className="w-full accent-teal-700" />
                <div className="flex justify-between text-[11px] text-slate-400"><span>first version</span><span>today</span></div>
              </div>
            )}
            <div className="prose-munshi text-sm text-slate-700"><Markdown>{shown?.content ?? ""}</Markdown></div>
          </Card>
          <Card title="🛡️ Fraud watchlist">
            {fraud.data?.content ? <div className="prose-munshi text-sm text-slate-700"><Markdown>{fraud.data.content}</Markdown></div>
              : <p className="text-sm text-slate-500">No fraud signals recorded yet.</p>}
          </Card>
        </div>
      )}
    </>
  );
}
