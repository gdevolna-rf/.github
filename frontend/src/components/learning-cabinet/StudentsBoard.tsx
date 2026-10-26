"use client";
/**
 * Students & attendance (SCH-10, INS-06/10): rows are built by the server from bookings — lessons, completed,
 * no-shows, attendance %, repeat flag, last / next lesson — plus teacher notes. Search and «только повторные».
 */
import { keepPreviousData, useQuery, type QueryKey } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { formatDate, formatNumber, plural, pluralize, WORDS } from "@/lib/format";
import type { StudentRow, StudentsPage } from "@/lib/api/learningCabinet";
import { Avatar } from "@/components/ui/Avatar";
import { Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TextInput } from "@/components/ui/Field";
import { Pagination } from "@/components/ui/Pagination";
import { QueryState } from "@/components/ui/QueryState";
import { Segmented } from "@/components/ui/Segmented";
import { EmptyState, LoadingState } from "@/components/ui/States";
import { StudentNotes } from "./StudentNotes";

const PAGE_SIZE = 20;

function useDebounced<T>(value: T, ms = 350): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function StudentItem({
  row,
  organizationId,
  inlineNotes,
  listKey,
  canWriteNotes,
  canManage,
}: {
  row: StudentRow;
  organizationId?: string;
  inlineNotes: boolean;
  listKey: QueryKey;
  canWriteNotes: boolean;
  canManage: boolean;
}) {
  const [open, setOpen] = useState(false);
  const name = row.student?.display_name || "Ученик";
  const notesCount = inlineNotes ? (row.notes?.length ?? 0) : (row.notes_count ?? 0);
  const id = row.student?.id;
  return (
    <li className="lc-student">
      <div className="lc-student-row">
        <Avatar media={row.student?.avatar} name={name} size={42} />
        <div className="lc-student-main">
          <div className="lc-student-name">
            <strong className="gv-clamp-1" title={name}>
              {name}
            </strong>
            {row.is_repeat && (
              <Tag variant="verified" icon="refresh">
                Повторный ученик
              </Tag>
            )}
          </div>
          <small>
            {pluralize(row.bookings_count, ["запись", "записи", "записей"])} · проведено {row.completed_count} · неявок {row.no_show_count}
            {row.attendance_pct !== null ? ` · посещаемость ${formatNumber(row.attendance_pct)} %` : ""}
          </small>
          <small>
            {row.last_session ? `Последнее: «${row.last_session.title}», ${formatDate(row.last_session.starts_at, { style: "medium" })}` : "Ещё не занимался"}
            {row.next_session_at ? ` · следующее: ${formatDate(row.next_session_at, { style: "medium" })}` : ""}
          </small>
        </div>
        {id && (
          <Button variant="soft" size="sm" icon="pencil" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            Заметки{notesCount ? ` · ${notesCount}` : ""}
          </Button>
        )}
      </div>
      {open && id && (
        <StudentNotes
          studentId={id}
          studentName={name}
          organizationId={organizationId}
          notes={inlineNotes ? (row.notes ?? []) : undefined}
          invalidateKey={listKey}
          canWrite={canWriteNotes}
          canManage={canManage}
        />
      )}
    </li>
  );
}

export function StudentsBoard({
  queryKey,
  fetcher,
  organizationId,
  inlineNotes,
  canWriteNotes = true,
  canManage = false,
  emptyText,
}: {
  queryKey: (q: string, repeat: boolean, page: number) => QueryKey;
  fetcher: (q: { q?: string; repeat?: boolean; page: number; page_size: number }) => Promise<StudentsPage>;
  organizationId?: string;
  /** instructor list embeds notes in every row */
  inlineNotes: boolean;
  canWriteNotes?: boolean;
  canManage?: boolean;
  emptyText?: string;
}) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "repeat">("all");
  const [page, setPage] = useState(1);
  const q = useDebounced(search.trim());
  const repeat = filter === "repeat";
  useEffect(() => setPage(1), [q, repeat]);
  const key = queryKey(q, repeat, page);
  const query = useQuery({
    queryKey: key,
    queryFn: () => fetcher({ q: q || undefined, repeat, page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });
  const summary = query.data?.summary;

  return (
    <div className="lc-students">
      <div className="lc-students-tools">
        <TextInput label="Поиск ученика" hideLabel type="search" placeholder="Имя или @handle" value={search} onChange={(e) => setSearch(e.target.value)} className="lc-search" />
        <Segmented<"all" | "repeat">
          ariaLabel="Какие ученики"
          size="sm"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: "Все" },
            { value: "repeat", label: "Повторные" },
          ]}
        />
      </div>
      {summary && (
        <p className="lc-students-summary">
          Учились у вас: <b>{pluralize(summary.unique_students, WORDS.student)}</b> · повторных: <b>{summary.repeat_students}</b>
          {summary.repeat_students_pct !== null ? ` (${formatNumber(summary.repeat_students_pct)} %)` : ""} · всего с записями: {summary.students_with_bookings}
          <span className="lc-muted"> Повторный — ≥2 проведённых занятия.</span>
        </p>
      )}
      <QueryState
        query={query}
        loading={<LoadingState variant="skeleton" lines={5} label="Загружаем учеников…" />}
        isEmpty={(d) => d.results.length === 0}
        empty={
          <EmptyState
            compact
            title={q || repeat ? "Никого не нашли" : "Учеников пока нет"}
            text={q || repeat ? "Измените поиск или фильтр." : (emptyText ?? "Ученики появятся после подтверждённых записей на занятия.")}
          />
        }
      >
        {(data) => (
          <>
            <ul className="lc-student-list" aria-label={`Ученики: ${data.count} ${plural(data.count, WORDS.student)}`}>
              {data.results.map((row, i) => (
                <StudentItem
                  key={row.student?.id ?? `row-${i}`}
                  row={row}
                  organizationId={organizationId}
                  inlineNotes={inlineNotes}
                  listKey={key}
                  canWriteNotes={canWriteNotes}
                  canManage={canManage}
                />
              ))}
            </ul>
            <Pagination page={page} count={data.count} pageSize={PAGE_SIZE} onChange={setPage} ariaLabel="Страницы учеников" />
          </>
        )}
      </QueryState>
    </div>
  );
}
