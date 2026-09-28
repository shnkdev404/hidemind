import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { toast } from "sonner";
import { LEVEL_NAME } from "./format";

/** Subscribes to the backend SSE stream: live toasts + cache invalidation. */
export function useEvents() {
  const qc = useQueryClient();

  useEffect(() => {
    const es = new EventSource("/api/events");
    const refresh = () => qc.invalidateQueries();

    es.onmessage = (e) => {
      let ev: Record<string, unknown>;
      try {
        ev = JSON.parse(e.data);
      } catch {
        return;
      }
      switch (ev.kind) {
        case "week_started":
          toast.loading(`Simulating week ${ev.week}…`, { id: "sim" });
          qc.invalidateQueries({ queryKey: ["health"] });
          break;
        case "week_done":
          toast.success(`Week ${ev.week} processed`, {
            id: "sim",
            description: `${ev.exceptions} exceptions · ${ev.auto_resolved} auto-resolved${ev.graded ? ` · ${ev.correct}/${ev.graded} proposals matched the team` : ""}`,
          });
          refresh();
          break;
        case "promoted":
          toast.success(`🎓 Munshi promoted to ${LEVEL_NAME[ev.level as number]}`, { description: `${ev.vendor} · ${ev.code}` });
          qc.invalidateQueries({ queryKey: ["trust"] });
          break;
        case "demoted":
          toast.warning(`Munshi demoted to ${LEVEL_NAME[ev.level as number]}`, { description: `${ev.vendor} · ${ev.code} - a human overrode it` });
          qc.invalidateQueries({ queryKey: ["trust"] });
          break;
        case "memorised":
          toast(`🧠 Memorised`, { description: `Decision on ${ev.vendor} stored in Hindsight`, duration: 2500 });
          break;
        case "reset":
          toast.info(`Demo reset to ${ev.to}`);
          refresh();
          break;
        case "error":
          toast.error(String(ev.message), { id: "sim" });
          refresh();
          break;
      }
    };
    return () => es.close();
  }, [qc]);
}
