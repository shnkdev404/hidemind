const inrFmt = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const inrWhole = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export const inr = (x: number | null | undefined, whole = false) =>
  x == null ? "–" : (whole ? inrWhole : inrFmt).format(x);

export const pct = (x: number | null | undefined, digits = 0) => (x == null ? "–" : `${(x * 100).toFixed(digits)}%`);

export const shortDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "–";

export const ACTION_LABEL: Record<string, string> = {
  APPROVE: "Approve",
  APPROVE_PARTIAL: "Approve partial",
  REJECT: "Reject",
  HOLD: "Hold",
  ESCALATE: "Escalate",
};

export const LEVEL_NAME = ["Intern", "Associate", "Senior"];
