/**
 * The single vocabulary of statuses, actions and enum labels (SHO-05, ATX-28): every screen shows the same
 * Russian words and colours for the same server code. Never print a raw code (prototype bug «pending»).
 * Codes are the backend TextChoices (backend/apps/<app>/models.py).
 */
import type { CompassPoint, FavoriteTargetType, MembershipRole, OrganizationKind, PrimaryType, SpecialtyCode, StaffRole } from "./api/types";

/** Visual tone → CSS `.gv-status.tone-<tone>` (colours in tokens.css --st-*). */
export type Tone = "info" | "new" | "ok" | "done" | "muted" | "danger" | "verified";

export interface StatusDef {
  label: string;
  tone: Tone;
}

const s = (label: string, tone: Tone): StatusDef => ({ label, tone });

export const STATUS = {
  /** commerce.Inquiry (7.2) */
  inquiry: {
    new: s("Новое", "new"),
    in_progress: s("В работе", "info"),
    completed: s("Завершено", "done"),
    declined: s("Отказано", "danger"),
    cancelled: s("Отменено клиентом", "muted"),
  },
  /** commerce.Booking for lessons (7.3) */
  booking: {
    requested: s("Ожидает подтверждения", "new"),
    confirmed: s("Подтверждено", "ok"),
    in_progress: s("Идёт", "info"),
    completed: s("Завершено", "done"),
    declined: s("Отклонено", "danger"),
    cancelled: s("Отменено", "muted"),
    no_show: s("Неявка", "danger"),
  },
  /** commerce.Booking kind=rental: in_progress = «выдано», completed = «возвращено» */
  rentalBooking: {
    requested: s("Ожидает подтверждения", "new"),
    confirmed: s("Подтверждено", "ok"),
    in_progress: s("Выдано", "info"),
    completed: s("Возвращено", "done"),
    declined: s("Отклонено", "danger"),
    cancelled: s("Отменено", "muted"),
    no_show: s("Не забрали", "danger"),
  },
  /** commerce.InquiryMilestone (SHO-06) */
  milestone: {
    planned: s("Запланирован", "info"),
    done: s("Выполнен исполнителем", "ok"),
    confirmed: s("Подтверждён клиентом", "done"),
  },
  /** learning.LessonSession */
  session: {
    scheduled: s("Запланировано", "info"),
    in_progress: s("Идёт", "ok"),
    completed: s("Проведено", "done"),
    cancelled: s("Отменено", "muted"),
  },
  /** learning.WaitlistEntry */
  waitlist: {
    waiting: s("В очереди", "new"),
    offered: s("Предложено место", "info"),
    converted: s("Записан", "ok"),
    cancelled: s("Отменено", "muted"),
  },
  /** trust.Review */
  review: {
    pending: s("На модерации", "new"),
    published: s("Опубликован", "ok"),
    rejected: s("Отклонён", "danger"),
    hidden: s("Скрыт модератором", "muted"),
  },
  /** spots.SpotChangeRequest (7.4) */
  proposal: {
    submitted: s("На модерации", "new"),
    needs_info: s("Нужны уточнения", "new"),
    approved: s("Принято", "ok"),
    rejected: s("Отклонено", "danger"),
    withdrawn: s("Отозвано автором", "muted"),
  },
  /** learning.InstructorCertificate + derived "none" (INS-03, TRUST-03) */
  certificate: {
    none: s("Сертификат не указан", "muted"),
    uploaded: s("Сертификат загружен, на проверке", "info"),
    verified: s("Сертификат проверен", "verified"),
    rejected: s("Сертификат отклонён", "danger"),
    revoked: s("Сертификат отозван", "muted"),
  },
  /** organizations.Organization */
  organization: {
    draft: s("Черновик", "muted"),
    pending_review: s("На проверке", "new"),
    published: s("Опубликована", "ok"),
    suspended: s("Ограничена модератором", "danger"),
    archived: s("В архиве", "muted"),
  },
  /** organizations.Membership */
  membership: {
    active: s("Активно", "ok"),
    revoked: s("Доступ отозван", "danger"),
    left: s("Вышел", "muted"),
  },
  /** organizations.OrganizationInvite */
  invite: {
    pending: s("Ожидает ответа", "new"),
    accepted: s("Принято", "ok"),
    declined: s("Отклонено", "muted"),
    revoked: s("Отозвано", "muted"),
    expired: s("Истекло", "muted"),
  },
  /** boards.BoardVariant.availability — «Нет в наличии» is red, not amber (prototype bug #3) */
  availability: {
    in_stock: s("В наличии", "ok"),
    made_to_order: s("Под заказ", "new"),
    out_of_stock: s("Нет в наличии", "danger"),
  },
  /** boards.BoardModel / spots.Spot / learning.InstructorProfile publication */
  publication: {
    draft: s("Черновик", "muted"),
    published: s("Опубликовано", "ok"),
    hidden: s("Скрыто модератором", "danger"),
    archived: s("В архиве", "muted"),
    closed: s("Закрыто", "muted"),
  },
  /** inventory.InventoryItem */
  inventory: {
    available: s("Доступен", "ok"),
    reserved: s("Зарезервирован", "new"),
    sold: s("Продан", "done"),
    maintenance: s("На обслуживании", "info"),
    retired: s("Списан", "muted"),
  },
  /** mediafiles.MediaAsset */
  media: {
    pending: s("Ожидает загрузки", "new"),
    processing: s("Обрабатывается", "info"),
    ready: s("Готово", "ok"),
    rejected: s("Отклонено", "danger"),
    deleted: s("Удалено", "muted"),
  },
  /** trust.Complaint */
  complaint: {
    open: s("Открыта", "new"),
    resolved: s("Решена", "ok"),
    dismissed: s("Отклонена", "muted"),
  },
  /** trust.ModerationCase */
  moderationCase: {
    open: s("Открыт", "new"),
    in_review: s("В работе", "info"),
    resolved: s("Решён", "done"),
  },
  /** club.EventRegistration */
  eventRegistration: {
    registered: s("Вы записаны", "ok"),
    waitlist: s("Лист ожидания", "new"),
    cancelled: s("Отменено", "muted"),
  },
  /** club.ClubEvent */
  event: {
    draft: s("Черновик", "muted"),
    published: s("Открыта запись", "ok"),
    cancelled: s("Отменено", "danger"),
    completed: s("Прошло", "done"),
  },
} as const satisfies Record<string, Record<string, StatusDef>>;

export type StatusDomain = keyof typeof STATUS;

/**
 * Enum values come either as plain codes ("beginner") or as choice objects ({"code": "beginner",
 * "label": "Для новичков"}) depending on the serializer. Always read them through these helpers.
 */
export type Choice<T extends string = string> = T | { code: T; label?: string; [key: string]: unknown };

export function choiceCode<T extends string = string>(value: Choice<T> | null | undefined): T | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "string") return value;
  return typeof value === "object" && "code" in value ? (value.code as T) : null;
}

/** Server label first, then our dictionary, else "" (never the raw code). */
export function choiceLabel(value: Choice | null | undefined, dictionary?: Record<string, string>): string {
  if (value && typeof value === "object" && typeof value.label === "string" && value.label) return value.label;
  const code = choiceCode(value);
  if (!code) return "";
  return dictionary?.[code] ?? "";
}

const UNKNOWN: StatusDef = { label: "Статус уточняется", tone: "muted" };

export function getStatus(domain: StatusDomain, status: Choice | null | undefined): StatusDef {
  const code = choiceCode(status);
  if (!code) return UNKNOWN;
  const def = (STATUS[domain] as Record<string, StatusDef>)[code];
  if (def) return def;
  const serverLabel = choiceLabel(status);
  return serverLabel ? { label: serverLabel, tone: "muted" } : UNKNOWN;
}

export const statusLabel = (domain: StatusDomain, status: Choice | null | undefined) => getStatus(domain, status).label;
export const statusTone = (domain: StatusDomain, status: Choice | null | undefined) => getStatus(domain, status).tone;

/** Action buttons — same verbs everywhere (ATX-28 «В работе / Завершить / Отказать»). */
export const INQUIRY_ACTIONS = {
  accept: "Взять в работу",
  decline: "Отказать",
  complete: "Завершить",
  cancel: "Отменить обращение",
} as const;

export const BOOKING_ACTIONS = {
  confirm: "Подтвердить",
  decline: "Отклонить",
  start: "Начать занятие",
  complete: "Завершить",
  no_show: "Отметить неявку",
  cancel: "Отменить бронирование",
} as const;

export const RENTAL_BOOKING_ACTIONS = {
  ...BOOKING_ACTIONS,
  start: "Выдать",
  complete: "Принять возврат",
} as const;

/* ---------------- enums ---------------- */

export const SPECIALTY_LABELS: Record<SpecialtyCode, string> = {
  surfer: "Сёрфер",
  instructor: "Сёрф-инструктор",
  shaper: "Шейпер",
  rental: "Прокат",
};

export const SPECIALTY_DESCRIPTIONS: Record<SpecialtyCode, string> = {
  surfer: "Дневник катания, любимые споты и клубная активность",
  instructor: "Календарь занятий, ученики, заявки и отзывы",
  shaper: "Мастерская, доски, заявки, аренда и аналитика",
  rental: "Снаряжение, доступность и заявки на аренду",
};

export const PRIMARY_TYPE_LABELS: Record<PrimaryType, string> = {
  surfer: "Сёрфер",
  instructor: "Инструктор",
  shaper: "Шейпер",
  school: "Сёрф-школа",
  rental: "Прокат",
};

export const STAFF_ROLE_LABELS: Record<StaffRole, string> = {
  moderator: "Модератор",
  admin: "Администратор",
  organizer: "Организатор клуба",
};

export const MEMBERSHIP_ROLE_LABELS: Record<MembershipRole, string> = {
  owner: "Владелец",
  manager: "Менеджер",
  instructor: "Инструктор",
  staff: "Сотрудник",
};

export const ORGANIZATION_KIND_LABELS: Record<OrganizationKind, string> = {
  school: "Сёрф-школа",
  workshop: "Мастерская шейпера",
  rental: "Прокат",
};

export const INQUIRY_KIND_LABELS: Record<string, string> = {
  board_purchase: "Покупка доски",
  custom_order: "Индивидуальное изготовление",
  repair: "Ремонт",
  lesson: "Занятие с инструктором",
  program: "Программа школы",
  rental: "Аренда",
  merch: "Фирменные товары",
  general: "Вопрос",
};

export const FAVORITE_TARGET_LABELS: Record<FavoriteTargetType, string> = {
  spot: "Спот",
  instructor: "Инструктор",
  organization: "Школа, мастерская или прокат",
  board_model: "Модель доски",
  inventory_item: "Снаряжение",
};

export const SPOT_DIFFICULTY_LABELS: Record<string, string> = {
  beginner: "Для новичков",
  intermediate: "Средний",
  advanced: "Продвинутый",
  expert: "Эксперт",
};

export const SPOT_BOTTOM_LABELS: Record<string, string> = {
  sand: "Песок",
  rock: "Камни",
  reef: "Риф",
  pebble: "Галька",
  mixed: "Смешанное",
};

export const SPOT_BREAK_LABELS: Record<string, string> = {
  beach: "Бич-брейк",
  reef: "Риф-брейк",
  point: "Пойнт-брейк",
  river_mouth: "Устье реки",
  jetty: "У волнореза",
};

export const RIDING_LEVEL_LABELS: Record<string, string> = {
  beginner: "Новичок",
  intermediate: "Средний",
  advanced: "Продвинутый",
  pro: "Профи",
};

export const INVENTORY_KIND_LABELS: Record<string, string> = {
  board: "Доска",
  wetsuit: "Гидрокостюм",
  sup: "SUP",
  fins: "Плавники",
  accessory: "Аксессуар",
  other: "Другое",
};

export const CONDITION_LABELS: Record<string, string> = {
  new: "Новое",
  excellent: "Отличное",
  good: "Хорошее",
  fair: "Рабочее",
};

export const NOTIFICATION_KIND_LABELS: Record<string, string> = {
  message_new: "Новое сообщение",
  inquiry_new: "Новое обращение",
  inquiry_status: "Статус обращения",
  booking_new: "Новая бронь",
  booking_status: "Статус брони",
  lesson_assigned: "Назначено занятие",
  moderation_decision: "Решение модератора",
  review_published: "Отзыв опубликован",
  certificate_decision: "Проверка сертификата",
  invite: "Приглашение в организацию",
  membership: "Изменение доступа",
  event_reminder: "Напоминание о событии",
  lesson_reminder: "Напоминание о занятии",
  birthday: "Поздравление",
  complaint: "Жалоба",
  system: "Системное",
};

/** 16-point compass (spots.choices.COMPASS): code → name, short label, azimuth. */
export const COMPASS: Record<CompassPoint, { name: string; short: string; deg: number }> = {
  N: { name: "Север", short: "С", deg: 0 },
  NNE: { name: "Северо-северо-восток", short: "ССВ", deg: 22.5 },
  NE: { name: "Северо-восток", short: "СВ", deg: 45 },
  ENE: { name: "Восток-северо-восток", short: "ВСВ", deg: 67.5 },
  E: { name: "Восток", short: "В", deg: 90 },
  ESE: { name: "Восток-юго-восток", short: "ВЮВ", deg: 112.5 },
  SE: { name: "Юго-восток", short: "ЮВ", deg: 135 },
  SSE: { name: "Юго-юго-восток", short: "ЮЮВ", deg: 157.5 },
  S: { name: "Юг", short: "Ю", deg: 180 },
  SSW: { name: "Юго-юго-запад", short: "ЮЮЗ", deg: 202.5 },
  SW: { name: "Юго-запад", short: "ЮЗ", deg: 225 },
  WSW: { name: "Запад-юго-запад", short: "ЗЮЗ", deg: 247.5 },
  W: { name: "Запад", short: "З", deg: 270 },
  WNW: { name: "Запад-северо-запад", short: "ЗСЗ", deg: 292.5 },
  NW: { name: "Северо-запад", short: "СЗ", deg: 315 },
  NNW: { name: "Северо-северо-запад", short: "ССЗ", deg: 337.5 },
};

export const COMPASS_POINTS = Object.keys(COMPASS) as CompassPoint[];

export function isCompassPoint(value: unknown): value is CompassPoint {
  return typeof value === "string" && value in COMPASS;
}

/** ["NW", {code:"N", …}] → ["NW", "N"] (unknown codes dropped). */
export function compassCodes(values: ReadonlyArray<Choice | null | undefined> | null | undefined): CompassPoint[] {
  const out: CompassPoint[] = [];
  for (const v of values ?? []) {
    const code = choiceCode(v);
    if (isCompassPoint(code) && !out.includes(code)) out.push(code);
  }
  return out;
}
