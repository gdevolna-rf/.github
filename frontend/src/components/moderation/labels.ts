/**
 * Vocabulary of the moderation domain that labels.ts does not have yet (case kinds, complaint reasons/targets,
 * restriction kinds, audit actions). The server usually sends `{code, label}` — read through choiceLabel()
 * with these dictionaries as the fallback; never print a raw code.
 */
import type { IconName } from "@/components/ui/Icon";
import type { CaseAction, CaseKind } from "@/lib/api/moderation";

export const CASE_KIND_LABELS: Record<CaseKind, string> = {
  spot_change: "Правка спота",
  review: "Отзыв",
  certificate: "Сертификат инструктора",
  complaint: "Жалоба",
  organization: "Публикация организации",
  appeal: "Апелляция",
};

/** Filter tabs of the queue (TRUST-04): short plural labels. */
export const CASE_KIND_FILTERS: Array<{ kind: CaseKind; label: string }> = [
  { kind: "spot_change", label: "Правки спотов" },
  { kind: "review", label: "Отзывы" },
  { kind: "certificate", label: "Сертификаты" },
  { kind: "complaint", label: "Жалобы" },
  { kind: "organization", label: "Организации" },
  { kind: "appeal", label: "Апелляции" },
];

export const CASE_KIND_ICONS: Record<CaseKind, IconName> = {
  spot_change: "map-pin",
  review: "star",
  certificate: "shield",
  complaint: "alert",
  organization: "school",
  appeal: "refresh",
};

export const CASE_STATUS_FILTERS = [
  { value: "open", label: "Открытые и в работе" },
  { value: "in_review", label: "В работе" },
  { value: "resolved", label: "Решённые" },
  { value: "all", label: "Все" },
] as const;

export const COMPLAINT_REASON_LABELS: Record<string, string> = {
  spam: "Спам",
  fraud: "Мошенничество",
  offensive: "Оскорбления",
  wrong_info: "Недостоверные сведения",
  safety: "Угроза безопасности",
  copyright: "Нарушение прав",
  other: "Другое",
};

export const COMPLAINT_TARGET_LABELS: Record<string, string> = {
  spot: "Спот",
  account: "Пользователь",
  review: "Отзыв",
  message: "Сообщение",
  board_model: "Модель доски",
  inventory_item: "Объявление аренды",
  organization: "Организация",
  media: "Медиафайл",
  club_event: "Событие клуба",
};

export const COMPLAINT_ACTION_LABELS: Record<string, string> = {
  none: "Без действий",
  warning: "Предупреждение",
  hidden: "Материал скрыт",
  suspended: "Профиль ограничен",
};

export const COMPLAINT_ACTION_HINTS: Record<string, string> = {
  none: "Жалоба обоснована частично или нарушения нет, но разбор закрыт.",
  warning: "Владелец получит предупреждение; материал остаётся опубликованным.",
  hidden: "Материал будет скрыт с сайта. Для профиля используйте «Профиль ограничен».",
  suspended: "Публикации и сообщения владельца блокируются (бессрочно или до даты).",
};

export const RESTRICTION_KIND_LABELS: Record<string, string> = {
  messaging: "Запрет сообщений",
  publishing: "Запрет публикаций",
  suspended: "Профиль ограничен",
};

export const RESTRICTION_KIND_HINTS: Record<string, string> = {
  messaging: "Нельзя отправлять сообщения и создавать обращения.",
  publishing: "Нельзя публиковать и менять публичные материалы, отзывы, правки спотов.",
  suspended: "Блокирует и публикации, и сообщения. Вход и апелляции остаются доступны.",
};

export const REVIEW_TARGET_LABELS: Record<string, string> = {
  spot: "Спот",
  instructor: "Инструктор",
  organization: "Школа, мастерская или прокат",
};

/** Human names of audit actions (DATA-09); unknown actions are shown as their code in monospace. */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  "spot.change_proposed": "Предложена правка спота",
  "spot.change_resubmitted": "Правка дополнена автором",
  "spot.change_withdrawn": "Правка отозвана автором",
  "spot.change_approved": "Правка принята",
  "spot.change_rejected": "Правка отклонена",
  "spot.change_info_requested": "Запрошены уточнения",
  "spot.change_reverted": "Правка откатана",
  "spot.admin_updated": "Спот изменён в админке",
  "review.submitted": "Отзыв отправлен",
  "review.resubmitted": "Отзыв отправлен повторно",
  "review.revision_submitted": "Автор отправил новую редакцию",
  "review.deleted_by_author": "Отзыв удалён автором",
  "review.admin_updated": "Отзыв изменён в админке",
  "review.admin_deleted": "Отзыв удалён в админке",
  "review.published": "Отзыв опубликован",
  "review.revision_approved": "Новая редакция одобрена",
  "review.rejected": "Отзыв отклонён",
  "review.revision_rejected": "Новая редакция отклонена",
  "review.hidden": "Отзыв скрыт",
  "certificate.uploaded": "Сертификат загружен",
  "certificate.verified": "Сертификат проверен",
  "certificate.rejected": "Сертификат отклонён",
  "certificate.revoked": "Проверка сертификата отозвана",
  "certificate.deleted": "Сертификат удалён",
  "certificate.scan_viewed": "Просмотр скана модератором",
  "certificate.scan_visibility_changed": "Изменён показ скана",
  "organization.created": "Организация создана",
  "organization.updated": "Организация изменена",
  "organization.submitted": "Организация отправлена на проверку",
  "organization.published": "Организация опубликована",
  "organization.rejected": "Публикация отклонена",
  "organization.archived": "Организация в архиве",
  "organization.ownership_transferred": "Передано владение",
  "organization.changed_in_admin": "Организация изменена в админке",
  "complaint.created": "Жалоба подана",
  "complaint.resolved": "Жалоба рассмотрена",
  "complaint.dismissed": "Жалоба отклонена",
  "complaint.appealed": "Подана апелляция",
  "complaint.appeal_granted": "Апелляция удовлетворена",
  "complaint.appeal_denied": "Апелляция отклонена",
  "account.restricted": "Аккаунт ограничен",
  "account.restriction_lifted": "Ограничение снято",
  "account.restriction_admin_updated": "Ограничение изменено в админке",
  "account.2fa_enabled": "Включена 2FA",
  "account.2fa_disabled": "Отключена 2FA",
  "account.2fa_reset_by_admin": "2FA сброшена администратором",
  "account.email_verified": "Email подтверждён",
  "account.password_changed": "Пароль изменён",
  "account.password_reset": "Пароль восстановлен",
  "account.deletion_requested": "Запрошено удаление аккаунта",
  "account.deletion_cancelled": "Удаление аккаунта отменено",
  "account.anonymized": "Аккаунт обезличен",
  "message.viewed_by_moderator": "Сообщение просмотрено модератором",
  "message.hidden": "Сообщение скрыто",
  "message.unhidden": "Сообщение восстановлено",
  "staff_role.granted": "Выдана служебная роль",
  "staff_role.revoked": "Отозвана служебная роль",
  "staff_role.changed_in_admin": "Роль изменена в админке",
  "invite.created": "Отправлено приглашение",
  "invite.accepted": "Приглашение принято",
  "invite.declined": "Приглашение отклонено",
  "invite.revoked": "Приглашение отозвано",
  "membership.revoked": "Доступ сотрудника отозван",
  "membership.left": "Сотрудник вышел из организации",
  "membership.updated": "Роль сотрудника изменена",
  "board_model.hidden": "Модель доски скрыта",
  "profile.handle_changed": "Изменён адрес профиля",
};

export const AUDIT_OBJECT_TYPES: Array<{ value: string; label: string }> = [
  { value: "spots.spot", label: "Спот" },
  { value: "spots.spotchangerequest", label: "Правка спота" },
  { value: "trust.review", label: "Отзыв" },
  { value: "trust.complaint", label: "Жалоба" },
  { value: "learning.instructorcertificate", label: "Сертификат" },
  { value: "organizations.organization", label: "Организация" },
  { value: "accounts.account", label: "Аккаунт" },
  { value: "accounts.staffrole", label: "Служебная роль" },
  { value: "messaging.message", label: "Сообщение" },
];

export const AUDIT_ACTION_PREFIXES: Array<{ value: string; label: string }> = [
  { value: "spot.", label: "Споты и правки" },
  { value: "review.", label: "Отзывы" },
  { value: "certificate.", label: "Сертификаты" },
  { value: "organization.", label: "Организации" },
  { value: "complaint.", label: "Жалобы и апелляции" },
  { value: "account.", label: "Аккаунты и ограничения" },
  { value: "staff_role.", label: "Служебные роли" },
  { value: "invite.", label: "Приглашения" },
  { value: "membership.", label: "Команды организаций" },
  { value: "message.", label: "Сообщения" },
];

export function objectTypeLabel(type: string): string {
  return AUDIT_OBJECT_TYPES.find((t) => t.value === type)?.label ?? type;
}

/** Buttons of the case detail (ATX-28: same verbs everywhere). */
export const CASE_ACTION_LABELS: Record<CaseAction, string> = {
  approve: "Одобрить",
  reject: "Отклонить",
  request_info: "Запросить уточнения",
  revert: "Откатить правку",
  hide: "Скрыть",
  revoke: "Отозвать",
  resolve: "Принять меры",
  dismiss: "Отклонить жалобу",
  appeal_grant: "Удовлетворить апелляцию",
  appeal_deny: "Оставить решение в силе",
};

export const STAFF_ROLE_HINTS: Record<string, string> = {
  moderator: "Очередь модерации, решения по правкам, отзывам, сертификатам, организациям и жалобам. Нужна 2FA.",
  organizer: "Управление событиями и анонсами клуба.",
  admin: "Полный доступ, выдача ролей. Выдаётся только через Django Admin.",
};
