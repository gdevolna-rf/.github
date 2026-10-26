/**
 * trust/moderation (staff): unified queue, case detail with `target`/`history`/`available_actions`, decisions,
 * audit log, account restrictions, moderation stats, staff roles, TOTP 2FA for the staff session
 * (ARCHITECTURE §3 trust/accounts, TRUST-04/06/07, DATA-09, BR-04, 11 «2FA для админов»).
 *
 * Every endpoint here needs a server role + a 2FA-verified session; the server answers 403 otherwise.
 * Query keys live in `modKeys` (domain prefix "moderation") so mutations can invalidate the whole domain.
 */
import { api, type Query } from "./client";
import type { ChoiceValue, IsoDate, IsoDateTime, Media, Paginated, PublicAccount, UUID } from "./types";

/* ---------------- keys ---------------- */

export const modKeys = {
  all: ["moderation"] as const,
  cases: (params: object) => ["moderation", "cases", params] as const,
  case: (id: string) => ["moderation", "case", id] as const,
  stats: ["moderation", "stats"] as const,
  audit: (params: object) => ["moderation", "audit", params] as const,
  account: (id: string) => ["moderation", "account", id] as const,
  staffRoles: (includeRevoked: boolean) => ["moderation", "staff-roles", includeRevoked] as const,
};

/* ---------------- shared shapes ---------------- */

export type CaseKind = "spot_change" | "review" | "certificate" | "complaint" | "organization" | "appeal";
export type CaseStatus = "open" | "in_review" | "resolved";
export type CaseAction =
  | "approve"
  | "reject"
  | "request_info"
  | "revert"
  | "hide"
  | "revoke"
  | "resolve"
  | "dismiss"
  | "appeal_grant"
  | "appeal_deny";

/** apps.trust.serializers.ModeratorMediaSerializer — Media + short-lived `signed_url` (private files too). */
export interface ModeratorMedia extends Media {
  signed_url: string | null;
}

export interface AuditEvent {
  id: UUID;
  actor: PublicAccount | null;
  action: string;
  object_type: string;
  object_id: string;
  organization: UUID | null;
  before: unknown;
  after: unknown;
  metadata: Record<string, unknown> | null;
  ip: string | null;
  request_id: string;
  created_at: IsoDateTime;
}

/** CaseListSerializer */
export interface ModerationCaseItem {
  id: UUID;
  kind: ChoiceValue<CaseKind>;
  status: ChoiceValue<CaseStatus>;
  summary: string;
  target_id: UUID | null;
  due_at: IsoDateTime | null;
  is_overdue: boolean;
  assigned_to: PublicAccount | null;
  resolution: string;
  resolution_note: string;
  resolved_by: PublicAccount | null;
  resolved_at: IsoDateTime | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

/* ---------------- case targets (CaseDetailSerializer.target, discriminated by `type`) ---------------- */

/** spots ProposalChangeWithCurrentSerializer */
export interface SpotDiffItem {
  field: string;
  label: string;
  kind: "text" | "choice" | "compass" | "months" | "hazards" | "infrastructure" | string;
  old: unknown;
  new: unknown;
  old_display: string;
  new_display: string;
  current?: unknown;
  current_display?: string;
  changed_since_submission?: boolean;
}

export interface SpotChangeTarget {
  type: "spot_change";
  id: UUID;
  status: ChoiceValue;
  spot: { id: UUID; slug: string; name: string; region: string };
  author: PublicAccount;
  comment: string;
  source: string;
  diff: SpotDiffItem[];
  evidence: ModeratorMedia[];
  moderator: PublicAccount | null;
  moderator_comment: string;
  decided_at: IsoDateTime | null;
  reverted_at: IsoDateTime | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface ReviewTargetRef {
  type: string;
  id: UUID;
  name: string;
  link: string;
}

export interface ReviewCaseTarget {
  type: "review";
  id: UUID;
  status: ChoiceValue;
  target_type: string;
  target: ReviewTargetRef;
  rating: number;
  text: string;
  has_pending_revision: boolean;
  pending_rating: number | null;
  pending_text: string;
  photos: ModeratorMedia[];
  pending_photos: ModeratorMedia[];
  author: PublicAccount;
  context_label: string;
  booking: UUID | null;
  inquiry: UUID | null;
  moderation_note: string;
  published_at: IsoDateTime | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface CertificateCaseTarget {
  type: "certificate";
  id: UUID;
  status: ChoiceValue;
  title: string;
  issuer: string;
  issued_on: IsoDate | null;
  valid_until: IsoDate | null;
  allow_public_scan: boolean;
  instructor: { id: UUID; headline: string; status: string; account: PublicAccount };
  document: ModeratorMedia | null;
  moderator_comment: string;
  decided_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

export interface OrganizationCaseTarget {
  type: "organization";
  id: UUID;
  kind: ChoiceValue;
  name: string;
  slug: string;
  status: string;
  verification_status: string;
  short_description: string;
  description: string;
  region: string | null;
  city: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  social_links: Record<string, string> | null;
  formats: string[];
  languages: string[];
  price_from: string | null;
  currency: string;
  logo: Media | null;
  cover: Media | null;
  gallery: Media[];
  owner: PublicAccount;
  spots: Array<{ id: UUID; slug: string; name: string; region: string }>;
  moderation_note: string;
  created_at: IsoDateTime;
}

/** complaint_target_snapshot(): `exists:false` when the target was deleted; other keys depend on target_type. */
export interface ComplaintSnapshot {
  exists: boolean;
  name?: string;
  title?: string;
  slug?: string;
  status?: string;
  region?: string;
  link?: string;
  account?: PublicAccount;
  bio?: string;
  is_active?: boolean;
  rating?: number;
  text?: string;
  author?: PublicAccount;
  target?: ReviewTargetRef;
  body?: string;
  is_hidden?: boolean;
  is_published?: boolean;
  conversation_id?: string;
  created_at?: string;
  sender?: PublicAccount | null;
  attachments?: ModeratorMedia[];
  description?: string;
  workshop?: { id: string; name: string; slug: string };
  owner?: PublicAccount | null;
  organization?: { id: string; name: string } | null;
  kind?: string;
  media?: ModeratorMedia;
  starts_at?: string;
}

export interface ComplaintCaseTarget {
  type: "complaint";
  id: UUID;
  status: ChoiceValue;
  reason: ChoiceValue;
  text: string;
  reporter: PublicAccount;
  target_type: ChoiceValue;
  target_id: string;
  target_owner: PublicAccount | null;
  target_snapshot: ComplaintSnapshot;
  owner_history: { complaints_total: number; complaints_upheld: number; active_restrictions: number } | null;
  action_taken: ChoiceValue;
  appeal_text: string;
  appealed_at: IsoDateTime | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export type CaseTarget = SpotChangeTarget | ReviewCaseTarget | CertificateCaseTarget | OrganizationCaseTarget | ComplaintCaseTarget;

export interface ModerationCaseDetail extends ModerationCaseItem {
  target: CaseTarget | null;
  history: AuditEvent[];
  available_actions: CaseAction[];
}

/* ---------------- stats, accounts, restrictions ---------------- */

export interface ModerationStats {
  generated_at: IsoDateTime;
  open_cases: { total: number; by_kind: Partial<Record<CaseKind, number>> };
  overdue_cases: { total: number; by_kind: Partial<Record<CaseKind, number>> };
  oldest_open_case_hours: number | null;
  spot_proposals: {
    period_days: number;
    decided: number;
    approved: number;
    rejected: number;
    median_hours_to_decision: number | null;
  };
  resolved_last_period: number;
}

export type RestrictionKind = "messaging" | "publishing" | "suspended";

export interface Restriction {
  id: UUID;
  account: PublicAccount;
  kind: ChoiceValue<RestrictionKind>;
  reason: string;
  created_by: PublicAccount | null;
  expires_at: IsoDateTime | null;
  lifted_at: IsoDateTime | null;
  is_active: boolean;
  created_at: IsoDateTime;
}

export interface ModeratorComplaintShort {
  id: UUID;
  target_type: ChoiceValue;
  target_id: string;
  reason: ChoiceValue;
  text: string;
  status: ChoiceValue;
  action_taken: ChoiceValue;
  reporter: PublicAccount;
  appealed_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

export interface ModerationAccountSummary {
  account: PublicAccount;
  summary: {
    roles: string[];
    date_joined: IsoDateTime;
    is_active: boolean;
    is_email_verified: boolean;
    is_deleted: boolean;
    organizations: Array<{ id: UUID; name: string; kind: string; role: string; status: string }>;
    counts: {
      reviews: Record<string, number>;
      spot_proposals: number;
      complaints_filed: number;
      complaints_against: number;
      complaints_against_upheld: number;
    };
  };
  restrictions: Restriction[];
  complaints: ModeratorComplaintShort[];
}

/* ---------------- staff roles & 2FA ---------------- */

export type GrantableRole = "moderator" | "organizer" | "admin";

export interface StaffRoleRecord {
  id: number;
  account: PublicAccount;
  account_email: string;
  role: GrantableRole | string;
  granted_by: PublicAccount | null;
  granted_at: IsoDateTime;
  revoked_at: IsoDateTime | null;
  two_factor_enabled: boolean;
}

export interface TwoFactorState {
  enabled: boolean;
  verified: boolean;
  required: boolean;
}

/* ---------------- query params ---------------- */

export interface CaseListParams {
  kind?: string;
  status?: "open" | "in_review" | "resolved" | "all";
  overdue?: boolean;
  assigned?: "me" | "none";
  q?: string;
  page?: number;
  page_size?: number;
}

export interface AuditParams {
  object_type?: string;
  object_id?: string;
  actor?: string;
  action?: string;
  action_prefix?: string;
  from?: string;
  to?: string;
  page?: number;
  page_size?: number;
}

/* ---------------- decisions: path + body per kind/action ---------------- */

const DECISION_SEGMENT: Record<string, string> = {
  spot_change: "proposals",
  review: "reviews",
  certificate: "certificates",
  organization: "organizations",
  complaint: "complaints",
  appeal: "complaints",
};

const ACTION_SEGMENT: Partial<Record<CaseAction, string>> = {
  approve: "approve",
  reject: "reject",
  request_info: "request-info",
  revert: "revert",
  hide: "hide",
  revoke: "revoke",
  resolve: "resolve",
  dismiss: "dismiss",
  appeal_grant: "appeal-decision",
  appeal_deny: "appeal-decision",
};

/** `moderation/<segment>/<target id>/<action>` for a case kind (appeals are decided on the complaint). */
export function decisionPath(kind: CaseKind | string, targetId: string, action: CaseAction): string {
  const segment = DECISION_SEGMENT[kind];
  const verb = ACTION_SEGMENT[action];
  if (!segment || !verb) throw new Error(`Unsupported moderation action ${kind}/${action}`);
  return `moderation/${segment}/${encodeURIComponent(targetId)}/${verb}`;
}

export interface DecisionInput {
  /** comment (proposals) or note (others) — the API field name is chosen by `decisionBody`. */
  text?: string;
  addEvidenceToGallery?: boolean;
  force?: boolean;
  complaintAction?: "none" | "warning" | "hidden" | "suspended";
  expiresAt?: string | null;
}

/** Proposals take `comment` (≤2000); every other decision takes `note` (≤300). */
export function decisionBody(kind: CaseKind | string, action: CaseAction, input: DecisionInput): Record<string, unknown> {
  const text = (input.text ?? "").trim();
  if (kind === "spot_change") {
    const body: Record<string, unknown> = { comment: text };
    if (action === "approve") body.add_evidence_to_gallery = Boolean(input.addEvidenceToGallery);
    if (action === "revert") body.force = Boolean(input.force);
    return body;
  }
  if (action === "resolve") {
    const body: Record<string, unknown> = { action: input.complaintAction ?? "none", note: text };
    if (input.complaintAction === "suspended" && input.expiresAt) body.expires_at = input.expiresAt;
    return body;
  }
  if (action === "appeal_grant" || action === "appeal_deny") return { grant: action === "appeal_grant", note: text };
  return { note: text };
}

/* ---------------- API ---------------- */

const clean = (q: Record<string, unknown>): Query => {
  const out: Query = {};
  for (const [k, v] of Object.entries(q)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    out[k] = v as Query[string];
  }
  return out;
};

export const moderationApi = {
  cases: (params: CaseListParams) => api.get<Paginated<ModerationCaseItem>>("moderation/cases", { query: clean({ ...params }) }),
  case: (id: string) => api.get<ModerationCaseDetail>(`moderation/cases/${encodeURIComponent(id)}`),
  take: (id: string) => api.post<ModerationCaseItem>(`moderation/cases/${encodeURIComponent(id)}/take`),
  decide: (kind: CaseKind | string, targetId: string, action: CaseAction, input: DecisionInput) =>
    api.post<unknown>(decisionPath(kind, targetId, action), decisionBody(kind, action, input)),
  stats: (days = 30) => api.get<ModerationStats>("moderation/stats", { query: { days } }),
  audit: (params: AuditParams) => api.get<Paginated<AuditEvent>>("moderation/audit", { query: clean({ ...params }) }),
  account: (id: string) => api.get<ModerationAccountSummary>(`moderation/accounts/${encodeURIComponent(id)}`),
  restrict: (accountId: string, body: { kind: RestrictionKind; reason: string; expires_at?: string | null }) =>
    api.post<Restriction>(`moderation/accounts/${encodeURIComponent(accountId)}/restrict`, body),
  lift: (restrictionId: string, note: string) =>
    api.post<Restriction>(`moderation/restrictions/${encodeURIComponent(restrictionId)}/lift`, { note }),
};

export const staffApi = {
  roles: (includeRevoked = false) =>
    api.get<StaffRoleRecord[]>("staff/roles", { query: includeRevoked ? { include_revoked: 1 } : undefined }),
  grant: (account_email: string, role: GrantableRole) => api.post<StaffRoleRecord>("staff/roles", { account_email, role }),
  revoke: (id: number) => api.delete<StaffRoleRecord>(`staff/roles/${id}`),
};

export const twoFactorApi = {
  /** TOTP code → marks the current session as verified (staff actions). */
  verify: (code: string) => api.post<TwoFactorState>("auth/2fa/verify", { code }),
  /** New secret for the authenticator app (2FA is enabled only after `enable`). */
  setup: () => api.post<{ secret: string; otpauth_uri: string }>("me/2fa/setup"),
  enable: (code: string) => api.post<TwoFactorState>("me/2fa/enable", { code }),
};

/** "123 456" / "123-456" → "123456". */
export function normalizeTotp(value: string): string {
  return value.replace(/\D/g, "").slice(0, 6);
}
