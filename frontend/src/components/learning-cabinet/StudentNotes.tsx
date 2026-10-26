"use client";
/**
 * Teacher notes about a student (SCH-10): progress level + comment, visible to the student or to the team only.
 * Server checks who may write (taught the student) and who may edit/delete (author; managers may delete).
 */
import { useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useState } from "react";
import { errorMessage } from "@/lib/api/errors";
import { lk, notesApi, type StudentNote } from "@/lib/api/learningCabinet";
import { formatDateTime } from "@/lib/format";
import { RIDING_LEVEL_LABELS } from "@/lib/labels";
import { Avatar } from "@/components/ui/Avatar";
import { Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ClampText } from "@/components/ui/ClampText";
import { Checkbox, Select, Textarea } from "@/components/ui/Field";
import { LoadingState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ConfirmDialog } from "./ConfirmDialog";
import { LEVEL_OPTIONS } from "./dictionaries";
import { FormAlert } from "./FormAlert";

interface NoteFormValue {
  comment: string;
  level: string;
  visible: boolean;
}

function NoteForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: NoteFormValue;
  submitLabel: string;
  onSubmit: (v: NoteFormValue) => Promise<void>;
  onCancel?: () => void;
}) {
  const [value, setValue] = useState<NoteFormValue>(initial ?? { comment: "", level: "", visible: true });
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async () => {
    if (!value.comment.trim()) return setError("Напишите комментарий.");
    setPending(true);
    setError(null);
    try {
      await onSubmit({ ...value, comment: value.comment.trim() });
      if (!initial) setValue({ comment: "", level: "", visible: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="lc-note-form">
      <Textarea label="Комментарий преподавателя" value={value.comment} onChange={(e) => setValue({ ...value, comment: e.target.value })} maxLength={4000} rows={3} placeholder="Что получилось, над чем работать дальше" />
      <div className="gv-form-grid">
        <Select label="Уровень сейчас" placeholder="Не указывать" value={value.level} onChange={(e) => setValue({ ...value, level: e.target.value })} options={LEVEL_OPTIONS} />
        <Checkbox label="Показать заметку ученику" description="Иначе её видят только вы и менеджеры школы" checked={value.visible} onChange={(e) => setValue({ ...value, visible: e.target.checked })} />
      </div>
      {error && <FormAlert>{error}</FormAlert>}
      <div className="gv-ac-form-action">
        <Button variant="primary" size="sm" onClick={() => void submit()} loading={pending}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button variant="soft" size="sm" onClick={onCancel} disabled={pending}>
            Отмена
          </Button>
        )}
      </div>
    </div>
  );
}

function NoteItem({ note, canDelete, invalidate }: { note: StudentNote; canDelete: boolean; invalidate: () => void }) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  return (
    <li className="lc-note">
      <div className="lc-note-head">
        <Avatar media={note.author?.avatar} name={note.author?.display_name} size={26} />
        <b>{note.author?.display_name ?? "Автор"}</b>
        <small>{formatDateTime(note.created_at)}</small>
        {note.level && <Tag>{RIDING_LEVEL_LABELS[note.level] ?? note.level}</Tag>}
        <Tag variant="plain" className={note.visible_to_student ? "lc-tag-visible" : "lc-tag-private"} icon={note.visible_to_student ? "views" : "lock"}>
          {note.visible_to_student ? "Видно ученику" : "Только команда"}
        </Tag>
      </div>
      {editing ? (
        <NoteForm
          initial={{ comment: note.comment, level: note.level, visible: note.visible_to_student }}
          submitLabel="Сохранить"
          onCancel={() => setEditing(false)}
          onSubmit={async (v) => {
            await notesApi.update(note.id, { comment: v.comment, level: v.level, visible_to_student: v.visible });
            toast.success("Заметка сохранена");
            setEditing(false);
            invalidate();
          }}
        />
      ) : (
        <ClampText lines={4} className="lc-note-text">
          {note.comment}
        </ClampText>
      )}
      {!editing && (note.can_edit || canDelete) && (
        <div className="lc-note-actions">
          {note.can_edit && (
            <Button variant="link" size="sm" icon="pencil" onClick={() => setEditing(true)}>
              Изменить
            </Button>
          )}
          <Button variant="link" size="sm" icon="trash" onClick={() => setConfirm(true)}>
            Удалить
          </Button>
        </div>
      )}
      <ConfirmDialog
        open={confirm}
        title="Удалить заметку?"
        confirmLabel="Удалить"
        onClose={() => setConfirm(false)}
        onConfirm={() => notesApi.remove(note.id)}
        onDone={() => {
          toast.success("Заметка удалена");
          invalidate();
        }}
      >
        <p>Заметка исчезнет у вас{note.visible_to_student ? " и у ученика" : ""}. Это действие попадёт в журнал.</p>
      </ConfirmDialog>
    </li>
  );
}

/**
 * Notes of one student. `notes` given → rendered as is (instructor list returns them inline), otherwise they are
 * loaded with GET student-notes?student=&organization=.
 */
export function StudentNotes({
  studentId,
  studentName,
  organizationId,
  notes,
  invalidateKey,
  canWrite = true,
  canManage = false,
}: {
  studentId: string;
  studentName: string;
  organizationId?: string;
  notes?: StudentNote[];
  /** key of the list that embeds the notes (refetched after changes) */
  invalidateKey?: QueryKey;
  canWrite?: boolean;
  canManage?: boolean;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: lk.notes({ student: studentId, organization: organizationId }),
    queryFn: () => notesApi.list({ student: studentId, organization: organizationId }),
    enabled: notes === undefined,
  });
  const list = notes ?? query.data ?? [];
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: lk.notesAll });
    if (invalidateKey) void queryClient.invalidateQueries({ queryKey: invalidateKey });
  };

  return (
    <div className="lc-notes" aria-label={`Заметки об ученике ${studentName}`}>
      {notes === undefined && query.isPending ? (
        <LoadingState variant="inline" label="Загружаем заметки…" />
      ) : notes === undefined && query.isError ? (
        <ErrorState compact error={query.error} onRetry={() => void query.refetch()} />
      ) : list.length ? (
        <ul className="lc-note-list">
          {list.map((n) => (
            <NoteItem key={n.id} note={n} canDelete={n.can_edit || canManage} invalidate={invalidate} />
          ))}
        </ul>
      ) : (
        <p className="lc-muted">Заметок пока нет.</p>
      )}
      {canWrite && (
        <NoteForm
          submitLabel="Добавить заметку"
          onSubmit={async (v) => {
            await notesApi.create({
              student_id: studentId,
              organization_id: organizationId ?? null,
              comment: v.comment,
              level: v.level,
              visible_to_student: v.visible,
            });
            toast.success("Заметка добавлена");
            invalidate();
          }}
        />
      )}
    </div>
  );
}
