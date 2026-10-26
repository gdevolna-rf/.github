/**
 * Instructor cabinet API (TZ 8.2, 19, INS-01…12, ACC-15): own card, publication, gallery, certificates,
 * offers, private slots, unified schedule, students. Shapes: backend/apps/learning/serializers.py
 * (InstructorOwnSerializer, CertificateOwnSerializer, OfferSerializer, SessionManageSerializer,
 * ScheduleItemSerializer, MyStudentRowSerializer).
 */
import { api } from "./client";
import { isApiError } from "./errors";
import { listAll, type LearningOrg, type LearningSpot, type ManagedSession, type ScheduleItem, type SchedulePeriod, type StudentsPage } from "./learningCabinet";
import type { Decimal, IsoDateTime, Media, UUID } from "./types";

export type InstructorStatus = "draft" | "published" | "hidden";
export type CertificateState = "none" | "uploaded" | "verified";

export interface InstructorMediaItem {
  id: number;
  position: number;
  media: Media;
}

export interface PublishCheck {
  can_publish: boolean;
  /** field → Russian explanation (name, headline, region_slugs, formats, price_from, email) */
  missing: Record<string, string>;
}

export interface InstructorOwn {
  id: UUID;
  handle: string | null;
  display_name: string;
  first_name: string;
  last_name: string;
  avatar: Media | null;
  headline: string;
  regions: Array<{ slug: string; name: string }>;
  spots: LearningSpot[];
  surfing_since: number | null;
  teaching_since: number | null;
  riding_level: string;
  formats: string[];
  student_levels: string[];
  board_types: string[];
  languages: string[];
  price_from: Decimal | null;
  currency: string;
  certificate_status: CertificateState;
  rating_avg: Decimal;
  rating_count: number;
  schools: LearningOrg[];
  is_demo: boolean;
  effective_price_from: Decimal | null;
  about: string;
  fun_facts: string[];
  contact_note: string;
  allow_overlap: boolean;
  status: InstructorStatus;
  published_at: IsoDateTime | null;
  media: InstructorMediaItem[];
  publish_check: PublishCheck;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface InstructorProfileInput {
  headline?: string;
  about?: string;
  fun_facts?: string[];
  region_slugs?: string[];
  spot_slugs?: string[];
  surfing_since?: number | null;
  teaching_since?: number | null;
  riding_level?: string;
  formats?: string[];
  student_levels?: string[];
  board_types?: string[];
  languages?: string[];
  price_from?: string | null;
  currency?: string;
  contact_note?: string;
  allow_overlap?: boolean;
}

export type CertificateStatus = "uploaded" | "verified" | "rejected" | "revoked";

export interface CertificateOwn {
  id: UUID;
  title: string;
  issuer: string;
  status: CertificateStatus;
  issued_on: string | null;
  valid_until: string | null;
  is_expired: boolean;
  scan_available: boolean;
  allow_public_scan: boolean;
  moderator_comment: string;
  decided_at: IsoDateTime | null;
  document: Media;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface CertificateInput {
  title: string;
  issuer?: string;
  issued_on?: string | null;
  valid_until?: string | null;
  document_id: UUID;
  allow_public_scan?: boolean;
}

export type OfferFormat = "individual" | "group";

export interface Offer {
  id: UUID;
  title: string;
  description: string;
  format: OfferFormat;
  level: string;
  duration_min: number;
  price: Decimal;
  currency: string;
  capacity: number;
  spot: LearningSpot | null;
  equipment_included: boolean;
  equipment_note: string;
  rules: string;
  is_active: boolean;
  upcoming_sessions: number;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface OfferInput {
  title: string;
  description?: string;
  format: OfferFormat;
  level?: string;
  duration_min?: number;
  price: string;
  currency?: string;
  capacity?: number;
  spot_slug?: string | null;
  equipment_included?: boolean;
  equipment_note?: string;
  rules?: string;
  is_active?: boolean;
}

export interface PrivateSessionInput {
  offer_id: UUID;
  starts_at: string;
  ends_at?: string | null;
  title?: string;
  spot_slug?: string | null;
  notes?: string;
}

export interface PrivateSessionPatch {
  title?: string;
  spot_slug?: string | null;
  starts_at?: string;
  ends_at?: string;
  reschedule_reason?: string;
  notes?: string;
}

export interface ScheduleResponse {
  period: SchedulePeriod;
  results: ScheduleItem[];
}

export const instructorApi = {
  /** Own card or `null` when it was never created (404 instructor_profile_not_found). */
  profile: async (): Promise<InstructorOwn | null> => {
    try {
      return await api.get<InstructorOwn>("me/instructor");
    } catch (err) {
      if (isApiError(err) && err.isNotFound) return null;
      throw err;
    }
  },
  /** First save creates the card (PUT), later saves patch it. */
  save: (input: InstructorProfileInput, create: boolean) =>
    create ? api.put<InstructorOwn>("me/instructor", input) : api.patch<InstructorOwn>("me/instructor", input),
  publish: () => api.post<InstructorOwn>("me/instructor/publish"),
  unpublish: () => api.post<InstructorOwn>("me/instructor/unpublish"),
  media: {
    add: (mediaId: UUID) => api.post<InstructorMediaItem>("me/instructor/media", { media_id: mediaId }),
    reorder: (ids: number[]) => api.patch<InstructorMediaItem[]>("me/instructor/media", { ids }),
    remove: (itemId: number) => api.delete(`me/instructor/media/${itemId}`),
  },
  certificates: {
    list: () => api.get<CertificateOwn[]>("me/instructor/certificates"),
    upload: (body: CertificateInput) => api.post<CertificateOwn>("me/instructor/certificates", body),
    update: (id: UUID, body: { allow_public_scan: boolean }) => api.patch<CertificateOwn>(`me/instructor/certificates/${id}`, body),
    remove: (id: UUID) => api.delete(`me/instructor/certificates/${id}`),
    scanUrl: (id: UUID) => api.get<{ url: string; expires_in: number; content_type: string }>(`certificates/${id}/scan`),
  },
  offers: {
    list: () => listAll<Offer>("me/instructor/offers"),
    create: (body: OfferInput) => api.post<Offer>("me/instructor/offers", body),
    update: (id: UUID, body: Partial<OfferInput>) => api.patch<Offer>(`me/instructor/offers/${id}`, body),
    remove: (id: UUID) => api.delete(`me/instructor/offers/${id}`),
  },
  sessions: {
    create: (body: PrivateSessionInput) => api.post<ManagedSession>("me/instructor/sessions", body),
    update: (id: UUID, body: PrivateSessionPatch) => api.patch<ManagedSession>(`me/instructor/sessions/${id}`, body),
    remove: (id: UUID) => api.delete(`me/instructor/sessions/${id}`),
  },
  /** All sessions where I am the instructor — schools and private (INS-07, AT-06). */
  schedule: (q: { from: string; to: string; tz?: string; status?: string }) => api.get<ScheduleResponse>("me/schedule", { query: q }),
  students: (q: { q?: string; repeat?: boolean; page?: number; page_size?: number }) =>
    api.get<StudentsPage>("me/students", { query: { ...q, repeat: q.repeat ? "true" : undefined } }),
};

/** Query keys (domain "instructor-cabinet"). */
export const ik = {
  all: ["instructor-cabinet"] as const,
  profile: ["instructor-cabinet", "profile"] as const,
  certificates: ["instructor-cabinet", "certificates"] as const,
  offers: ["instructor-cabinet", "offers"] as const,
  scheduleAll: ["instructor-cabinet", "schedule"] as const,
  schedule: (from: string, to: string, tz: string) => ["instructor-cabinet", "schedule", from, to, tz] as const,
  students: (q: string, repeat: boolean, page: number) => ["instructor-cabinet", "students", q, repeat, page] as const,
};
