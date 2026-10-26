/**
 * Shared learning API for the instructor and school cabinets (fe-instructor domain):
 * lesson sessions + actions (assign / reschedule / cancel / complete), student notes (SCH-10),
 * dashboard metrics (GET me/metrics, MET-04/05), reference lists (regions, spots, board types).
 * Shapes: backend/apps/learning/serializers.py, backend/apps/analytics/services/metrics.py.
 */
import { api } from "./client";
import type { Decimal, IsoDateTime, Media, Paginated, PublicAccount, UUID } from "./types";

/* ---------------- reference lists ---------------- */

/** GET /regions (not paginated). */
export interface RegionOption {
  id: number;
  slug: string;
  name: string;
  timezone: string;
  spots_count?: number;
}

/** GET /spots item (subset used by the cabinets). */
export interface SpotOption {
  id: UUID;
  slug: string;
  name: string;
  region: { id?: number; slug: string; name: string } | null;
}

/** GET /board-types. */
export interface BoardTypeOption {
  id: number;
  code: string;
  name: string;
  is_custom: boolean;
  sort_order?: number;
}

/* ---------------- sessions ---------------- */

export interface LearningSpot {
  id: UUID;
  slug: string;
  name: string;
  region: { slug: string; name: string } | null;
}

export interface LearningOrg {
  id: UUID;
  slug: string;
  name: string;
  kind: string;
}

export interface SessionInstructor extends PublicAccount {
  has_public_profile?: boolean;
}

export type SessionStatus = "scheduled" | "in_progress" | "completed" | "cancelled";

export interface SessionProgramBrief {
  id: UUID;
  title: string;
  level: string;
  age_category: string;
  format: string;
  duration_min: number;
  sessions_count: number;
}

export interface SessionOfferBrief {
  id: UUID;
  title: string;
  format: string;
  level: string;
  duration_min: number;
}

/** SessionPublicSerializer — times are ISO with offset; `timezone` is the spot/region IANA zone. */
export interface LessonSession {
  id: UUID;
  kind: "school" | "private";
  title: string;
  status: SessionStatus;
  starts_at: IsoDateTime;
  ends_at: IsoDateTime;
  timezone: string;
  capacity: number;
  seats_taken: number;
  free_seats: number;
  is_full: boolean;
  price: Decimal | null;
  currency: string;
  program: SessionProgramBrief | null;
  offer: SessionOfferBrief | null;
  organization: LearningOrg | null;
  instructor: SessionInstructor | null;
  spot: LearningSpot | null;
  reschedule_reason: string;
  cancel_reason: string;
}

export interface BookingsSummary {
  requested: number;
  confirmed: number;
  in_progress: number;
  completed: number;
  no_show: number;
  cancelled: number;
  declined: number;
}

/** SessionManageSerializer (school sessions, private slots). */
export interface ManagedSession extends LessonSession {
  notes: string;
  allow_overlap: boolean;
  bookings_summary: BookingsSummary;
  waitlist_count: number;
  cancelled_at: IsoDateTime | null;
  completed_at: IsoDateTime | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

/** Participant of a session in GET me/schedule (confirmed / in progress / completed / no-show bookings). */
export interface SessionParticipant {
  booking_id: UUID;
  status: string;
  seats: number;
  name: string;
  participant_is_minor: boolean;
  customer: PublicAccount;
}

/** ScheduleItemSerializer — one row of the instructor's unified schedule (INS-07, AT-06). */
export interface ScheduleItem extends LessonSession {
  participants: SessionParticipant[];
  requested_count: number;
  can_manage: boolean;
  notes: string;
}

export interface SchedulePeriod {
  from: string;
  to: string;
  timezone: string;
  starts_at: IsoDateTime;
  ends_at: IsoDateTime;
}

export interface SessionCompleteResult {
  session: ManagedSession;
  completed_booking_ids: UUID[];
  no_show_booking_ids: UUID[];
}

/* ---------------- students & notes ---------------- */

export interface SessionBrief {
  id: UUID;
  title: string;
  starts_at: IsoDateTime;
  ends_at: IsoDateTime;
  status: SessionStatus;
}

export interface StudentNote {
  id: UUID;
  student: PublicAccount;
  author: PublicAccount;
  organization: LearningOrg | null;
  session: SessionBrief | null;
  level: string;
  comment: string;
  visible_to_student: boolean;
  can_edit: boolean;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface StudentRow {
  student: PublicAccount | null;
  bookings_count: number;
  completed_count: number;
  no_show_count: number;
  attendance_pct: number | null;
  is_repeat: boolean;
  first_session_at: IsoDateTime | null;
  last_session_at: IsoDateTime | null;
  next_session_at: IsoDateTime | null;
  last_session: SessionBrief | null;
  /** instructor list only */
  notes?: StudentNote[];
  /** school list only */
  notes_count?: number;
}

export interface StudentsSummary {
  unique_students: number;
  repeat_students: number;
  repeat_students_pct: number | null;
  students_with_bookings: number;
}

export interface StudentsPage extends Paginated<StudentRow> {
  summary: StudentsSummary;
}

export interface StudentNoteInput {
  student_id: UUID;
  organization_id?: UUID | null;
  session_id?: UUID | null;
  level?: string;
  comment: string;
  visible_to_student?: boolean;
}

/* ---------------- metrics ---------------- */

export type MetricUnit = "count" | "percent" | "money" | "rating" | "days" | "minutes";

export interface DashboardMetric {
  key: string;
  label: string;
  /** int | float | decimal string (money) | null (no data for the formula) */
  value: number | string | null;
  unit: MetricUnit;
  formula: string;
  currency: string | null;
}

export interface MetricsResponse {
  scope: string;
  period: SchedulePeriod;
  rule_version: number;
  generated_at: IsoDateTime;
  subject: Record<string, unknown>;
  metrics: DashboardMetric[];
  breakdowns: Record<string, unknown>;
}

export interface MetricsQuery {
  scope: "instructor" | "school";
  organization_id?: UUID;
  from?: string;
  to?: string;
  tz?: string;
}

/* ---------------- helpers ---------------- */

/** Walks DRF pagination (`next` links) and returns all rows (bounded by maxPages × 100). */
export async function listAll<T>(path: string, query: Record<string, string | number | boolean | null | undefined> = {}, maxPages = 10): Promise<T[]> {
  const out: T[] = [];
  let page = await api.get<Paginated<T> | T[]>(path, { query: { page_size: 100, ...query } });
  for (let n = 0; ; n++) {
    if (Array.isArray(page)) return [...out, ...page];
    out.push(...page.results);
    if (!page.next || n + 1 >= maxPages) return out;
    page = await api.get<Paginated<T>>(page.next);
  }
}

export const refsApi = {
  regions: () => api.get<RegionOption[]>("regions"),
  spots: (region?: string) => listAll<SpotOption>("spots", { region }),
  boardTypes: () => api.get<BoardTypeOption[]>("board-types"),
};

export const sessionsApi = {
  assign: (id: UUID, instructorId: UUID | null) => api.post<ManagedSession>(`sessions/${id}/assign`, { instructor_id: instructorId }),
  reschedule: (id: UUID, body: { starts_at: string; ends_at?: string; reason?: string }) =>
    api.post<ManagedSession>(`sessions/${id}/reschedule`, body),
  cancel: (id: UUID, reason: string) => api.post<ManagedSession>(`sessions/${id}/cancel`, { reason }),
  complete: (id: UUID, noShowBookingIds: UUID[]) =>
    api.post<SessionCompleteResult>(`sessions/${id}/complete`, { no_show_booking_ids: noShowBookingIds }),
};

export const notesApi = {
  list: (q: { student?: UUID; organization?: UUID; session?: UUID }) => listAll<StudentNote>("student-notes", q),
  create: (body: StudentNoteInput) => api.post<StudentNote>("student-notes", body),
  update: (id: UUID, body: { level?: string; comment?: string; visible_to_student?: boolean }) =>
    api.patch<StudentNote>(`student-notes/${id}`, body),
  remove: (id: UUID) => api.delete(`student-notes/${id}`),
};

export const metricsApi = {
  get: (q: MetricsQuery) => api.get<MetricsResponse>("me/metrics", { query: { ...q } }),
};

/**
 * Query keys of the learning cabinets (kept here instead of the shared lib/api/keys.ts — fe-instructor owns
 * only its domain files). Reference lists start with "public" so logout keeps them (resetPrivateData).
 */
export const lk = {
  regions: ["public", "regions"] as const,
  spots: (region?: string) => ["public", "spots", "all", region ?? "all"] as const,
  boardTypes: ["public", "board-types"] as const,
  metrics: (q: MetricsQuery) => ["metrics", q.scope, q.organization_id ?? "me", q.from ?? "", q.to ?? ""] as const,
  notes: (q: { student?: UUID; organization?: UUID }) => ["student-notes", q.student ?? "all", q.organization ?? "none"] as const,
  notesAll: ["student-notes"] as const,
};

export type { Media };
