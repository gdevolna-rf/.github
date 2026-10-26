/**
 * Account self-service (fe-account): profile, settings, specialties, security, consents, data export/deletion,
 * notification preferences, blocks, notifications feed, favorites list.
 * Shapes: backend/apps/accounts/serializers.py, apps/messaging/serializers.py, apps/favorites/serializers.py.
 *
 * Query keys start with an existing domain head ("me", "notifications") so the realtime bridge and logout
 * (resetPrivateData) refresh / drop them together with the shared keys from keys.ts.
 */
import { api } from "./client";
import type { Counters, FavoriteTargetType, Media, Paginated, PublicAccount, RegionRef, SpecialtyCode, UUID } from "./types";

/* ---------------- query keys (local to the account screens) ---------------- */

export const accountKeys = {
  regions: ["public", "regions"] as const,
  spotOptions: ["public", "spot-options"] as const,
  consents: ["me", "consents"] as const,
  exports: ["me", "exports"] as const,
  deletion: ["me", "deletion"] as const,
  notificationPrefs: ["me", "notification-preferences"] as const,
  blocks: ["me", "blocks"] as const,
  favoritesAll: ["me", "favorites", "list", "account-page"] as const,
  notifications: (filter: "unread" | "all") => ["notifications", filter] as const,
};

/* ---------------- /me profile (raw backend shape) ---------------- */

export type RidingLevel = "beginner" | "intermediate" | "advanced" | "pro" | "";
export type ContactPolicy = "everyone" | "nobody";

/** `GET /me` → `profile` (MeProfileSerializer). Private fields (phone, birth_date, private_contacts) only here. */
export interface MeProfile {
  handle: string;
  first_name: string;
  last_name: string;
  display_name: string;
  avatar: Media | null;
  region: (RegionRef & { id: number }) | null;
  city: string;
  bio: string;
  fun_facts: string[];
  surfing_since: number | null;
  riding_level: RidingLevel;
  preferred_board_types: string[];
  favorite_spot_ids: UUID[];
  interests: string[];
  languages: string[];
  phone: string;
  birth_date: string | null;
  private_contacts: string;
  gg_surfer_enabled: boolean;
  gg_contact_policy: ContactPolicy;
  gg_show_region: boolean;
  gg_show_age: boolean;
  birthday_greetings_consent: boolean;
  show_birthday: boolean;
}

export interface MeSpecialtyRow {
  code: SpecialtyCode;
  name: string;
  status: "active" | "disabled";
  is_primary: boolean;
  activated_at: string | null;
  disabled_at: string | null;
}

export interface AvailableSpecialty {
  code: SpecialtyCode;
  name: string;
  description: string;
}

const EMPTY_PROFILE: MeProfile = {
  handle: "",
  first_name: "",
  last_name: "",
  display_name: "",
  avatar: null,
  region: null,
  city: "",
  bio: "",
  fun_facts: [],
  surfing_since: null,
  riding_level: "",
  preferred_board_types: [],
  favorite_spot_ids: [],
  interests: [],
  languages: [],
  phone: "",
  birth_date: null,
  private_contacts: "",
  gg_surfer_enabled: false,
  gg_contact_policy: "everyone",
  gg_show_region: true,
  gg_show_age: false,
  birthday_greetings_consent: false,
  show_birthday: false,
};

/** Read the full profile from `Me.raw` (normalizeMe keeps the untouched payload). */
export function profileFromRaw(raw: Record<string, unknown> | null | undefined): MeProfile {
  const p = (raw?.profile ?? {}) as Partial<MeProfile>;
  return {
    ...EMPTY_PROFILE,
    ...p,
    fun_facts: p.fun_facts ?? [],
    preferred_board_types: p.preferred_board_types ?? [],
    favorite_spot_ids: p.favorite_spot_ids ?? [],
    interests: p.interests ?? [],
    languages: p.languages ?? [],
  };
}

export function specialtiesFromRaw(raw: Record<string, unknown> | null | undefined): {
  rows: MeSpecialtyRow[];
  available: AvailableSpecialty[];
} {
  const rows = Array.isArray(raw?.specialties) ? (raw?.specialties as MeSpecialtyRow[]) : [];
  const available = Array.isArray(raw?.available_specialties) ? (raw?.available_specialties as AvailableSpecialty[]) : [];
  return { rows, available };
}

/** PATCH /me body (ProfileUpdateSerializer). */
export interface ProfilePatch {
  handle?: string;
  first_name?: string;
  last_name?: string;
  avatar_id?: UUID | null;
  region_id?: number | null;
  city?: string;
  bio?: string;
  fun_facts?: string[];
  surfing_since?: number | null;
  riding_level?: RidingLevel;
  preferred_board_types?: string[];
  favorite_spot_ids?: UUID[];
  interests?: string[];
  languages?: string[];
  phone?: string;
  birth_date?: string | null;
  private_contacts?: string;
  gg_surfer_enabled?: boolean;
  gg_contact_policy?: ContactPolicy;
  gg_show_region?: boolean;
  gg_show_age?: boolean;
  birthday_greetings_consent?: boolean;
  show_birthday?: boolean;
}

/* ---------------- specialties ---------------- */

export interface SpecialtyWarning {
  code: string;
  message: string;
  count: number | null;
}

export interface SpecialtyActivateResult {
  specialty: MeSpecialtyRow;
  /** instructor_profile | create_workshop | null */
  next_step: string | null;
}

export interface SpecialtyDeactivateResult {
  specialty: MeSpecialtyRow;
  warnings: SpecialtyWarning[];
  unpublished: Array<{ type: string; id: UUID }>;
}

/* ---------------- security / data ---------------- */

export interface TwoFactorState {
  enabled: boolean;
  verified: boolean;
  required: boolean;
}

export interface TwoFactorSetup {
  secret: string;
  otpauth_uri: string;
}

export type ConsentKind =
  | "terms"
  | "privacy"
  | "gg_surfer"
  | "birthday_greetings"
  | "geolocation"
  | "marketing"
  | "guardian";

export interface ConsentRecord {
  id: number | string;
  kind: ConsentKind;
  granted: boolean;
  created_at: string;
}

export interface ConsentsState {
  current: Partial<Record<ConsentKind, boolean>>;
  history: ConsentRecord[];
}

export interface DataExport {
  id: UUID;
  status: "pending" | "ready" | "failed";
  file: Media | null;
  created_at: string;
  completed_at: string | null;
}

export interface DeletionState {
  pending: boolean;
  request: {
    id: UUID;
    status: "requested" | "cancelled" | "completed";
    reason: string;
    scheduled_for: string;
    created_at: string;
    completed_at: string | null;
  } | null;
  grace_days: number;
}

/* ---------------- notifications ---------------- */

export interface NotificationPreference {
  kind: string;
  label: string;
  in_app: boolean;
  email: boolean;
  push: boolean;
  is_default: boolean;
}

export interface UserNotification {
  id: UUID;
  kind: string;
  kind_label: string;
  title: string;
  body: string;
  link: string;
  payload: Record<string, unknown>;
  actor: PublicAccount | null;
  created_at: string;
  read_at: string | null;
  is_read: boolean;
}

export interface AccountBlock {
  account: PublicAccount;
  created_at: string;
}

/* ---------------- favorites (typed cards, ATX-11) ---------------- */

export interface FavoriteCard {
  title: string;
  subtitle: string;
  image: Media | null;
  url: string;
  extra: Record<string, unknown>;
}

export interface FavoriteEntry {
  target_type: FavoriteTargetType;
  target_id: UUID;
  created_at: string;
  card: FavoriteCard;
}

/* ---------------- regions / spots for selects ---------------- */

export interface RegionOption extends RegionRef {
  id: number;
  timezone: string;
}

export interface SpotOption {
  id: UUID;
  slug: string;
  name: string;
  region?: { id?: number; slug: string; name: string } | null;
}

/* ---------------- API ---------------- */

export const accountApi = {
  updateProfile: (patch: ProfilePatch) => api.patch<unknown>("me", patch),
  regions: () => api.get<RegionOption[]>("regions"),
  spots: () => api.get<Paginated<SpotOption>>("spots", { query: { page_size: 100 } }),

  activateSpecialty: (code: SpecialtyCode) => api.put<SpecialtyActivateResult>(`me/specialties/${code}`),
  deactivateSpecialty: (code: SpecialtyCode, unpublish: boolean) =>
    api.delete<SpecialtyDeactivateResult>(`me/specialties/${code}`, { query: unpublish ? { unpublish: 1 } : undefined }),

  changePassword: (old_password: string, new_password: string) =>
    api.post<{ detail: string }>("auth/password-change", { old_password, new_password }),
  resendVerification: () => api.post<{ detail?: string }>("auth/verify-email/resend"),
  twoFactorSetup: () => api.post<TwoFactorSetup>("me/2fa/setup"),
  twoFactorEnable: (code: string) => api.post<TwoFactorState>("me/2fa/enable", { code }),
  twoFactorDisable: (code: string) => api.post<TwoFactorState>("me/2fa/disable", { code }),

  consents: () => api.get<ConsentsState>("me/consents"),
  setConsent: (kind: ConsentKind, granted: boolean) => api.post<ConsentsState>("me/consents", { kind, granted }),

  exports: () => api.get<DataExport[]>("me/exports"),
  requestExport: () => api.post<DataExport>("me/exports"),
  deletion: () => api.get<DeletionState>("me/deletion"),
  requestDeletion: (reason: string) => api.post<DeletionState>("me/deletion", { reason }),
  cancelDeletion: () => api.delete<DeletionState>("me/deletion"),

  notificationPrefs: () => api.get<{ preferences: NotificationPreference[] }>("me/notification-preferences"),
  updateNotificationPrefs: (preferences: Array<Partial<NotificationPreference> & { kind: string }>) =>
    api.put<{ preferences: NotificationPreference[] }>("me/notification-preferences", { preferences }),

  blocks: () => api.get<Paginated<AccountBlock>>("me/blocks", { query: { page_size: 100 } }),
  block: (accountId: UUID) => api.post<AccountBlock>("blocks", { account_id: accountId }),
  unblock: (accountId: UUID) => api.delete(`blocks/${accountId}`),

  notifications: (opts: { unread?: boolean; page?: number; pageSize?: number }) =>
    api.get<Paginated<UserNotification>>("me/notifications", {
      query: { unread: opts.unread ? 1 : undefined, page: opts.page, page_size: opts.pageSize ?? 20 },
    }),
  readNotification: (id: UUID) => api.post<UserNotification>(`me/notifications/${id}/read`),
  readAllNotifications: () => api.post<{ updated: number }>("me/notifications/read-all"),

  favorites: () => api.get<Paginated<FavoriteEntry>>("me/favorites", { query: { page_size: 100 } }),
};

export type { Counters };
