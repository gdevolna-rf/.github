/**
 * Organizations & school cabinet API (TZ 8.3, 20, SCH-01…13, AT-09, F05/F15, ATX-18).
 * Shapes: backend/apps/organizations/serializers.py, backend/apps/learning/serializers.py (ProgramSerializer,
 * SessionManageSerializer), backend/apps/inventory/serializers.py, backend/apps/trust/serializers.py,
 * backend/apps/commerce/serializers.py (InquiryListSerializer, BookingSerializer).
 */
import { api } from "./client";
import { listAll, type ManagedSession, type StudentsPage } from "./learningCabinet";
import type { Decimal, IsoDateTime, Media, MembershipRole, OrganizationKind, Paginated, PublicAccount, UUID } from "./types";

export type OrganizationStatus = "draft" | "pending_review" | "published" | "suspended" | "archived";
export type MembershipStatus = "active" | "revoked" | "left";

export interface OrgRegion {
  id: number;
  slug: string;
  name: string;
}

/** OrganizationCardSerializer (GET /me/organizations → organization). */
export interface OrgCard {
  id: UUID;
  slug: string;
  kind: OrganizationKind;
  name: string;
  short_description: string;
  region: OrgRegion | null;
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
  is_demo: boolean;
  /** not in the card serializer, kept optional for forward compatibility */
  status?: OrganizationStatus;
}

export interface MyMembership {
  membership_id: UUID;
  role: MembershipRole;
  status: MembershipStatus;
  title: string;
  joined_at: IsoDateTime;
  organization: OrgCard;
}

export interface OrgSpot {
  id: UUID;
  slug: string;
  name: string;
  region: OrgRegion | null;
}

/** OrganizationManageSerializer (GET/PATCH organizations/{id}/manage — owner/manager). */
export interface OrgManage {
  id: UUID;
  slug: string;
  kind: OrganizationKind;
  name: string;
  status: OrganizationStatus;
  verification_status: string;
  moderation_note: string;
  short_description: string;
  description: string;
  region: OrgRegion | null;
  city: string;
  address: string;
  spots: OrgSpot[];
  logo: Media | null;
  cover: Media | null;
  gallery: Media[];
  phone: string;
  email: string;
  website: string;
  social_links: Record<string, string>;
  formats: string[];
  languages: string[];
  price_from: Decimal | null;
  currency: string;
  rating_avg: Decimal;
  rating_count: number;
  published_at: IsoDateTime | null;
  owner: PublicAccount;
  my_role: MembershipRole | null;
  members_count: number;
  pending_invites_count: number;
  /** name / description / region / spots_or_address */
  missing_fields: string[];
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface OrgInput {
  kind?: OrganizationKind;
  name?: string;
  short_description?: string;
  description?: string;
  region_id?: number | null;
  city?: string;
  address?: string;
  spot_ids?: UUID[];
  logo_id?: UUID | null;
  cover_id?: UUID | null;
  gallery_ids?: UUID[];
  phone?: string;
  email?: string;
  website?: string;
  social_links?: Record<string, string>;
  formats?: string[];
  languages?: string[];
  price_from?: string | null;
  currency?: string;
}

export interface Member {
  id: UUID;
  account: PublicAccount;
  role: MembershipRole;
  status: MembershipStatus;
  title: string;
  joined_at: IsoDateTime;
  invited_by: PublicAccount | null;
  revoked_at: IsoDateTime | null;
  revoked_by: PublicAccount | null;
}

export interface OrgInvite {
  id: UUID;
  email: string;
  role: MembershipRole;
  status: string;
  message: string;
  invited_by: PublicAccount;
  has_account: boolean;
  expires_at: IsoDateTime;
  responded_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

export type ProgramFormat = "individual" | "group";
export type AgeCategory = "kids" | "teens" | "adults" | "all";

export interface Program {
  id: UUID;
  title: string;
  description: string;
  level: string;
  age_category: AgeCategory;
  format: ProgramFormat;
  duration_min: number;
  sessions_count: number;
  price: Decimal;
  currency: string;
  max_group_size: number;
  equipment_included: boolean;
  is_active: boolean;
  upcoming_sessions: number;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface ProgramInput {
  title: string;
  description?: string;
  level?: string;
  age_category?: AgeCategory;
  format?: ProgramFormat;
  duration_min?: number;
  sessions_count?: number;
  price: string;
  currency?: string;
  max_group_size?: number;
  equipment_included?: boolean;
  is_active?: boolean;
}

export interface SchoolSessionInput {
  program_id?: UUID | null;
  title?: string;
  instructor_id?: UUID | null;
  spot_slug?: string | null;
  starts_at: string;
  ends_at?: string | null;
  capacity?: number;
  price?: string | null;
  currency?: string;
  notes?: string;
}

export interface SchoolSessionPatch {
  title?: string;
  program_id?: UUID | null;
  spot_slug?: string | null;
  capacity?: number;
  price?: string | null;
  notes?: string;
}

/** InventoryItemCabinetSerializer (subset). */
export interface InventoryCard {
  id: UUID;
  title: string;
  kind: string;
  kind_label: string;
  purpose: string;
  size: string;
  condition: string;
  condition_label: string;
  region: { slug: string; name: string } | null;
  pickup_location: string;
  rental_price_per_day: Decimal | null;
  rental_price_per_hour: Decimal | null;
  sale_price: Decimal | null;
  currency: string;
  cover: Media | null;
  photos_count: number;
  status: string;
  status_label: string;
  is_published: boolean;
  public_url: string;
}

export interface PublicReview {
  id: UUID;
  target_type: string;
  rating: number;
  text: string;
  author: PublicAccount;
  context_label: string;
  photos: Media[];
  published_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

export interface InquirySummary {
  id: UUID;
  kind: string;
  kind_label: string;
  status: string;
  status_label: string;
  subject: string;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  counterpart: { name: string; avatar: Media | null } | null;
  context: { title: string; subtitle: string } | null;
  last_message: { body: string; created_at: IsoDateTime; sender_name: string | null } | null;
  unread_count: number;
}

/** BookingSerializer (subset) — used to list participants of a school session for managers. */
export interface ProviderBooking {
  id: UUID;
  status: string;
  seats: number;
  participant_name: string;
  participant_is_minor: boolean;
  customer: PublicAccount;
  created_at: IsoDateTime;
  lesson: { session_id: UUID; title: string } | null;
}

export const orgApi = {
  mine: () => api.get<MyMembership[]>("me/organizations"),
  myInvitesCount: () => api.get<unknown[]>("me/invites").then((rows) => (Array.isArray(rows) ? rows.length : 0)),
  create: (input: OrgInput & { kind: OrganizationKind; name: string }) => api.post<OrgManage>("organizations", input),
  manage: (id: UUID) => api.get<OrgManage>(`organizations/${id}/manage`),
  update: (id: UUID, patch: OrgInput) => api.patch<OrgManage>(`organizations/${id}/manage`, patch),
  submit: (id: UUID) => api.post<OrgManage>(`organizations/${id}/submit`),
  members: (id: UUID, status?: MembershipStatus | "all") => api.get<Member[]>(`organizations/${id}/members`, { query: { status } }),
  updateMember: (id: UUID, membershipId: UUID, body: { role?: MembershipRole; title?: string }) =>
    api.patch<Member>(`organizations/${id}/members/${membershipId}`, body),
  revokeMember: (id: UUID, membershipId: UUID) => api.delete<Member>(`organizations/${id}/members/${membershipId}`),
  invites: (id: UUID, status: string = "pending") => api.get<OrgInvite[]>(`organizations/${id}/invites`, { query: { status } }),
  invite: (id: UUID, body: { email: string; role: MembershipRole; message?: string }) => api.post<OrgInvite>(`organizations/${id}/invites`, body),
  revokeInvite: (inviteId: UUID) => api.delete<OrgInvite>(`invites/${inviteId}`),
  transferOwnership: (id: UUID, accountId: UUID) => api.post<OrgManage>(`organizations/${id}/transfer-ownership`, { account_id: accountId }),
  leave: (id: UUID) => api.post<void>(`organizations/${id}/leave`),
  programs: {
    list: (orgId: UUID) => listAll<Program>(`organizations/${orgId}/programs`),
    create: (orgId: UUID, body: ProgramInput) => api.post<Program>(`organizations/${orgId}/programs`, body),
    update: (orgId: UUID, id: UUID, body: Partial<ProgramInput>) => api.patch<Program>(`organizations/${orgId}/programs/${id}`, body),
    remove: (orgId: UUID, id: UUID) => api.delete(`organizations/${orgId}/programs/${id}`),
  },
  sessions: {
    list: (orgId: UUID, q: { from: string; to: string; tz?: string; status?: string; instructor_id?: string; program_id?: string }) =>
      listAll<ManagedSession>(`organizations/${orgId}/sessions`, q),
    create: (orgId: UUID, body: SchoolSessionInput) => api.post<ManagedSession>(`organizations/${orgId}/sessions`, body),
    update: (orgId: UUID, id: UUID, body: SchoolSessionPatch) => api.patch<ManagedSession>(`organizations/${orgId}/sessions/${id}`, body),
    remove: (orgId: UUID, id: UUID) => api.delete(`organizations/${orgId}/sessions/${id}`),
    /** Active bookings of one session (confirmed / in progress / requested) — provider view of the school. */
    bookings: (orgId: UUID, session: { id: UUID; starts_at: string; ends_at: string }) =>
      listAll<ProviderBooking>("bookings", {
        box: "provider",
        organization: orgId,
        kind: "lesson",
        from: session.starts_at,
        to: session.ends_at,
      }).then((rows) => rows.filter((b) => b.lesson?.session_id === session.id)),
  },
  students: (orgId: UUID, q: { q?: string; repeat?: boolean; page?: number; page_size?: number }) =>
    api.get<StudentsPage>(`organizations/${orgId}/students`, { query: { ...q, repeat: q.repeat ? "true" : undefined } }),
  inventory: (orgId: UUID) => api.get<Paginated<InventoryCard>>("me/inventory", { query: { organization: orgId, page_size: 50 } }),
  reviews: (orgId: UUID, page = 1) =>
    api.get<Paginated<PublicReview>>("reviews", { query: { target_type: "organization", target_id: orgId, page, page_size: 10 } }),
  inquiries: (orgId: UUID) =>
    api.get<Paginated<InquirySummary>>("inquiries", { query: { box: "incoming", organization: orgId, page_size: 5 } }),
};

/** Query keys (domain "school-cabinet"; my memberships use the shared qk.myOrganizations). */
export const sk = {
  all: ["school-cabinet"] as const,
  org: (id: UUID) => ["school-cabinet", id] as const,
  manage: (id: UUID) => ["school-cabinet", id, "manage"] as const,
  members: (id: UUID, status: string) => ["school-cabinet", id, "members", status] as const,
  invites: (id: UUID) => ["school-cabinet", id, "invites"] as const,
  programs: (id: UUID) => ["school-cabinet", id, "programs"] as const,
  sessionsAll: (id: UUID) => ["school-cabinet", id, "sessions"] as const,
  sessions: (id: UUID, from: string, to: string, tz: string) => ["school-cabinet", id, "sessions", from, to, tz] as const,
  sessionBookings: (id: UUID, sessionId: UUID) => ["school-cabinet", id, "sessions", "bookings", sessionId] as const,
  students: (id: UUID, q: string, repeat: boolean, page: number) => ["school-cabinet", id, "students", q, repeat, page] as const,
  inventory: (id: UUID) => ["school-cabinet", id, "inventory"] as const,
  reviews: (id: UUID, page: number) => ["school-cabinet", id, "reviews", page] as const,
  inquiries: (id: UUID) => ["school-cabinet", id, "inquiries"] as const,
};
