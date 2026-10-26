"use client";
/**
 * «Мои направления» (ACC-01/03…05/11/12, 7.1, BR-02/04/11, ATX-17, CABINET_SCREENS §5.6).
 * Подключение — PUT me/specialties/{code} (next_step → куда пойти дальше); отключение — подтверждение с
 * опцией скрыть публичную карточку, затем показываем предупреждения сервера (активные брони, публикации): история,
 * заказы и документы сохраняются. Сёрф-школа — организация, не переключатель. Роли модератора/администратора
 * здесь не показываются вообще (BR-04).
 */
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { accountApi, specialtiesFromRaw, type SpecialtyWarning } from "@/lib/api/account";
import { qk } from "@/lib/api/keys";
import type { SpecialtyCode } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";
import { SPECIALTY_DESCRIPTIONS, SPECIALTY_LABELS, ORGANIZATION_KIND_LABELS, MEMBERSHIP_ROLE_LABELS } from "@/lib/labels";
import { routes } from "@/lib/routes";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Field";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { LoadingState } from "@/components/ui/States";
import { Toggle } from "@/components/ui/Toggle";
import { useToast } from "@/components/ui/Toast";
import { errorMessage } from "@/lib/api/errors";

const ORDER: SpecialtyCode[] = ["surfer", "instructor", "shaper", "rental"];
const ICONS: Record<SpecialtyCode, IconName> = { surfer: "waves", instructor: "clover", shaper: "ruler", rental: "board" };
const TOOLS: Record<SpecialtyCode, string> = {
  surfer: routes.account.diary,
  instructor: routes.account.instructor,
  shaper: routes.account.shaper,
  rental: routes.account.rental,
};
const NEXT_STEP: Record<string, { text: string; href: string; label: string }> = {
  instructor_profile: {
    text: "Заполните карточку инструктора — после публикации она появится в каталоге. Сертификат можно добавить позже.",
    href: `${routes.account.instructor}/profile`,
    label: "Заполнить карточку",
  },
  create_workshop: {
    text: "Создайте мастерскую — в ней появятся модели досок, заказы и статистика.",
    href: routes.account.shaper,
    label: "Создать мастерскую",
  },
};

interface Outcome {
  code: SpecialtyCode;
  kind: "on" | "off";
  nextStep?: string | null;
  warnings?: SpecialtyWarning[];
  unpublished?: number;
}

export function SpecialtiesPage() {
  const { me } = useMe();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState<SpecialtyCode | null>(null);
  const [confirm, setConfirm] = useState<SpecialtyCode | null>(null);
  const [unpublish, setUnpublish] = useState(true);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const { rows, available } = useMemo(() => specialtiesFromRaw(me?.raw), [me]);

  if (!me) return <LoadingState label="Загружаем направления…" />;

  const active = new Set(me.specialties);
  const meta = (code: SpecialtyCode) => available.find((a) => a.code === code);
  const codes = ORDER.filter((c) => available.length === 0 || available.some((a) => a.code === c));
  const disabledRow = (code: SpecialtyCode) => rows.find((r) => r.code === code && r.status === "disabled");
  const refreshMe = () => queryClient.invalidateQueries({ queryKey: qk.me, exact: true });

  const enable = async (code: SpecialtyCode) => {
    setBusy(code);
    try {
      const res = await accountApi.activateSpecialty(code);
      await refreshMe();
      setOutcome({ code, kind: "on", nextStep: res.next_step });
      toast.success(`Направление «${SPECIALTY_LABELS[code]}» подключено`);
    } catch (err) {
      toast.error(err, { action: { label: "Повторить", onClick: () => void enable(code) } });
    } finally {
      setBusy(null);
    }
  };

  const disable = async (code: SpecialtyCode) => {
    setBusy(code);
    setDialogError(null);
    try {
      const res = await accountApi.deactivateSpecialty(code, code === "instructor" && unpublish);
      await refreshMe();
      setConfirm(null);
      setOutcome({ code, kind: "off", warnings: res.warnings, unpublished: res.unpublished.length });
      toast.success(`Направление «${SPECIALTY_LABELS[code]}» отключено`);
    } catch (err) {
      setDialogError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const ownedSchools = me.organizations.filter((o) => o.kind === "school");

  return (
    <section className="gv-ac-panel" aria-labelledby="spec-title">
      <h2 id="spec-title">Мои направления</h2>
      <p className="gv-ac-desc">
        Можно быть сёрфером, инструктором, шейпером и сдавать снаряжение одновременно. Подключение направления не создаёт
        второй аккаунт.
      </p>
      <p className="gv-ac-note">
        Аккаунт <b>@{me.handle}</b> · подключено направлений: <b>{me.specialties.length}</b>. Отключение скрывает
        инструменты направления, но не удаляет историю, заказы, клиентов и документы — их можно вернуть, подключив
        направление снова.
      </p>

      {outcome && (
        <div className={outcome.kind === "on" ? "acc-banner is-ok" : "acc-banner is-warn"} role="status" aria-live="polite">
          <Icon name={outcome.kind === "on" ? "check" : "info"} size={20} />
          <div>
            {outcome.kind === "on" ? (
              <>
                <b>«{SPECIALTY_LABELS[outcome.code]}» подключено.</b>
                <p>{outcome.nextStep && NEXT_STEP[outcome.nextStep] ? NEXT_STEP[outcome.nextStep].text : "Инструменты направления появились в меню кабинета."}</p>
              </>
            ) : (
              <>
                <b>«{SPECIALTY_LABELS[outcome.code]}» отключено.</b>
                {outcome.unpublished ? <p>Публичная карточка скрыта из каталога.</p> : null}
                {outcome.warnings && outcome.warnings.length > 0 ? (
                  <ul className="acc-warnings">
                    {outcome.warnings.map((w) => (
                      <li key={w.code}>{w.message}</li>
                    ))}
                  </ul>
                ) : (
                  <p>Активных броней и публикаций не было — история сохранена.</p>
                )}
              </>
            )}
          </div>
          <div className="acc-banner-actions">
            {outcome.kind === "on" && outcome.nextStep && NEXT_STEP[outcome.nextStep] ? (
              <ButtonLink href={NEXT_STEP[outcome.nextStep].href} variant="primary" iconRight="arrow">
                {NEXT_STEP[outcome.nextStep].label}
              </ButtonLink>
            ) : outcome.kind === "on" ? (
              <ButtonLink href={TOOLS[outcome.code]} variant="soft" iconRight="arrow">
                Открыть раздел
              </ButtonLink>
            ) : (
              <ButtonLink href={`${routes.account.bookings}?box=provider`} variant="soft" iconRight="arrow">
                Бронирования клиентов
              </ButtonLink>
            )}
            <Button variant="link" onClick={() => setOutcome(null)}>
              Скрыть
            </Button>
          </div>
        </div>
      )}

      <ul className="acc-modules" aria-label="Направления аккаунта">
        {codes.map((code) => {
          const on = active.has(code);
          const name = SPECIALTY_LABELS[code];
          const description = meta(code)?.description || SPECIALTY_DESCRIPTIONS[code];
          const locked = code === "surfer" && on;
          const was = disabledRow(code);
          return (
            <li key={code} className="gv-ac-module">
              <span className="gv-ac-module-icon" aria-hidden="true">
                <Icon name={ICONS[code]} size={20} />
              </span>
              <div className="gv-ac-module-copy">
                <strong id={`spec-${code}`}>{name}</strong>
                <p id={`spec-${code}-d`}>
                  {description}
                  {locked ? " · основа аккаунта, не отключается (скрыться из сообщества можно в настройках приватности)." : ""}
                  {!on && was ? " · было подключено раньше — история сохранена." : ""}
                </p>
                {on && code !== "surfer" && (
                  <Link className="acc-module-link" href={TOOLS[code]}>
                    Открыть раздел <Icon name="arrow" size={13} />
                  </Link>
                )}
              </div>
              {busy === code ? (
                <span className="acc-toggle-spinner" role="status" aria-label="Сохраняем…" />
              ) : null}
              <Toggle
                checked={on}
                disabled={locked || busy !== null}
                aria-labelledby={`spec-${code}`}
                aria-describedby={`spec-${code}-d`}
                onChange={(next) => {
                  if (next) void enable(code);
                  else {
                    setUnpublish(true);
                    setDialogError(null);
                    setConfirm(code);
                  }
                }}
              />
            </li>
          );
        })}
        <li className="gv-ac-module">
          <span className="gv-ac-module-icon" aria-hidden="true">
            <Icon name="school" size={20} />
          </span>
          <div className="gv-ac-module-copy">
            <strong>Сёрф-школа</strong>
            <p>
              Школа — отдельная организация с командой, программами и расписанием. Создайте свою или примите приглашение
              владельца.
            </p>
            {ownedSchools.length > 0 && (
              <ul className="acc-org-list">
                {ownedSchools.map((o) => (
                  <li key={o.id}>
                    <Link href={routes.account.org(o.id)}>{o.name}</Link> · {MEMBERSHIP_ROLE_LABELS[o.role] ?? "Участник"}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="acc-module-actions">
            <ButtonLink href={`${routes.account.orgs}?create=school`} variant="soft" icon="plus">
              Создать школу
            </ButtonLink>
            <ButtonLink href={routes.account.invites} variant="link">
              Приглашения
            </ButtonLink>
          </div>
        </li>
        {me.organizations.filter((o) => o.kind !== "school").length > 0 && (
          <li className="gv-ac-module">
            <span className="gv-ac-module-icon" aria-hidden="true">
              <Icon name="brief" size={20} />
            </span>
            <div className="gv-ac-module-copy">
              <strong>Мастерские и прокаты</strong>
              <ul className="acc-org-list">
                {me.organizations
                  .filter((o) => o.kind !== "school")
                  .map((o) => (
                    <li key={o.id}>
                      <Link href={routes.account.org(o.id)}>{o.name}</Link> · {ORGANIZATION_KIND_LABELS[o.kind]} ·{" "}
                      {MEMBERSHIP_ROLE_LABELS[o.role] ?? "Участник"}
                    </li>
                  ))}
              </ul>
            </div>
          </li>
        )}
      </ul>

      <div className="gv-ac-form-action">
        <ButtonLink href={routes.account.root} variant="primary" iconRight="arrow">
          Вернуться в обзор
        </ButtonLink>
      </div>

      <Modal
        open={confirm !== null}
        onClose={() => (busy ? undefined : setConfirm(null))}
        title={confirm ? `Отключить «${SPECIALTY_LABELS[confirm]}»?` : ""}
        description="Инструменты направления исчезнут из меню. История, заказы, клиенты и документы сохранятся; активные брони не отменяются."
        footer={
          <>
            <Button variant="soft" onClick={() => setConfirm(null)} disabled={busy !== null}>
              Оставить
            </Button>
            <Button variant="danger" loading={busy === confirm} onClick={() => confirm && void disable(confirm)}>
              Отключить
            </Button>
          </>
        }
      >
        {confirm === "instructor" && (
          <Checkbox
            label="Скрыть мою карточку инструктора из каталога"
            description="Новые ученики не смогут записаться. Карточку можно снова опубликовать позже."
            checked={unpublish}
            onChange={(e) => setUnpublish(e.target.checked)}
          />
        )}
        {(confirm === "shaper" || confirm === "rental") && (
          <p className="gv-ac-muted">
            Опубликованные {confirm === "shaper" ? "мастерская и модели досок" : "объявления проката"} останутся в каталоге —
            после отключения мы покажем, что ещё опубликовано, и как это скрыть.
          </p>
        )}
        {dialogError && (
          <p className="gv-field-error" role="alert">
            {dialogError}
          </p>
        )}
      </Modal>
    </section>
  );
}
