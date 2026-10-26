"use client";
/**
 * Workshop reference lists (SHP-05/06, ATX-07): standard board types/materials (read-only) + the workshop's own
 * ones (add, rename, delete). A custom type («Фиш», «Мини-малибу»…) immediately appears in the model type select
 * of «Мои доски» — both read the same query (shaperKeys.boardTypes).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { errorMessage, isApiError } from "@/lib/api/errors";
import { shaperApi, shaperKeys, SILHOUETTE_LABELS, SILHOUETTES, silhouetteSrc, type BoardType, type Material } from "@/lib/api/shaper";
import { cx } from "@/lib/cx";
import { Button } from "@/components/ui/Button";
import { Select, TextInput } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";

const silhouetteOptions = SILHOUETTES.map((s) => ({ value: s, label: SILHOUETTE_LABELS[s] ?? s }));

function fieldMessage(err: unknown, field: string): string {
  if (isApiError(err)) return err.fieldError(field) ?? err.message;
  return errorMessage(err);
}

/**
 * A small «form» that can live inside the workshop <form> (no nested forms): Enter in a text field and the
 * button marked `data-submit` call onSubmit; Enter never submits the outer form.
 */
function InlineGroup({ label, onSubmit, className, children }: { label: string; onSubmit: () => void; className?: string; children: ReactNode }) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cx("gv-sc-inline-form", className)}
      onKeyDown={(e) => {
        const target = e.target as HTMLElement;
        if (e.key === "Enter" && target.tagName === "INPUT") {
          e.preventDefault();
          onSubmit();
        }
      }}
      onClick={(e) => {
        const button = (e.target as HTMLElement).closest("button");
        if (button?.hasAttribute("data-submit") && !button.disabled) onSubmit();
      }}
    >
      {children}
    </div>
  );
}

/* ================= board types ================= */

function TypeRow({ type, workshopId, disabled }: { type: BoardType; workshopId: string; disabled?: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(type.name);
  const [silhouette, setSilhouette] = useState(type.silhouette);
  const [error, setError] = useState<string | null>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: shaperKeys.boardTypes(workshopId) });
  const update = useMutation({
    mutationFn: () => shaperApi.updateBoardType(workshopId, type.id, { name: name.trim(), silhouette }),
    onSuccess: () => {
      setEditing(false);
      setError(null);
      toast.success(`Тип «${name.trim()}» сохранён`);
      void invalidate();
      void qc.invalidateQueries({ queryKey: shaperKeys.all });
    },
    onError: (err) => setError(fieldMessage(err, "name")),
  });
  const remove = useMutation({
    mutationFn: () => shaperApi.deleteBoardType(workshopId, type.id),
    onSuccess: () => {
      toast.success(`Тип «${type.name}» удалён`);
      void invalidate();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  if (editing) {
    return (
      <li className="gv-sc-type is-editing">
        <InlineGroup
          label="Переименовать тип"
          onSubmit={() => {
            if (name.trim().length < 2) return setError("Название — от 2 до 40 символов.");
            update.mutate();
          }}
        >
          <TextInput label="Название типа" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} error={error} autoFocus />
          <Select label="Силуэт" value={silhouette} options={silhouetteOptions} onChange={(e) => setSilhouette(e.target.value)} />
          <div className="gv-sc-inline-actions">
            <Button variant="primary" size="sm" loading={update.isPending} data-submit="">
              Сохранить
            </Button>
            <Button
              variant="soft"
              size="sm"
              onClick={() => {
                setEditing(false);
                setName(type.name);
                setSilhouette(type.silhouette);
                setError(null);
              }}
            >
              Отмена
            </Button>
          </div>
        </InlineGroup>
      </li>
    );
  }
  return (
    <li className="gv-sc-type">
      <img src={silhouetteSrc(type.silhouette)} alt="" width={22} height={56} />
      <span className="gv-sc-type-name" title={type.name}>
        {type.name}
        <small>артикул {type.sku_code || "—"}</small>
      </span>
      <button type="button" className="model-menu gv-sc-icon-btn" aria-label={`Переименовать тип «${type.name}»`} onClick={() => setEditing(true)} disabled={disabled}>
        <Icon name="pencil" size={16} />
      </button>
      <button
        type="button"
        className="model-menu gv-sc-icon-btn is-danger"
        aria-label={`Удалить тип «${type.name}»`}
        onClick={() => remove.mutate()}
        disabled={disabled || remove.isPending}
      >
        <Icon name="close" size={16} />
      </button>
      {error && (
        <p className="gv-field-error gv-sc-row-error" role="alert">
          {error}
        </p>
      )}
    </li>
  );
}

export function CustomTypesManager({ workshopId, disabled }: { workshopId: string; disabled?: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: shaperKeys.boardTypes(workshopId), queryFn: () => shaperApi.boardTypes(workshopId) });
  const [name, setName] = useState("");
  const [silhouette, setSilhouette] = useState("custom");
  const [error, setError] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => shaperApi.createBoardType(workshopId, { name: name.trim(), silhouette }),
    onSuccess: (type) => {
      setName("");
      setError(null);
      toast.success(`Тип «${type.name}» добавлен — он уже есть в форме модели`);
      void qc.invalidateQueries({ queryKey: shaperKeys.boardTypes(workshopId) });
    },
    onError: (err) => setError(fieldMessage(err, "name")),
  });
  const submit = () => {
    if (name.trim().length < 2) return setError("Название — от 2 до 40 символов.");
    create.mutate();
  };

  if (query.isPending) return <LoadingState variant="skeleton" lines={2} />;
  if (query.isError) return <ErrorState compact error={query.error} onRetry={() => void query.refetch()} />;
  const standard = query.data.filter((t) => !t.is_custom);
  const custom = query.data.filter((t) => t.is_custom);
  return (
    <div className="gv-sc-catalog">
      <p className="form-help">Стандартные типы доступны всем мастерским:</p>
      <ul className="gv-sc-std-types" aria-label="Стандартные типы досок">
        {standard.map((t) => (
          <li key={t.id} title={t.name}>
            <img src={silhouetteSrc(t.silhouette)} alt="" width={20} height={52} />
            <span>{t.name}</span>
          </li>
        ))}
      </ul>
      <h4 className="gv-sc-subtitle">Свои типы</h4>
      {custom.length ? (
        <ul className="gv-sc-types" aria-label="Свои типы досок">
          {custom.map((t) => (
            <TypeRow key={`${t.id}-${t.name}-${t.silhouette}`} type={t} workshopId={workshopId} disabled={disabled} />
          ))}
        </ul>
      ) : (
        <p className="form-help">Своих типов пока нет — например, «Мини-малибу» или «Софтборд».</p>
      )}
      <InlineGroup className="gv-sc-add-form" onSubmit={submit} label="Добавить свой тип доски">
        <TextInput
          label="Новый тип"
          placeholder="Например, Мини-малибу"
          value={name}
          maxLength={40}
          onChange={(e) => {
            setName(e.target.value);
            setError(null);
          }}
          error={error}
          disabled={disabled}
        />
        <Select label="Силуэт" value={silhouette} options={silhouetteOptions} onChange={(e) => setSilhouette(e.target.value)} disabled={disabled} />
        <Button variant="soft" icon="plus" loading={create.isPending} disabled={disabled} data-submit="">
          Добавить тип
        </Button>
      </InlineGroup>
    </div>
  );
}

/* ================= materials ================= */

function MaterialChip({ material, workshopId, disabled }: { material: Material; workshopId: string; disabled?: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(material.name);
  const [error, setError] = useState<string | null>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: shaperKeys.materials(workshopId) });
  const update = useMutation({
    mutationFn: () => shaperApi.updateMaterial(workshopId, material.id, name.trim()),
    onSuccess: () => {
      setEditing(false);
      setError(null);
      toast.success("Материал сохранён");
      void invalidate();
    },
    onError: (err) => setError(fieldMessage(err, "name")),
  });
  const remove = useMutation({
    mutationFn: () => shaperApi.deleteMaterial(workshopId, material.id),
    onSuccess: () => {
      toast.success(`Материал «${material.name}» удалён`);
      void invalidate();
    },
    onError: (err) => setError(errorMessage(err)),
  });
  if (editing) {
    return (
      <li className="gv-sc-material is-editing">
        <InlineGroup
          label="Переименовать материал"
          onSubmit={() => {
            if (name.trim().length < 2) return setError("Название — от 2 до 50 символов.");
            update.mutate();
          }}
        >
          <TextInput label="Материал" value={name} maxLength={50} onChange={(e) => setName(e.target.value)} error={error} autoFocus />
          <div className="gv-sc-inline-actions">
            <Button variant="primary" size="sm" loading={update.isPending} data-submit="">
              Сохранить
            </Button>
            <Button
              variant="soft"
              size="sm"
              onClick={() => {
                setEditing(false);
                setName(material.name);
                setError(null);
              }}
            >
              Отмена
            </Button>
          </div>
        </InlineGroup>
      </li>
    );
  }
  return (
    <li className="gv-sc-material">
      <span className="gv-sc-material-name" title={material.name}>
        {material.name}
      </span>
      <button type="button" className="gv-sc-chip-btn" aria-label={`Переименовать «${material.name}»`} onClick={() => setEditing(true)} disabled={disabled}>
        <Icon name="pencil" size={13} />
      </button>
      <button type="button" className="gv-sc-chip-btn is-danger" aria-label={`Удалить «${material.name}»`} onClick={() => remove.mutate()} disabled={disabled || remove.isPending}>
        <Icon name="close" size={13} />
      </button>
      {error && (
        <span className="gv-field-error gv-sc-row-error" role="alert">
          {error}
        </span>
      )}
    </li>
  );
}

export function MaterialsManager({ workshopId, disabled }: { workshopId: string; disabled?: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: shaperKeys.materials(workshopId), queryFn: () => shaperApi.materials(workshopId) });
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => shaperApi.createMaterial(workshopId, name.trim()),
    onSuccess: (m) => {
      setName("");
      setError(null);
      toast.success(`Материал «${m.name}» добавлен`);
      void qc.invalidateQueries({ queryKey: shaperKeys.materials(workshopId) });
    },
    onError: (err) => setError(fieldMessage(err, "name")),
  });
  if (query.isPending) return <LoadingState variant="skeleton" lines={2} />;
  if (query.isError) return <ErrorState compact error={query.error} onRetry={() => void query.refetch()} />;
  const standard = query.data.filter((m) => !m.is_custom);
  const custom = query.data.filter((m) => m.is_custom);
  return (
    <div className="gv-sc-catalog">
      <p className="form-help">Стандартные материалы:</p>
      <ul className="gv-sc-chips" aria-label="Стандартные материалы">
        {standard.map((m) => (
          <li key={m.id} className="gv-sc-material is-standard">
            {m.name}
          </li>
        ))}
      </ul>
      <h4 className="gv-sc-subtitle">Свои материалы</h4>
      {custom.length ? (
        <ul className="gv-sc-chips" aria-label="Свои материалы">
          {custom.map((m) => (
            <MaterialChip key={`${m.id}-${m.name}`} material={m} workshopId={workshopId} disabled={disabled} />
          ))}
        </ul>
      ) : (
        <p className="form-help">Добавьте то, с чем работаете: «Стекловолокно», «Био-смола», «Деревянный шпон»…</p>
      )}
      <InlineGroup
        className="gv-sc-add-form"
        label="Добавить свой материал"
        onSubmit={() => {
          if (name.trim().length < 2) return setError("Название — от 2 до 50 символов.");
          create.mutate();
        }}
      >
        <TextInput
          label="Новый материал"
          placeholder="Например, Био-смола"
          value={name}
          maxLength={50}
          onChange={(e) => {
            setName(e.target.value);
            setError(null);
          }}
          error={error}
          disabled={disabled}
        />
        <Button variant="soft" icon="plus" loading={create.isPending} disabled={disabled} data-submit="">
          Добавить материал
        </Button>
      </InlineGroup>
    </div>
  );
}
