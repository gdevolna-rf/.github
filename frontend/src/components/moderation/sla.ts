/**
 * SLA marker for a moderation case (TRUST-07 «очередь, SLA»): the server sets `due_at` and `is_overdue`;
 * the client only words it. Resolved cases have no marker.
 */
import { formatNumber, plural, WORDS } from "@/lib/format";

export interface SlaInfo {
  tone: "overdue" | "soon" | "ok" | "none";
  text: string;
  /** For screen readers / title. */
  long: string;
}

const SOON_HOURS = 6;

function span(ms: number): string {
  const minutes = Math.max(1, Math.round(Math.abs(ms) / 60_000));
  if (minutes < 60) return `${minutes} ${plural(minutes, WORDS.minute)}`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} ${plural(hours, WORDS.hour)}`;
  const days = Math.round(hours / 24);
  return `${formatNumber(days)} ${plural(days, WORDS.day)}`;
}

export function slaInfo(
  c: { due_at: string | null; is_overdue?: boolean; status: unknown },
  now: Date = new Date(),
): SlaInfo {
  const status = typeof c.status === "string" ? c.status : (c.status as { code?: string } | null)?.code;
  if (status === "resolved" || !c.due_at) return { tone: "none", text: "", long: "" };
  const due = new Date(c.due_at).getTime();
  if (Number.isNaN(due)) return { tone: "none", text: "", long: "" };
  const diff = due - now.getTime();
  if (c.is_overdue || diff <= 0) {
    const s = span(diff);
    return { tone: "overdue", text: `Просрочено на ${s}`, long: `Срок рассмотрения по SLA истёк ${s} назад` };
  }
  const s = span(diff);
  return {
    tone: diff <= SOON_HOURS * 3_600_000 ? "soon" : "ok",
    text: `Срок: ${s}`,
    long: `До окончания срока рассмотрения по SLA осталось ${s}`,
  };
}
