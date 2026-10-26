/**
 * Learning domain (instructors, schools, lesson sessions, bookings of lessons).
 * Shapes: backend/apps/learning/serializers.py (InstructorCardSerializer, InstructorDetailSerializer,
 * SessionDetailSerializer), backend/apps/organizations (public school card), apps/commerce (BookingCreateSerializer).
 * Server Components fetch the public parts with serverFetch(); client islands use these functions.
 */
import { api } from "./client";
import type { Decimal, IsoDateTime, Media, Paginated, PublicAccount, UUID } from "./types";

export interface LearningRegion {
  id?: number;
  slug: string;
  name: string;
  timezone?: string;
}

export interface LearningSpot {
  id: UUID;
  slug: string;
  name: string;
  region?: LearningRegion | null;
}

export interface LearningOrgRef {
  id: UUID;
  slug: string;
  name: string;
  kind: string;
}

export type CertificateStatusCode = "none" | "uploaded" | "verified";

/** GET /instructors — catalogue card (INS-01, INS-03). */
export interface InstructorCard {
  id: UUID;
  handle: string;
  display_name: string;
  first_name: string;
  last_name: string;
  avatar: Media | null;
  headline: string;
  regions: LearningRegion[];
  spots: LearningSpot[];
  surfing_since: number | null;
  teaching_since: number | null;
  riding_level: string | null;
  formats: string[];
  student_levels: string[];
  board_types: string[];
  languages: string[];
  price_from: Decimal | null;
  currency: string;
  certificate_status: CertificateStatusCode;
  rating_avg: Decimal;
  rating_count: number;
  schools: LearningOrgRef[];
  is_demo?: boolean;
}

export interface InstructorOffer {
  id: UUID;
  title: string;
  description: string;
  format: string;
  level: string;
  duration_min: number;
  price: Decimal;
  currency: string;
  capacity: number;
  spot: LearningSpot | null;
  equipment_included: boolean;
  equipment_note: string;
  rules: string;
}

export interface InstructorCertificate {
  id: UUID;
  title: string;
  issuer: string;
  status: "uploaded" | "verified" | string;
  issued_on: string | null;
  valid_until: string | null;
  is_expired: boolean;
  scan_available: boolean;
}

export interface ProgramBrief {
  id: UUID;
  title: string;
  level: string;
  age_category: string;
  format: string;
  duration_min: number;
  sessions_count: number;
}

export interface OfferBrief {
  id: UUID;
  title: string;
  format: string;
  level: string;
  duration_min: number;
}

export interface SessionInstructor extends PublicAccount {
  has_public_profile?: boolean;
}

/** GET /sessions/{id} and items of `upcoming_slots` (SCH-05/08, ATX-14). */
export interface LessonSession {
  id: UUID;
  kind: "school" | "private";
  title: string;
  status: string;
  starts_at: IsoDateTime;
  ends_at: IsoDateTime;
  timezone: string;
  capacity: number;
  seats_taken: number;
  free_seats: number;
  is_full: boolean;
  price: Decimal | null;
  currency: string;
  program: ProgramBrief | null;
  offer: OfferBrief | null;
  organization: LearningOrgRef | null;
  instructor: SessionInstructor | null;
  spot: LearningSpot | null;
  reschedule_reason: string;
  cancel_reason: string;
  my_waitlist?: { id: UUID; status: string; position: number | null; created_at: IsoDateTime } | null;
  waitlist_count?: number;
}

/** GET /instructors/{handle} (INS-01/02). Old handle → `{redirect: "<new>"}`. */
export interface InstructorDetail extends InstructorCard {
  about: string;
  fun_facts: string[];
  contact_note: string;
  media: Array<{ id: UUID | number; position: number; media: Media }>;
  offers: InstructorOffer[];
  upcoming_slots: LessonSession[];
  certificates: InstructorCertificate[];
  published_at: IsoDateTime | null;
}

export interface InstructorRedirect {
  redirect: string;
}

/** GET /organizations?kind=school — catalogue card. */
export interface SchoolCard {
  id: UUID;
  slug: string;
  kind: string;
  name: string;
  short_description: string;
  region: LearningRegion | null;
  city: string;
  logo: Media | null;
  cover: Media | null;
  rating_avg: Decimal;
  rating_count: number;
  price_from: Decimal | null;
  currency: string;
  formats: string[];
  languages: string[];
  verification_status: string;
  published_at: IsoDateTime | null;
  is_demo?: boolean;
}

export interface SchoolProgram {
  id: UUID;
  title: string;
  description: string;
  level: string;
  age_category: string;
  format: string;
  duration_min: number;
  sessions_count: number;
  price: Decimal | null;
  currency: string;
  max_group_size: number | null;
  equipment_included: boolean;
}

export interface SchoolUpcomingSession {
  id: UUID;
  title: string;
  program_id: UUID | null;
  starts_at: IsoDateTime;
  ends_at: IsoDateTime;
  capacity: number;
  free_seats: number;
  price: Decimal | null;
  currency: string;
  status: string;
  spot: { id: UUID; slug: string; name: string } | null;
  instructor: PublicAccount | null;
  timezone?: string;
}

export interface SchoolTeamMember {
  account: PublicAccount;
  role: string;
  title: string;
  instructor_profile: { id: UUID; handle: string } | null;
}

/** GET /organizations/{slug} for a school (SCH-02). */
export interface SchoolDetail extends SchoolCard {
  description: string;
  address: string;
  website: string;
  social_links: Record<string, string>;
  gallery: Media[] | Array<{ id: UUID | number; media: Media }>;
  spots: LearningSpot[];
  team: SchoolTeamMember[];
  programs: SchoolProgram[];
  upcoming_sessions: SchoolUpcomingSession[];
  viewer_role: string | null;
}

/* ---------------- dictionaries (labels for codes) ---------------- */

export const LESSON_FORMAT_LABELS: Record<string, string> = {
  individual: "Индивидуально",
  pair: "Вдвоём",
  group: "Группа",
  kids: "Детские занятия",
};

export const STUDENT_LEVEL_LABELS: Record<string, string> = {
  beginner: "Новичок",
  intermediate: "Средний",
  advanced: "Продвинутый",
  pro: "Профи",
};

export const AGE_CATEGORY_LABELS: Record<string, string> = {
  kids: "Дети",
  teens: "Подростки",
  adults: "Взрослые",
  all: "Все возрасты",
};

export const BOARD_TYPE_LABELS: Record<string, string> = {
  shortboard: "Шортборд",
  longboard: "Лонгборд",
  funboard: "Фанборд",
  fish: "Фиш",
  softboard: "Софтборд",
  midlength: "Мидленг",
  gun: "Ган",
  sup: "SUP",
  hybrid: "Гибрид",
};

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

export const labelOf = (dict: Record<string, string>, code: string | null | undefined): string =>
  code ? (dict[code] ?? code) : "";

/* ---------------- client API ---------------- */

export interface LessonBookingInput {
  lesson_session_id: UUID;
  seats?: number;
  participant_name?: string;
  participant_is_minor?: boolean;
  guardian_consent?: boolean;
  customer_note?: string;
}

export interface CreatedBooking {
  id: UUID;
  status: string | { code: string; label?: string };
  [key: string]: unknown;
}

export const learningApi = {
  instructors: (query: Record<string, string | number | undefined>) =>
    api.get<Paginated<InstructorCard>>("instructors", { query }),
  session: (id: string) => api.get<LessonSession>(`sessions/${encodeURIComponent(id)}`),
  /** POST /bookings — Idempotency-Key is mandatory (one per user attempt). */
  bookLesson: (body: LessonBookingInput, idempotencyKey: string) =>
    api.post<CreatedBooking>("bookings", body, { idempotencyKey }),
  joinWaitlist: (sessionId: string) => api.post<unknown>(`sessions/${encodeURIComponent(sessionId)}/waitlist`, {}),
  leaveWaitlist: (sessionId: string) => api.delete(`sessions/${encodeURIComponent(sessionId)}/waitlist`),
};

export const learningKeys = {
  all: ["learning"] as const,
  session: (id: string) => ["learning", "session", id] as const,
};
