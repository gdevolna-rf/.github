/**
 * «Обращения» inbox + chat (fe-account; MSG-01…13, SHO-02/05/06, ATX-09/10/27/28).
 * Shapes: backend/apps/commerce/serializers.py (Inquiry*), apps/messaging/serializers.py (Conversation*, ChatMessage*).
 * Keys reuse the shared heads from keys.ts ("inquiries", "conversations") so realtime events refresh them.
 */
import { api } from "./client";
import { qk } from "./keys";
import type { Counters, Decimal, Media, Paginated, PublicAccount, UUID } from "./types";

export type InquiryStatus = "new" | "in_progress" | "completed" | "declined" | "cancelled";
export type InquiryAction = "accept" | "decline" | "complete" | "cancel";
export type InquiryRoleFilter = "customer" | "shaper" | "school" | "instructor" | "rental";
export type InboxBox = "incoming" | "outgoing";

/** CommercePartyCardSerializer — account or organization. */
export interface PartyCard {
  type: "account" | "organization";
  id: UUID;
  name: string;
  avatar: Media | null;
  logo: Media | null;
  handle: string | null;
  slug: string | null;
  kind: string | null;
  url: string | null;
}

export interface OrgBrief {
  id: UUID;
  name: string;
  kind: string;
  slug: string;
}

/** InquiryContextCardSerializer (MSG-08): built from the snapshot taken at creation. */
export interface ContextCard {
  type: string;
  id: string;
  title: string;
  subtitle: string;
  /** thumbnail URL (public) or null */
  image: string | null;
  url: string | null;
}

export interface LastMessage {
  id: UUID;
  kind: "text" | "system";
  body: string;
  created_at: string;
  sender_name: string | null;
  is_mine: boolean;
}

export interface InquiryListItem {
  id: UUID;
  kind: string;
  kind_label: string;
  status: InquiryStatus;
  status_label: string;
  subject: string;
  created_at: string;
  updated_at: string;
  my_role: "customer" | "provider";
  counterpart: PartyCard | null;
  provider_organization: OrgBrief | null;
  context: ContextCard | null;
  last_message: LastMessage | null;
  unread_count: number;
  conversation_id: UUID | null;
  agreed_amount: Decimal | null;
  currency: string;
  amount_confirmed: boolean;
  actions: InquiryAction[];
}

export interface InquiryHistoryEntry {
  from_status: string;
  from_status_label: string;
  to_status: string;
  to_status_label: string;
  actor: PublicAccount | null;
  comment: string;
  created_at: string;
}

export type MilestoneStatus = "planned" | "done" | "confirmed";

export interface Milestone {
  id: UUID;
  inquiry: UUID;
  title: string;
  amount: Decimal | null;
  due_date: string | null;
  status: MilestoneStatus;
  status_label: string;
  position: number;
  completed_at: string | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SignedMedia extends Media {
  signed_url: string | null;
  signed_thumbnail_url: string | null;
}

export interface InquiryDetail extends InquiryListItem {
  customer: PublicAccount;
  provider: PartyCard | null;
  message: string;
  details: Record<string, unknown> & { photos?: SignedMedia[] };
  snapshot: Record<string, unknown>;
  source_channel: string;
  history: InquiryHistoryEntry[];
  milestones: Milestone[];
  decline_reason: string;
  cancel_reason: string;
  closed_at: string | null;
  can_send_messages: boolean;
  send_blocked_reason: string | null;
  bookings: Array<{ id: UUID; kind: string; status: string; starts_at: string }>;
}

/* ---------------- conversations / messages ---------------- */

export interface ChatMessage {
  id: UUID;
  conversation_id: UUID;
  kind: "text" | "system";
  body: string;
  sender: PublicAccount | null;
  is_mine: boolean;
  is_hidden: boolean;
  client_id: string;
  created_at: string;
  edited_at: string | null;
  attachments: SignedMedia[];
}

export interface MessagePage {
  results: ChatMessage[];
  has_more: boolean;
  has_newer: boolean;
  next_before: UUID | null;
}

export interface ConversationListItem {
  id: UUID;
  kind: "inquiry" | "direct" | "support";
  subject: string;
  inquiry_id: UUID | null;
  inquiry_status: InquiryStatus | null;
  counterpart: PartyCard | null;
  context: ContextCard | null;
  last_message: LastMessage | null;
  unread_count: number;
  is_locked: boolean;
  last_message_at: string | null;
  created_at: string;
}

export interface ConversationParticipant {
  account: PublicAccount;
  role: "customer" | "provider" | "member" | "peer" | "staff";
  organization: OrgBrief | null;
  last_read_at: string | null;
}

export interface ConversationDetail extends ConversationListItem {
  inquiry: {
    id: UUID;
    kind: string;
    kind_label: string;
    status: InquiryStatus;
    status_label: string;
    subject: string;
    my_role: "customer" | "provider";
    actions: InquiryAction[];
    provider_organization: OrgBrief | null;
  } | null;
  participants: ConversationParticipant[];
  my_last_read_at: string | null;
  can_send: boolean;
  send_blocked_reason: "conversation_closed" | "messaging_restricted" | "blocked" | string | null;
}

export interface ReadResult {
  conversation_id: UUID;
  last_read_at: string | null;
  unread_count: number;
  counters: Counters;
}

export interface InquiryListQuery {
  box?: InboxBox;
  role?: InquiryRoleFilter;
  status?: string;
  organization?: string;
  unread?: boolean;
  page?: number;
  page_size?: number;
}

/* ---------------- keys ---------------- */

export const inboxKeys = {
  list: (q: InquiryListQuery) => ["inquiries", "list", q] as const,
  count: (q: InquiryListQuery) => ["inquiries", "count", q] as const,
  detail: (id: string) => qk.inquiry(id),
  directList: ["conversations", "list", "direct"] as const,
  directCount: ["conversations", "count", "direct-unread"] as const,
  conversation: (id: string) => qk.conversation(id),
  messages: (id: string) => qk.messages(id),
};

/* ---------------- API ---------------- */

export const inboxApi = {
  list: (q: InquiryListQuery) =>
    api.get<Paginated<InquiryListItem>>("inquiries", {
      query: {
        box: q.box,
        role: q.role,
        status: q.status,
        organization: q.organization,
        unread: q.unread ? 1 : undefined,
        page: q.page,
        page_size: q.page_size ?? 20,
      },
    }),
  detail: (id: UUID) => api.get<InquiryDetail>(`inquiries/${id}`),
  action: (id: UUID, action: InquiryAction, body: { reason?: string; agreed_amount?: string | null; amount_confirmed?: boolean } = {}) =>
    api.post<InquiryDetail>(`inquiries/${id}/${action}`, body),

  milestones: (id: UUID) => api.get<Milestone[]>(`inquiries/${id}/milestones`),
  addMilestone: (id: UUID, body: { title: string; amount?: string | null; due_date?: string | null }) =>
    api.post<Milestone>(`inquiries/${id}/milestones`, body),
  deleteMilestone: (id: UUID, milestoneId: UUID) => api.delete(`inquiries/${id}/milestones/${milestoneId}`),
  milestoneDone: (milestoneId: UUID) => api.post<Milestone>(`milestones/${milestoneId}/done`),
  milestoneConfirm: (milestoneId: UUID) => api.post<Milestone>(`milestones/${milestoneId}/confirm`),

  conversations: (q: { kind?: "inquiry" | "direct"; unread?: boolean; page?: number; page_size?: number }) =>
    api.get<Paginated<ConversationListItem>>("conversations", {
      query: { kind: q.kind, unread: q.unread ? 1 : undefined, page: q.page, page_size: q.page_size ?? 20 },
    }),
  conversation: (id: UUID) => api.get<ConversationDetail>(`conversations/${id}`),
  messages: (id: UUID, q: { before?: string; after?: string; limit?: number } = {}) =>
    api.get<MessagePage>(`conversations/${id}/messages`, { query: { before: q.before, after: q.after, limit: q.limit ?? 30 } }),
  /**
   * `client_id` makes a repeat harmless (the server returns the existing message), so it doubles as the
   * Idempotency-Key: the API client then retries network/5xx failures automatically (ATX-25).
   */
  send: (id: UUID, body: { body: string; attachment_ids: UUID[]; client_id: string }) =>
    api.post<ChatMessage>(`conversations/${id}/messages`, body, { idempotencyKey: body.client_id }),
  read: (id: UUID, messageId?: UUID) => api.post<ReadResult>(`conversations/${id}/read`, messageId ? { message_id: messageId } : {}),
  openDirect: (accountId: UUID) => api.post<ConversationDetail>("direct-conversations", { account_id: accountId }),
};
