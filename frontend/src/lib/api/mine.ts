/**
 * «Моё» in the account: my spot proposals (7.4, SPT-07/08), my reviews (7.5), complaints I filed and decisions about
 * my content with appeals (TRUST-07), organization invites (5.3, ACC-11) and the GG Surfer riding diary
 * (COM-04/06, MET-06). Owner-only endpoints; the server filters by the current account (IDOR).
 * Query keys: `mineKeys` (first element = domain), invites reuse the shared `qk.myInvites`.
 */
import { api } from "./client";
import { qk } from "./keys";
import type { ChoiceValue, IsoDate, IsoDateTime, Media, MembershipRole, OrganizationKind, Paginated, PublicAccount, UUID } from "./types";

export const mineKeys = {
  proposals: (status?: string) => ["me", "proposals", status ?? "all"] as const,
  proposalsAll: ["me", "proposals"] as const,
  reviews: (status?: string) => ["me", "reviews", status ?? "all"] as const,
  reviewsAll: ["me", "reviews"] as const,
  complaints: (box: "filed" | "against") => ["me", "complaints", box] as const,
  complaintsAll: ["me", "complaints"] as const,
  invites: qk.myInvites,
  invite: (token: string) => ["me", "invites", "token", token] as const,
  diary: ["me", "diary"] as const,
  diaryList: (page: number) => ["me", "diary", "list", page] as const,
  diaryStats: ["me", "diary", "stats"] as const,
  spotDictionaries: ["public", "spots", "dictionaries"] as const,
  spotOptions: ["public", "spots", "options"] as const,
};

/* ---------------- proposals ---------------- */

/** spots.ProposalChangeSerializer */
export interface ProposalChange {
  field: string;
  label: string;
  kind: string;
  old: unknown;
  new: unknown;
  old_display: string;
  new_display: string;
}

export interface MyProposal {
  id: UUID;
  spot: { id: UUID; slug: string; name: string };
  status: ChoiceValue;
  changes: ProposalChange[];
  comment: string;
  source: string;
  evidence: Media[];
  moderator_comment: string;
  decided_at: IsoDateTime | null;
  is_reverted: boolean;
  reverted_at: IsoDateTime | null;
  can_edit: boolean;
  can_withdraw: boolean;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface ProposalUpdate {
  changes?: Record<string, unknown>;
  comment?: string;
  source?: string;
  evidence_ids?: string[];
}

export interface SpotDictionaries {
  difficulty: Array<{ code: string; label: string }>;
  bottom_type: Array<{ code: string; label: string }>;
  break_type: Array<{ code: string; label: string }>;
  location_precision: Array<{ code: string; label: string }>;
  compass_points: Array<{ code: string; label: string; short: string; degrees: number }>;
  months: Array<{ code: number; label: string }>;
  hazards: Array<{ code: string; label: string }>;
  infrastructure_types: Array<{ code: string; label: string }>;
  editable_fields: Array<{ field: string; label: string; kind: string; max_length: number | null }>;
}

/* ---------------- reviews ---------------- */

export interface MyReview {
  id: UUID;
  target_type: string;
  target: { type: string; id: UUID; name: string; link: string };
  rating: number;
  text: string;
  status: ChoiceValue;
  context_label: string;
  photos: Media[];
  has_pending_revision: boolean;
  pending_rating: number | null;
  pending_text: string;
  pending_photos: Media[];
  moderation_note: string;
  moderated_at: IsoDateTime | null;
  published_at: IsoDateTime | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

/* ---------------- complaints ---------------- */

export interface MyComplaint {
  id: UUID;
  target_type: ChoiceValue;
  target_id: string;
  reason: ChoiceValue;
  text: string;
  status: ChoiceValue;
  action_taken: ChoiceValue;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface ComplaintAgainstMe {
  id: UUID;
  target_type: ChoiceValue;
  target_id: string;
  reason: ChoiceValue;
  status: ChoiceValue;
  action_taken: ChoiceValue;
  appeal_text: string;
  appealed_at: IsoDateTime | null;
  can_appeal: boolean;
  updated_at: IsoDateTime;
}

/* ---------------- invites ---------------- */

export interface MyInvite {
  id: UUID;
  token: string;
  organization: { id: UUID; slug: string; name: string; kind: OrganizationKind | string; status: string; logo: Media | null };
  role: MembershipRole | string;
  status: string;
  message: string;
  invited_by: PublicAccount | null;
  expires_at: IsoDateTime;
  created_at: IsoDateTime;
}

/* ---------------- diary ---------------- */

export type DiaryVisibility = "private" | "community" | "public";

export interface DiaryEntry {
  id: UUID;
  date: IsoDate;
  spot: { id: UUID; slug: string; name: string; url: string; region: { id: number; slug: string; name: string } | null; is_published?: boolean } | null;
  spot_name: string;
  place_name: string;
  duration_min: number | null;
  board_note: string;
  conditions: string;
  wave_height_m: string | null;
  mood_rating: number | null;
  notes: string;
  visibility: DiaryVisibility;
  visibility_label: string;
  photos: Media[];
  created_at?: IsoDateTime;
  updated_at?: IsoDateTime;
}

export interface DiaryInput {
  date: IsoDate;
  spot_id?: string | null;
  spot_name?: string;
  duration_min?: number | null;
  board_note?: string;
  conditions?: string;
  wave_height_m?: string | null;
  mood_rating?: number | null;
  notes?: string;
  visibility?: DiaryVisibility;
  photo_ids?: string[];
}

export interface DiaryStats {
  ride_days: number;
  sessions: number;
  spots_visited: number;
  this_year_days: number;
  longest_streak_days: number;
  current_streak_days: number;
  last_ride_date: IsoDate | null;
  top_spots: Array<{ spot: { id: UUID; slug: string; name: string; url: string } | null; name: string; days: number }>;
}

export interface SpotOption {
  id: UUID;
  slug: string;
  name: string;
  region?: { name: string } | string | null;
}

/* ---------------- API ---------------- */

const id = (v: string) => encodeURIComponent(v);

export const mineApi = {
  proposals: (status?: string, page = 1) =>
    api.get<Paginated<MyProposal>>("me/proposals", { query: { status, page, page_size: 50 } }),
  updateProposal: (proposalId: string, body: ProposalUpdate) => api.patch<MyProposal>(`proposals/${id(proposalId)}`, body),
  withdrawProposal: (proposalId: string) => api.post<MyProposal>(`proposals/${id(proposalId)}/withdraw`),
  spotDictionaries: () => api.get<SpotDictionaries>("spots/dictionaries"),

  reviews: (status?: string, page = 1) => api.get<Paginated<MyReview>>("me/reviews", { query: { status, page, page_size: 50 } }),
  deleteReview: (reviewId: string) => api.delete(`reviews/${id(reviewId)}`),

  complaints: (box: "filed" | "against") =>
    api.get<Paginated<MyComplaint | ComplaintAgainstMe>>("me/complaints", { query: { box: box === "against" ? "against" : undefined, page_size: 100 } }),
  appeal: (complaintId: string, text: string) => api.post<ComplaintAgainstMe>(`complaints/${id(complaintId)}/appeal`, { text }),

  invites: () => api.get<MyInvite[]>("me/invites"),
  invite: (token: string) => api.get<MyInvite>(`invites/${id(token)}`),
  acceptInvite: (token: string) => api.post<unknown>(`invites/${id(token)}/accept`),
  declineInvite: (token: string) => api.post<MyInvite>(`invites/${id(token)}/decline`),

  diary: (page = 1) => api.get<Paginated<DiaryEntry>>("me/diary", { query: { page, page_size: 20 } }),
  diaryStats: () => api.get<DiaryStats>("me/diary/stats"),
  createDiary: (body: DiaryInput) => api.post<DiaryEntry>("me/diary", body),
  updateDiary: (entryId: string, body: Partial<DiaryInput>) => api.patch<DiaryEntry>(`me/diary/${id(entryId)}`, body),
  deleteDiary: (entryId: string) => api.delete(`me/diary/${id(entryId)}`),
  spotOptions: () => api.get<Paginated<SpotOption>>("spots", { query: { page_size: 100 } }),
};

/** DRF list or plain array → items. */
export function itemsOf<T>(data: Paginated<T> | T[] | null | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results ?? [];
}
