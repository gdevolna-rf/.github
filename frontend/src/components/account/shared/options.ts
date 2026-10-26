/** Option lists for the account forms (codes = backend values; labels in Russian, never raw codes). */
import type { TagOption } from "./TagPicker";

/** boards.BoardType standard codes (preferred_board_types stores codes). */
export const BOARD_TYPE_OPTIONS: TagOption[] = [
  { value: "longboard", label: "Лонгборд" },
  { value: "midlength", label: "Мидлленг" },
  { value: "funboard", label: "Фанборд" },
  { value: "shortboard", label: "Шортборд" },
  { value: "fish", label: "Фиш" },
  { value: "egg", label: "Эгг" },
  { value: "hybrid", label: "Гибрид" },
  { value: "gun", label: "Ган" },
  { value: "softtop", label: "Софттоп" },
  { value: "sup", label: "SUP" },
];

/** Prototype interests (CABINET_SCREENS §3.2) — stored as text. */
export const INTEREST_OPTIONS: TagOption[] = [
  "Сёрфинг",
  "Кемпинг",
  "Сноуборд",
  "Путешествия",
  "Фотография",
  "Походы",
  "Шейпинг",
  "Йога",
  "Экология",
  "Кофе у океана",
].map((v) => ({ value: v, label: v }));

/** ISO 639-1 codes (languages ≤ 8 chars, lower-case on the server). */
export const LANGUAGE_OPTIONS: TagOption[] = [
  { value: "ru", label: "Русский" },
  { value: "en", label: "English" },
  { value: "de", label: "Deutsch" },
  { value: "fr", label: "Français" },
  { value: "es", label: "Español" },
  { value: "it", label: "Italiano" },
  { value: "pt", label: "Português" },
  { value: "zh", label: "中文" },
  { value: "ja", label: "日本語" },
  { value: "ko", label: "한국어" },
];

export const CONSENT_LABELS: Record<string, string> = {
  terms: "Пользовательское соглашение",
  privacy: "Обработка персональных данных",
  gg_surfer: "Участие в GG Surfer",
  birthday_greetings: "Поздравления с днём рождения",
  geolocation: "Использование геолокации",
  marketing: "Рассылки и новости проекта",
  guardian: "Согласие законного представителя",
};

export const EXPORT_STATUS: Record<string, { label: string; tone: "new" | "ok" | "danger" }> = {
  pending: { label: "Готовится", tone: "new" },
  ready: { label: "Готово", tone: "ok" },
  failed: { label: "Ошибка", tone: "danger" },
};

export const ROLE_FILTER_LABELS: Record<string, string> = {
  customer: "Клиент",
  instructor: "Инструктор",
  shaper: "Шейпер",
  school: "Школа",
  rental: "Прокат",
};

export const FAVORITE_GROUPS: Array<{ id: string; title: string; empty: string }> = [
  { id: "spot", title: "Споты", empty: "Сохраняйте споты с карты и из каталога." },
  { id: "instructor", title: "Инструкторы", empty: "Сохраняйте инструкторов из каталога." },
  { id: "school", title: "Сёрф-школы", empty: "Сохраняйте школы из каталога." },
  { id: "shaper", title: "Шейперы и мастерские", empty: "Сохраняйте мастерские из каталога шейперов." },
  { id: "board_model", title: "Доски", empty: "Сохраняйте модели досок из каталога." },
  { id: "equipment", title: "Снаряжение и прокат", empty: "Сохраняйте снаряжение и прокаты из раздела «Аренда»." },
];
