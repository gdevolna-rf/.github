/**
 * What each moderator decision needs (mirrors the backend body serializers, apps/trust/serializers.py):
 *  - spot proposals: `comment` ≤2000, required for reject / request-info;
 *  - reviews, certificates, organizations: `note` ≤300, required for reject / hide / revoke;
 *  - complaints: resolve {action, note?, expires_at?}, dismiss {note?}; appeals {grant, note?}.
 * Used by the decision dialog to label the field, validate before sending and explain the consequence.
 */
import type { CaseAction, CaseKind } from "@/lib/api/moderation";

export interface ActionRule {
  title: string;
  confirm: string;
  description: string;
  field: "comment" | "note";
  fieldLabel: string;
  required: boolean;
  maxLength: number;
  tone: "primary" | "danger" | "neutral";
  placeholder?: string;
}

const NOTE = 300;
const COMMENT = 2000;

export function actionRule(kind: CaseKind | string, action: CaseAction): ActionRule {
  const k = kind === "appeal" ? "complaint" : kind;
  if (k === "spot_change") {
    switch (action) {
      case "approve":
        return {
          title: "Одобрить правку спота",
          confirm: "Одобрить и опубликовать",
          description: "Изменения сразу появятся на публичной карточке спота, дата подтверждения обновится, автор получит уведомление. Решение попадёт в журнал.",
          field: "comment",
          fieldLabel: "Комментарий автору (необязательно)",
          required: false,
          maxLength: COMMENT,
          tone: "primary",
        };
      case "reject":
        return {
          title: "Отклонить правку",
          confirm: "Отклонить",
          description: "Карточка спота не изменится. Автор увидит ваш комментарий в разделе «Мои правки спотов».",
          field: "comment",
          fieldLabel: "Причина отказа",
          required: true,
          maxLength: COMMENT,
          tone: "danger",
          placeholder: "Например: нет подтверждения источником, направление свелла противоречит данным станции…",
        };
      case "request_info":
        return {
          title: "Запросить уточнения",
          confirm: "Отправить запрос",
          description: "Кейс уйдёт из очереди до ответа автора. Автор сможет изменить предложение и отправить его снова.",
          field: "comment",
          fieldLabel: "Что нужно уточнить",
          required: true,
          maxLength: COMMENT,
          tone: "neutral",
          placeholder: "Например: приложите фото с берега или ссылку на источник.",
        };
      case "revert":
        return {
          title: "Откатить принятую правку",
          confirm: "Откатить",
          description: "Поля спота вернутся к значениям до этой правки; фото и источник, добавленные при одобрении, будут убраны. Автор получит уведомление.",
          field: "comment",
          fieldLabel: "Причина отката (необязательно)",
          required: false,
          maxLength: COMMENT,
          tone: "danger",
        };
      default:
        break;
    }
  }
  const base = { field: "note" as const, maxLength: NOTE };
  switch (`${k}:${action}`) {
    case "review:approve":
      return { ...base, title: "Опубликовать отзыв", confirm: "Опубликовать", description: "Отзыв (или новая редакция) появится на карточке, рейтинг объекта пересчитается по опубликованным отзывам.", fieldLabel: "Заметка (необязательно)", required: false, tone: "primary" };
    case "review:reject":
      return { ...base, title: "Отклонить отзыв", confirm: "Отклонить", description: "Отзыв не будет опубликован; для новой редакции опубликованная версия сохранится. Автор увидит причину.", fieldLabel: "Причина для автора", required: true, tone: "danger" };
    case "review:hide":
      return { ...base, title: "Скрыть отзыв", confirm: "Скрыть", description: "Отзыв исчезнет с сайта, рейтинг объекта пересчитается. Автор увидит причину.", fieldLabel: "Причина скрытия", required: true, tone: "danger" };
    case "certificate:approve":
      return { ...base, title: "Подтвердить сертификат", confirm: "Подтвердить", description: "На карточке инструктора появится значок «Сертификат проверен».", fieldLabel: "Заметка (необязательно)", required: false, tone: "primary" };
    case "certificate:reject":
      return { ...base, title: "Отклонить сертификат", confirm: "Отклонить", description: "Значок «проверен» не появится. Инструктор увидит причину и сможет загрузить документ снова.", fieldLabel: "Причина для инструктора", required: true, tone: "danger" };
    case "certificate:revoke":
      return { ...base, title: "Отозвать проверку сертификата", confirm: "Отозвать", description: "Значок «Сертификат проверен» будет снят с карточки инструктора.", fieldLabel: "Причина отзыва", required: true, tone: "danger" };
    case "organization:approve":
      return { ...base, title: "Опубликовать организацию", confirm: "Опубликовать", description: "Карточка появится в публичном каталоге; владелец и команда получат уведомление.", fieldLabel: "Заметка (необязательно)", required: false, tone: "primary" };
    case "organization:reject":
      return { ...base, title: "Отклонить публикацию", confirm: "Отклонить", description: "Организация вернётся в черновики; владелец увидит, что исправить.", fieldLabel: "Что исправить", required: true, tone: "danger" };
    case "complaint:resolve":
      return { ...base, title: "Принять меры по жалобе", confirm: "Применить решение", description: "Все открытые жалобы на этот объект будут закрыты тем же решением; авторы жалоб и владелец получат уведомления.", fieldLabel: "Комментарий (увидит владелец)", required: false, tone: "primary" };
    case "complaint:dismiss":
      return { ...base, title: "Отклонить жалобу", confirm: "Отклонить жалобу", description: "Жалоба будет закрыта без мер; автор жалобы получит уведомление.", fieldLabel: "Заметка (необязательно)", required: false, tone: "neutral" };
    case "complaint:appeal_grant":
      return { ...base, title: "Удовлетворить апелляцию", confirm: "Снять меру", description: "Применённая мера будет снята: материал восстановлен, ограничение профиля снято.", fieldLabel: "Комментарий для владельца", required: false, tone: "primary" };
    case "complaint:appeal_deny":
      return { ...base, title: "Оставить решение в силе", confirm: "Отклонить апелляцию", description: "Мера останется в силе; владелец получит уведомление с вашим комментарием.", fieldLabel: "Комментарий для владельца", required: false, tone: "danger" };
    default:
      return { ...base, title: "Решение", confirm: "Подтвердить", description: "", fieldLabel: "Комментарий", required: false, tone: "neutral" };
  }
}

/** Order of the buttons: positive first, destructive last. */
const ORDER: CaseAction[] = ["approve", "resolve", "appeal_grant", "request_info", "dismiss", "appeal_deny", "reject", "hide", "revoke", "revert"];

export function sortActions(actions: CaseAction[]): CaseAction[] {
  return [...actions].sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b));
}

/** Validate the comment before sending; returns a Russian error or null. */
export function validateDecisionText(rule: ActionRule, text: string): string | null {
  const t = text.trim();
  if (rule.required && !t) return rule.field === "comment" ? "Напишите комментарий для автора." : "Укажите причину — её увидит автор.";
  if (t.length > rule.maxLength) return `Не длиннее ${rule.maxLength} символов.`;
  return null;
}

export const RESOLUTION_LABELS: Record<string, string> = {
  approved: "Принято",
  published: "Опубликовано",
  verified: "Сертификат проверен",
  rejected: "Отклонено",
  needs_info: "Запрошены уточнения",
  withdrawn: "Отозвано автором",
  hidden: "Скрыто",
  revoked: "Проверка отозвана",
  none: "Без мер",
  warning: "Предупреждение",
  suspended: "Профиль ограничен",
  dismissed: "Жалоба отклонена",
  appeal_granted: "Апелляция удовлетворена",
  appeal_denied: "Апелляция отклонена",
};
