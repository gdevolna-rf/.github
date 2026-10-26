"use client";
/** The viewer's open proposals for this spot with their statuses (SPT-08 «статус предложения»). */
import Link from "next/link";
import { Icon, StatusBadge } from "@/components/ui";
import { formatDate } from "@/lib/format";
import { routes } from "@/lib/routes";
import { useSpotViewer } from "./SpotViewer";

const FIELD_LABELS: Record<string, string> = {
  short_description: "краткое описание",
  description: "описание",
  difficulty: "уровень",
  bottom_type: "дно",
  break_type: "тип брейка",
  wave_character: "характер волн",
  wave_power: "мощность волн",
  season: "сезон",
  best_months: "лучшие месяцы",
  best_wind_directions: "ветер",
  best_swell_directions: "свелл",
  best_tide: "прилив",
  typical_conditions: "типичные условия",
  hazards: "опасности",
  hazard_notes: "безопасность",
  entry_exit: "вход и выход",
  access: "доступ",
  infrastructure: "инфраструктура",
  water_temp_note: "температура воды",
  seasonal_warning: "сезонное предупреждение",
};

export function SpotMyStatus() {
  const { pendingProposals } = useSpotViewer();
  if (!pendingProposals.length) return null;
  return (
    <div className="gv-spot-my-proposals" role="status">
      <Icon name="pencil" size={16} />
      <div>
        <b>Ваши предложения по этому споту</b>
        <ul>
          {pendingProposals.map((p) => (
            <li key={p.id}>
              <StatusBadge domain="proposal" status={p.status?.code} />{" "}
              <span>
                {formatDate(p.created_at, { style: "dayMonth" })}:{" "}
                {p.changed_fields.map((f) => FIELD_LABELS[f] ?? f).join(", ")}
              </span>
              {p.moderator_comment ? <small> — модератор: {p.moderator_comment}</small> : null}
            </li>
          ))}
        </ul>
        <Link href={routes.account.proposals}>Все мои предложения →</Link>
      </div>
    </div>
  );
}
