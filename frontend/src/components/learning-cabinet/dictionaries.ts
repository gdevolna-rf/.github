/**
 * Enum vocabularies of the learning cabinets (codes = backend choices). The shared statuses stay in
 * lib/labels.ts (STATUS.session, STATUS.booking, …); these are domain-specific option lists.
 */
import { RIDING_LEVEL_LABELS } from "@/lib/labels";
import type { MembershipRole } from "@/lib/api/types";

export interface Option<T extends string = string> {
  value: T;
  label: string;
}

const toOptions = <T extends string>(dict: Record<T, string>): Option<T>[] =>
  (Object.keys(dict) as T[]).map((value) => ({ value, label: dict[value] }));

/** learning.serializers.FORMAT_CHOICES (instructor card / school formats). */
export const LESSON_FORMAT_LABELS = {
  individual: "Индивидуально",
  pair: "Вдвоём",
  group: "Группа",
  kids: "Детские занятия",
} as const;
export const LESSON_FORMAT_OPTIONS = toOptions(LESSON_FORMAT_LABELS);

/** InstructorOffer.Format / SchoolProgram.format. */
export const OFFER_FORMAT_LABELS = { individual: "Индивидуально", group: "Группа" } as const;
export const OFFER_FORMAT_OPTIONS = toOptions(OFFER_FORMAT_LABELS);

/** accounts.UserProfile.Level — riding level and student levels. */
export const LEVEL_OPTIONS: Option[] = Object.entries(RIDING_LEVEL_LABELS).map(([value, label]) => ({ value, label }));

/** Student level wording for cards («для новичков»). */
export const STUDENT_LEVEL_LABELS: Record<string, string> = {
  beginner: "Новички",
  intermediate: "Средний уровень",
  advanced: "Продвинутые",
  pro: "Профи",
};

export const AGE_CATEGORY_LABELS = {
  all: "Все возрасты",
  kids: "Дети",
  teens: "Подростки",
  adults: "Взрослые",
} as const;
export const AGE_CATEGORY_OPTIONS = toOptions(AGE_CATEGORY_LABELS);

/** ISO 639 codes accepted by the API (^[a-z]{2,3}$). */
export const LANGUAGE_LABELS: Record<string, string> = {
  ru: "Русский",
  en: "Английский",
  de: "Немецкий",
  fr: "Французский",
  es: "Испанский",
  it: "Итальянский",
  zh: "Китайский",
  ja: "Японский",
  ko: "Корейский",
};
export const LANGUAGE_OPTIONS: Option[] = Object.entries(LANGUAGE_LABELS).map(([value, label]) => ({ value, label }));

export const CURRENCY_OPTIONS: Option[] = [
  { value: "RUB", label: "₽ — рубли" },
  { value: "USD", label: "$ — доллары" },
  { value: "EUR", label: "€ — евро" },
];

export const CANCEL_SIDE_LABELS: Record<string, string> = {
  customer: "Клиент",
  provider: "Исполнитель",
  system: "Система (истёк срок)",
};

/** Roles that a member with `role` may assign when inviting (server: OWNER_INVITABLE / MANAGER_INVITABLE). */
export const ROLE_DESCRIPTIONS: Record<MembershipRole, string> = {
  owner: "Все права, публикация и передача владения",
  manager: "Расписание, программы, команда (кроме менеджеров)",
  instructor: "Свои занятия, ученики и заметки",
  staff: "Просмотр расписания и аналитики",
};

export function labelOf(dict: Record<string, string>, code: string | null | undefined, fallback = ""): string {
  if (!code) return fallback;
  return dict[code] ?? fallback;
}

export function listLabels(dict: Record<string, string>, codes: string[] | null | undefined): string {
  return (codes ?? []).map((c) => dict[c]).filter(Boolean).join(", ");
}
