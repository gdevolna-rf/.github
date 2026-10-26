"use client";
/**
 * Workshop publication (TZ 7.1, ACC-15): the server checklist (name, region, specialization, confirmed email),
 * «Опубликовать мастерскую» / «Снять с публикации» and the server's explanation when it refuses
 * (workshop_incomplete, unverified email, suspended by a moderator).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errorMessage, isApiError } from "@/lib/api/errors";
import { shaperApi, shaperKeys, type Workshop } from "@/lib/api/shaper";
import { cx } from "@/lib/cx";
import { routes } from "@/lib/routes";
import { StatusBadge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";

export function WorkshopPublishBox({ workshop, organization, dirty }: { workshop: Workshop; organization?: string | null; dirty?: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const published = workshop.status === "published" || workshop.status === "pending_review";
  const suspended = workshop.status === "suspended";
  const missing = workshop.publish_requirements.filter((r) => !r.ok);

  const mutation = useMutation({
    mutationFn: () => (published ? shaperApi.unpublishWorkshop(workshop.id) : shaperApi.publishWorkshop(workshop.id)),
    onSuccess: (saved) => {
      qc.setQueryData(shaperKeys.workshop(organization), saved);
      void qc.invalidateQueries({ queryKey: shaperKeys.all });
      setError(null);
      toast.success(published ? "Мастерская снята с публикации" : "Мастерская опубликована — она уже в каталоге «По шейперам»");
    },
    onError: (err) => {
      setError(errorMessage(err));
      if (isApiError(err) && err.retryable) toast.error(err, { action: { label: "Повторить", onClick: () => mutation.mutate() } });
    },
  });

  return (
    <section className="card gv-sc-publish" aria-label="Публикация мастерской">
      <h3>
        <Icon name="sparkle" className="ic" size={19} />
        Публикация
      </h3>
      <p className="gv-sc-publish-status">
        <StatusBadge domain="organization" status={workshop.status} />
        {workshop.is_public ? <span>Мастерская видна в каталоге.</span> : <span>Мастерская не видна в каталоге.</span>}
      </p>
      <ul className="gv-sc-checklist" aria-label="Что нужно для публикации">
        {workshop.publish_requirements.map((r) => (
          <li key={r.code} className={cx(r.ok ? "is-ok" : "is-missing")}>
            <Icon name={r.ok ? "check" : "alert"} size={14} />
            <span>
              {r.label}
              <span className="sr-only">{r.ok ? " — готово" : " — не заполнено"}</span>
            </span>
          </li>
        ))}
      </ul>
      {missing.some((m) => m.code === "email_verified") && (
        <p className="form-help">Подтвердите почту по ссылке из письма — без этого публикация недоступна.</p>
      )}
      {suspended ? (
        <p className="gv-sc-form-error" role="alert">
          <Icon name="lock" size={14} /> Мастерская ограничена модератором. Опубликовать её снова можно после решения поддержки.
        </p>
      ) : (
        <>
          <div className="gv-sc-publish-actions">
            <Button
              variant={published ? "soft" : "primary"}
              loading={mutation.isPending}
              disabled={!workshop.can_manage || (!published && dirty)}
              onClick={() => mutation.mutate()}
            >
              {published ? "Снять с публикации" : "Опубликовать мастерскую"}
            </Button>
            {workshop.is_public && (
              <ButtonLink href={routes.shaper(workshop.slug)} variant="link" iconRight="arrow">
                Посмотреть на сайте
              </ButtonLink>
            )}
          </div>
          {!published && dirty && <p className="form-help">Сначала сохраните изменения профиля.</p>}
        </>
      )}
      {error && (
        <p className="gv-sc-form-error" role="alert">
          <Icon name="alert" size={14} /> {error}
        </p>
      )}
    </section>
  );
}
