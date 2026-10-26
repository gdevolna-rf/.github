"use client";
/**
 * Chat pane (MSG-03/04/05/06/09/10/13, ATX-09/10; SHAPERS_SCREENS §5.5 look): tall log with a gentle «начало
 * переписки» marker at the top, own messages on the right, photo attachments (paperclip → phone gallery,
 * preview, remove before sending), read receipts, report on others' messages, closed state for
 * declined/cancelled inquiries (history stays readable). Writing is allowed before acceptance (BR-06).
 */
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import type { ChatMessage } from "@/lib/api/account-inbox";
import { isApiError } from "@/lib/api/errors";
import { formatDate, formatTime, isoDateInZone } from "@/lib/format";
import { useMe } from "@/lib/auth/hooks";
import { cx } from "@/lib/cx";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { EmptyState, ErrorState, LoadingState, NoAccess } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ReportButton } from "@/components/trust/ReportButton";
import { openPrivateMedia, PrivateImage } from "../shared/PrivateImage";
import { viewerTimeZone } from "../shared/utils";
import { AttachmentStrip } from "./AttachmentStrip";
import { ATTACHMENT_TYPES, MAX_ATTACHMENTS, useAttachmentDrafts } from "./useAttachmentDrafts";
import { useChat, type PendingMessage } from "./useChat";

const CLOSED_TEXT: Record<string, string> = {
  conversation_closed: "Обращение закрыто — отправка сообщений недоступна, история переписки сохранена.",
  blocked: "Переписка недоступна: один из участников заблокировал другого.",
  messaging_restricted: "Отправка сообщений ограничена модератором. История переписки доступна.",
};

function dayLabel(iso: string, tz: string): string {
  const day = isoDateInZone(iso, tz);
  const today = isoDateInZone(new Date(), tz);
  const yesterday = isoDateInZone(Date.now() - 86_400_000, tz);
  if (day === today) return "Сегодня";
  if (day === yesterday) return "Вчера";
  return formatDate(iso, { timeZone: tz, style: new Date(iso).getFullYear() === new Date().getFullYear() ? "dayMonth" : "long" });
}

function Attachments({ message }: { message: ChatMessage }) {
  const toast = useToast();
  if (!message.attachments.length) return null;
  return (
    <ul className={cx("acc-msg-photos", message.attachments.length === 1 && "is-single")}>
      {message.attachments.map((a, i) => (
        <li key={a.id}>
          <button
            type="button"
            className="acc-msg-photo"
            aria-label={`Открыть фото ${i + 1}${a.original_filename ? ` «${a.original_filename}»` : ""}`}
            onClick={() => openPrivateMedia(a).catch((err) => toast.error(err))}
          >
            <PrivateImage media={a} signedUrl={a.signed_thumbnail_url || a.signed_url} alt={a.alt_text || `Фото ${i + 1}`} />
          </button>
        </li>
      ))}
    </ul>
  );
}

function Bubble({ message, read, tz }: { message: ChatMessage; read: boolean; tz: string }) {
  if (message.kind === "system") {
    return (
      <li className="acc-msg-system">
        <span>{message.body}</span>
        <time dateTime={message.created_at}>{formatTime(message.created_at, tz)}</time>
      </li>
    );
  }
  const mine = message.is_mine;
  return (
    <li className={cx("acc-msg", mine ? "is-mine" : "is-theirs")}>
      <div className="acc-msg-bubble">
        {!mine && message.sender && <span className="acc-msg-author">{message.sender.display_name}</span>}
        {message.is_hidden ? (
          <p className="acc-msg-hidden">
            <Icon name="shield" size={13} /> Сообщение скрыто модератором
          </p>
        ) : (
          <>
            {message.body && <p className="acc-msg-text">{message.body}</p>}
            <Attachments message={message} />
          </>
        )}
        <span className="acc-msg-meta">
          <time dateTime={message.created_at}>{formatTime(message.created_at, tz)}</time>
          {mine && (
            <span className={cx("acc-msg-status", read && "is-read")}>
              <Icon name="check" size={12} />
              {read ? "Прочитано" : "Отправлено"}
            </span>
          )}
        </span>
      </div>
      {!mine && !message.is_hidden && (
        <ReportButton targetType="message" targetId={message.id} variant="icon" label="Пожаловаться на сообщение" className="acc-msg-report" />
      )}
    </li>
  );
}

function PendingBubble({ item, onRetry, onDiscard }: { item: PendingMessage; onRetry: () => void; onDiscard: () => void }) {
  return (
    <li className={cx("acc-msg is-mine is-pending", item.status === "failed" && "is-failed")}>
      <div className="acc-msg-bubble">
        {item.body && <p className="acc-msg-text">{item.body}</p>}
        {item.previews.length > 0 && (
          <ul className={cx("acc-msg-photos", item.previews.length === 1 && "is-single")}>
            {item.previews.map((src, i) => (
              <li key={src}>
                <span className="acc-msg-photo">
                  <img src={src} alt={`Фото ${i + 1}`} />
                </span>
              </li>
            ))}
          </ul>
        )}
        <span className="acc-msg-meta" role={item.status === "failed" ? "alert" : "status"}>
          {item.status === "sending" ? (
            <span className="acc-msg-status">
              <Icon name="clock" size={12} /> Отправляем…
            </span>
          ) : (
            <span className="acc-msg-status is-error">
              <Icon name="alert" size={12} /> {item.error ?? "Не отправлено"}
            </span>
          )}
        </span>
        {item.status === "failed" && (
          <span className="acc-msg-retry">
            <button type="button" onClick={onRetry}>
              <Icon name="refresh" size={13} /> Повторить
            </button>
            <button type="button" onClick={onDiscard}>
              Удалить
            </button>
          </span>
        )}
      </div>
    </li>
  );
}

function Composer({ onSend, disabled }: { onSend: (body: string, media: ReturnType<ReturnType<typeof useAttachmentDrafts>["take"]>) => void; disabled?: boolean }) {
  const [text, setText] = useState("");
  const files = useAttachmentDrafts();
  const inputRef = useRef<HTMLInputElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const toast = useToast();
  const empty = !text.trim() && files.readyCount === 0;

  // auto-grow up to ~6 lines
  useLayoutEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  const submit = () => {
    if (disabled) return;
    if (files.uploading) {
      toast.info("Дождитесь загрузки фото — это пара секунд.");
      return;
    }
    if (empty) {
      toast.error("Напишите сообщение или прикрепите фото");
      areaRef.current?.focus();
      return;
    }
    const media = files.take();
    onSend(text, media);
    setText("");
    areaRef.current?.focus();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const coarse = typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)").matches;
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && !coarse) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <form
      className="acc-chat-form"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <AttachmentStrip files={files} />
      <div className="acc-chat-input">
        <button
          type="button"
          className="acc-paperclip"
          aria-label="Прикрепить фото"
          title={`Прикрепить фото (JPG, PNG, WebP, до ${MAX_ATTACHMENTS})`}
          onClick={() => inputRef.current?.click()}
          disabled={disabled || files.drafts.length >= MAX_ATTACHMENTS}
        >
          <Icon name="paperclip" size={20} />
        </button>
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          tabIndex={-1}
          aria-hidden="true"
          accept={ATTACHMENT_TYPES.join(",")}
          multiple
          data-testid="chat-file-input"
          onChange={(e) => {
            files.add(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
        <label htmlFor="chat-message" className="sr-only">
          Сообщение
        </label>
        <textarea
          id="chat-message"
          ref={areaRef}
          className="gv-input acc-chat-textarea"
          rows={1}
          maxLength={4000}
          value={text}
          placeholder="Напишите сообщение или прикрепите фото…"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={disabled}
        />
        <Button type="submit" variant="primary" disabled={disabled} loading={false} aria-disabled={empty || files.uploading || undefined}>
          {files.uploading ? "Загружаем фото…" : "Отправить"}
        </Button>
      </div>
      <p className="acc-chat-hint">
        <span className="acc-hide-coarse">Enter — отправить, Shift + Enter — новая строка. </span>Сообщения видят только участники обращения.
      </p>
    </form>
  );
}

export function ChatView({ conversationId, kind = "inquiry", introText, className, onConversationError }: {
  conversationId: string;
  kind?: "inquiry" | "direct";
  introText?: ReactNode;
  className?: string;
  onConversationError?: (err: unknown) => void;
}) {
  const { me } = useMe();
  const chat = useChat(conversationId, me?.id);
  const logRef = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const [unseen, setUnseen] = useState(0);
  const lastCount = useRef(0);
  const tz = viewerTimeZone();
  const conv = chat.conversation.data;

  useEffect(() => {
    if (chat.conversation.error) onConversationError?.(chat.conversation.error);
  }, [chat.conversation.error, onConversationError]);

  const total = chat.messages.length + chat.pending.length;
  // keep the newest message in view; if the user scrolled up, show «новые сообщения» instead of jumping
  useLayoutEffect(() => {
    const el = logRef.current;
    if (!el) return;
    const grew = total > lastCount.current;
    const first = lastCount.current === 0;
    lastCount.current = total;
    if (!grew) return;
    if (first || nearBottom.current) {
      el.scrollTop = el.scrollHeight;
      setUnseen(0);
    } else {
      setUnseen((n) => n + 1);
    }
  }, [total]);

  const loadOlder = async () => {
    const el = logRef.current;
    const before = el ? el.scrollHeight - el.scrollTop : 0;
    await chat.loadOlder();
    requestAnimationFrame(() => {
      if (el) el.scrollTop = el.scrollHeight - before;
    });
  };

  if (chat.conversation.isPending || (chat.latest.isPending && !chat.latest.data)) {
    return (
      <div className={cx("acc-chat", className)}>
        <LoadingState label="Загружаем переписку…" />
      </div>
    );
  }
  const err = chat.conversation.error ?? (chat.latest.data ? null : chat.latest.error);
  if (err) {
    if (isApiError(err) && err.isForbidden) return <NoAccess text="Эта переписка вам недоступна." />;
    if (isApiError(err) && err.isNotFound) return <EmptyState compact title="Переписка не найдена" text="Возможно, она была удалена или ссылка устарела." />;
    return (
      <ErrorState
        error={err}
        title="Не получилось загрузить переписку"
        onRetry={() => {
          void chat.conversation.refetch();
          void chat.latest.refetch();
        }}
      />
    );
  }

  const canSend = conv?.can_send ?? true;
  const closedText = conv && !canSend ? (CLOSED_TEXT[conv.send_blocked_reason ?? ""] ?? "Отправка сообщений сейчас недоступна.") : null;

  // build the log with day dividers
  const rows: ReactNode[] = [];
  let lastDay = "";
  for (const m of chat.messages) {
    const day = isoDateInZone(m.created_at, tz);
    if (day !== lastDay) {
      rows.push(
        <li key={`d-${day}`} className="acc-msg-day" role="separator">
          <span>{dayLabel(m.created_at, tz)}</span>
        </li>,
      );
      lastDay = day;
    }
    rows.push(<Bubble key={m.id} message={m} tz={tz} read={m.is_mine && chat.othersReadAt >= Date.parse(m.created_at)} />);
  }

  return (
    <section className={cx("acc-chat", className)} aria-label="Переписка">
      <div
        ref={logRef}
        className="acc-chat-log"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Сообщения"
        tabIndex={0}
        onScroll={(e) => {
          const el = e.currentTarget;
          nearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
          if (nearBottom.current && unseen) setUnseen(0);
        }}
      >
        {chat.hasMore ? (
          <div className="acc-chat-older">
            <Button variant="soft" size="sm" icon="chevron-up" loading={chat.olderLoading} onClick={() => void loadOlder()}>
              Показать более ранние
            </Button>
            {chat.olderError && <p className="gv-field-error" role="alert">{chat.olderError}</p>}
          </div>
        ) : (
          <div className="acc-chat-intro">
            <span className="acc-chat-intro-icon" aria-hidden="true">
              <svg viewBox="0 0 120 36" width="120" height="36" className="acc-chat-wave">
                <path d="M2 24c10-10 20-10 30 0s20 10 30 0 20-10 30 0 18 10 26 2" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
                <path d="M14 32c8-6 16-6 24 0s16 6 24 0 16-6 24 0 14 6 20 1" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" opacity=".55" />
              </svg>
              <span className="acc-chat-intro-mail">
                <Icon name="mail" size={22} />
              </span>
            </span>
            <b>Начало переписки</b>
            <p>
              {introText ??
                (kind === "direct"
                  ? "Поздоровайтесь и договоритесь о катании. Сообщения видят только участники диалога."
                  : "Обсудите детали — время, снаряжение, размеры и сроки. Писать можно сразу, даже до ответа исполнителя.")}
            </p>
            <span className="acc-chat-divider">Сообщения</span>
          </div>
        )}
        <div className="acc-chat-spacer" />
        <ol className="acc-chat-list">
          {rows}
          {chat.pending.map((p) => (
            <PendingBubble key={p.clientId} item={p} onRetry={() => chat.retry(p.clientId)} onDiscard={() => chat.discard(p.clientId)} />
          ))}
        </ol>
        {total === 0 && <p className="acc-chat-empty">Сообщений пока нет — напишите первым.</p>}
      </div>
      {unseen > 0 && (
        <button
          type="button"
          className="acc-chat-jump"
          onClick={() => {
            const el = logRef.current;
            if (el) el.scrollTop = el.scrollHeight;
            setUnseen(0);
          }}
        >
          <Icon name="chevron-down" size={14} /> Новые сообщения
        </button>
      )}
      {closedText ? (
        <p className="acc-chat-closed" role="status">
          <Icon name="lock" size={15} /> {closedText}
        </p>
      ) : (
        <Composer
          onSend={(body, media) => {
            nearBottom.current = true;
            chat.send(body, media.media, media.previews);
          }}
        />
      )}
    </section>
  );
}
