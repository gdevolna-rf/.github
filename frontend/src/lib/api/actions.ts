/**
 * Cross-domain user actions used from many public pages: inquiries (MSG-03/09, AT-01, AT-03) and complaints
 * (TRUST-07). Shapes: backend/apps/commerce/serializers.py (InquiryCreateSerializer) and
 * backend/apps/trust/serializers.py (ComplaintCreateSerializer).
 */
import { api } from "./client";
import type { UUID } from "./types";

export type InquiryKind =
  | "board_purchase"
  | "custom_order"
  | "repair"
  | "lesson"
  | "program"
  | "rental"
  | "merch"
  | "general";

/** commerce.services.snapshots.TARGET_TYPES */
export type InquiryTargetType =
  | "board_model"
  | "board_variant"
  | "inventory_item"
  | "instructor_offer"
  | "school_program"
  | "lesson_session"
  | "organization"
  | "account";

export interface RepairDetails {
  problem: string;
  desired_date?: string | null;
  photo_ids?: UUID[];
  board?: string;
}

export interface CustomOrderDetails {
  params?: Record<string, string | number | boolean>;
  desired_date?: string | null;
  budget?: string | number | null;
  comment?: string;
}

export interface InquiryCreateInput {
  kind: InquiryKind;
  /** Exactly one of: target_type + target_id, provider_account_id, provider_organization_id. */
  target_type?: InquiryTargetType;
  target_id?: UUID;
  provider_account_id?: UUID;
  provider_organization_id?: UUID;
  message: string;
  details?: RepairDetails | CustomOrderDetails | Record<string, string | number | boolean | null>;
  subject?: string;
  source_channel?: string;
}

/** Minimal part of the inquiry detail returned by POST /inquiries (201). */
export interface CreatedInquiry {
  id: UUID;
  kind: InquiryKind | { code: InquiryKind; label?: string };
  status: string | { code: string; label?: string };
  subject?: string;
  conversation_id?: UUID | null;
  [key: string]: unknown;
}

/** POST /inquiries — `idempotencyKey` is mandatory (create it once per user attempt). */
export function createInquiry(body: InquiryCreateInput, idempotencyKey: string): Promise<CreatedInquiry> {
  return api.post<CreatedInquiry>("inquiries", body, { idempotencyKey });
}

/** trust.Complaint.Target */
export type ComplaintTargetType =
  | "spot"
  | "account"
  | "review"
  | "message"
  | "board_model"
  | "inventory_item"
  | "organization"
  | "media"
  | "club_event";

/** trust.Complaint.Reason */
export type ComplaintReason = "spam" | "fraud" | "offensive" | "wrong_info" | "safety" | "copyright" | "other";

export const COMPLAINT_REASONS: Array<{ value: ComplaintReason; label: string }> = [
  { value: "wrong_info", label: "Недостоверные сведения" },
  { value: "safety", label: "Угроза безопасности" },
  { value: "spam", label: "Спам" },
  { value: "fraud", label: "Мошенничество" },
  { value: "offensive", label: "Оскорбления" },
  { value: "copyright", label: "Нарушение прав" },
  { value: "other", label: "Другое" },
];

export interface ComplaintCreateInput {
  target_type: ComplaintTargetType;
  target_id: UUID;
  reason: ComplaintReason;
  text?: string;
}

export interface CreatedComplaint {
  id: UUID;
  status: string | { code: string; label?: string };
  [key: string]: unknown;
}

/** POST /complaints — 409 `complaint_exists` when the user already reported this object. */
export function createComplaint(body: ComplaintCreateInput): Promise<CreatedComplaint> {
  return api.post<CreatedComplaint>("complaints", body);
}
