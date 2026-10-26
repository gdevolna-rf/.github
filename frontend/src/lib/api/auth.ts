/**
 * accounts: session auth, registration, verification, password reset, `GET /me`, `GET /me/counters`.
 * `normalizeMe` converts the raw `/me` payload into the stable `Me` shape the UI uses, so small backend
 * naming differences are absorbed here and nowhere else.
 */
import { api } from "./client";
import type {
  Counters,
  Media,
  MembershipRole,
  OrganizationKind,
  PrimaryType,
  RegionRef,
  SpecialtyCode,
  StaffRole,
  UUID,
} from "./types";

export interface MyOrganization {
  id: UUID;
  slug: string;
  name: string;
  kind: OrganizationKind;
  role: MembershipRole;
  /** organization status (draft / pending_review / published / suspended / archived) */
  status?: string;
  membershipId?: UUID;
}

export interface Me {
  id: UUID;
  email: string;
  emailVerified: boolean;
  handle: string;
  firstName: string;
  lastName: string;
  displayName: string;
  avatar: Media | null;
  region: RegionRef | null;
  /** Active specialties only (disabled ones keep their history but hide the tools, BR-11). */
  specialties: SpecialtyCode[];
  primarySpecialty: SpecialtyCode | null;
  staffRoles: StaffRole[];
  isModerator: boolean;
  isAdmin: boolean;
  twoFactor: { enabled: boolean; verified: boolean };
  organizations: MyOrganization[];
  ggSurferEnabled: boolean;
  /** Pending account deletion (AT-10) or null. */
  deletion: { requestedAt: string; scheduledFor: string } | null;
  /** Own instructor card, if the instructor specialty was ever set up. */
  instructorProfile: { id: UUID; status: string } | null;
  /** Untouched payload for fields not covered above. */
  raw: Record<string, unknown>;
}

type Raw = Record<string, unknown>;
const obj = (v: unknown): Raw => (v && typeof v === "object" && !Array.isArray(v) ? (v as Raw) : {});
const str = (v: unknown): string => (typeof v === "string" ? v : v == null ? "" : String(v));

function specialtyList(value: unknown): { codes: SpecialtyCode[]; primary: SpecialtyCode | null } {
  const codes: SpecialtyCode[] = [];
  let primary: SpecialtyCode | null = null;
  if (Array.isArray(value)) {
    for (const item of value) {
      if (typeof item === "string") codes.push(item as SpecialtyCode);
      else {
        const o = obj(item);
        const code = str(o.code ?? obj(o.specialty).code ?? o.specialty) as SpecialtyCode;
        const status = str(o.status || "active");
        if (code && status === "active") codes.push(code);
        if (code && o.is_primary) primary = code;
      }
    }
  }
  return { codes: Array.from(new Set(codes)), primary };
}

function roleList(value: unknown): StaffRole[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((r) => (typeof r === "string" ? r : str(obj(r).role)))
    .filter(Boolean) as StaffRole[];
}

function orgList(value: unknown): MyOrganization[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    const o = obj(item);
    const org = obj(o.organization);
    const src = Object.keys(org).length ? org : o;
    return {
      id: str(src.id),
      slug: str(src.slug),
      name: str(src.name) || "Организация",
      kind: (str(src.kind) || "school") as OrganizationKind,
      role: (str(o.role) || "staff") as MembershipRole,
      status: src.status ? str(src.status) : o.status ? str(o.status) : undefined,
      membershipId: o.membership_id ? str(o.membership_id) : undefined,
    };
  });
}

export function normalizeMe(input: unknown): Me {
  const raw = obj(input);
  // `/me` may be {account fields…, profile:{…}} or flat, or wrapped {account:{…}}
  const base = Object.keys(obj(raw.account)).length ? { ...raw, ...obj(raw.account) } : raw;
  const profile = obj(base.profile);
  const pick = (key: string) => (profile[key] !== undefined ? profile[key] : base[key]);

  const firstName = str(pick("first_name"));
  const lastName = str(pick("last_name"));
  const handle = str(pick("handle"));
  const displayName = str(pick("display_name")) || `${firstName} ${lastName}`.trim() || handle || "Участник";
  const { codes, primary } = specialtyList(base.specialties);
  const staffRoles = roleList(base.staff_roles ?? base.roles);
  const tf = obj(base.two_factor);
  const regionRaw = pick("region");
  const region =
    regionRaw && typeof regionRaw === "object"
      ? (regionRaw as RegionRef)
      : regionRaw
        ? { id: str(regionRaw), slug: str(regionRaw), name: str(pick("region_name") || regionRaw) }
        : null;

  return {
    id: str(base.id),
    email: str(base.email),
    emailVerified: Boolean(base.email_verified ?? base.is_email_verified ?? base.email_verified_at),
    handle,
    firstName,
    lastName,
    displayName,
    avatar: (pick("avatar") as Media | null) ?? null,
    region,
    specialties: codes,
    primarySpecialty: primary,
    staffRoles,
    isModerator: staffRoles.includes("moderator") || staffRoles.includes("admin"),
    isAdmin: staffRoles.includes("admin"),
    twoFactor: {
      enabled: Boolean(tf.enabled ?? base.totp_enabled),
      verified: Boolean(tf.verified ?? tf.verified_in_session ?? tf.session_verified),
    },
    organizations: orgList(base.organizations ?? base.memberships),
    ggSurferEnabled: Boolean(pick("gg_surfer_enabled")),
    deletion: (() => {
      const d = obj(base.deletion);
      return d.scheduled_for || d.requested_at
        ? { requestedAt: str(d.requested_at), scheduledFor: str(d.scheduled_for) }
        : null;
    })(),
    instructorProfile: (() => {
      const ip = obj(base.instructor_profile);
      return ip.id ? { id: str(ip.id), status: str(ip.status) } : null;
    })(),
    raw,
  };
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  primary_type: PrimaryType;
  extra_specialties: SpecialtyCode[];
  accept_terms: boolean;
  accept_privacy: boolean;
}

/** POST /auth/register returns the `/me` payload + `next_step`. */
export interface RegisterResult {
  /** e.g. "create_school" (school primary type), "verify_email". */
  next_step?: string | null;
  [key: string]: unknown;
}

export const authApi = {
  me: () => api.get<unknown>("me").then(normalizeMe),
  updateMe: (patch: Record<string, unknown>) => api.patch<unknown>("me", patch).then(normalizeMe),
  counters: () => api.get<Counters>("me/counters"),
  login: (payload: LoginPayload) => api.post<unknown>("auth/login", payload),
  logout: () => api.post<void>("auth/logout"),
  register: (payload: RegisterPayload) => api.post<RegisterResult>("auth/register", payload),
  verifyEmail: (token: string) => api.post<unknown>("auth/verify-email", { token }),
  resendVerification: () => api.post<unknown>("auth/verify-email/resend"),
  requestPasswordReset: (email: string) => api.post<unknown>("auth/password-reset", { email }),
  confirmPasswordReset: (payload: { uid: string; token: string; new_password: string }) =>
    api.post<unknown>("auth/password-reset/confirm", payload),
};

/** Where to go after registration, by `next_step` (ACC-01, ARCHITECTURE accounts table). */
export function routeForNextStep(nextStep: string | null | undefined, fallback: string): string {
  switch (nextStep) {
    case "create_school":
      return "/account/orgs?create=school";
    case "verify_email":
      return "/verify-email?sent=1";
    case "complete_profile":
      return "/account/profile";
    default:
      return fallback;
  }
}

/**
 * Only same-site relative paths are accepted as `?next=` targets (open-redirect protection).
 * Auth pages themselves are not valid targets.
 */
export function safeNext(next: string | null | undefined, fallback = "/account"): string {
  if (!next || typeof next !== "string") return fallback;
  if (!next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  if (/^\/(login|register|reset-password|verify-email)(\/|\?|$)/.test(next)) return fallback;
  return next;
}

export function loginHref(next?: string | null): string {
  const target = next ? safeNext(next, "") : "";
  return target ? `/login?next=${encodeURIComponent(target)}` : "/login";
}
