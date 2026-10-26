"use client";
/**
 * Приватность и сообщество: GG Surfer — отдельное согласие 18+ (ACC-06, BR-12, COM-01), политика контактов и
 * видимость региона/возраста (COM-07), геолокация — отдельное согласие (COM-08), поздравления с днём рождения и
 * показ дня рождения (COM-05). Каждый переключатель сохраняется сразу, с откатом при ошибке.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import Link from "next/link";
import { accountApi, accountKeys, profileFromRaw, type ConsentKind, type ConsentsState, type ProfilePatch } from "@/lib/api/account";
import { normalizeMe, type Me } from "@/lib/api/auth";
import { qk } from "@/lib/api/keys";
import { routes } from "@/lib/routes";
import { Checkbox } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Segmented";
import { ToggleRow } from "@/components/ui/Toggle";
import { useToast } from "@/components/ui/Toast";
import { age } from "../shared/utils";

export function PrivacySection({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const profile = useMemo(() => profileFromRaw(me.raw), [me]);
  const [ggConfirm, setGgConfirm] = useState(false);
  const [adult, setAdult] = useState(false);
  const years = age(profile.birth_date);

  const consents = useQuery({ queryKey: accountKeys.consents, queryFn: accountApi.consents });

  const patchProfile = useMutation({
    mutationFn: (patch: ProfilePatch) => accountApi.updateProfile(patch),
    onMutate: async (patch) => {
      await queryClient.cancelQueries({ queryKey: qk.me, exact: true });
      const previous = queryClient.getQueryData<Me | null>(qk.me);
      if (previous) {
        const raw = { ...previous.raw, profile: { ...(previous.raw.profile as object), ...patch } };
        queryClient.setQueryData(qk.me, normalizeMe(raw));
      }
      return { previous };
    },
    onError: (err, patch, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(qk.me, ctx.previous);
      toast.error(err, { action: { label: "Повторить", onClick: () => patchProfile.mutate(patch) } });
    },
    onSuccess: (raw) => {
      queryClient.setQueryData(qk.me, normalizeMe(raw));
      void queryClient.invalidateQueries({ queryKey: accountKeys.consents });
      toast.success("Настройка сохранена");
    },
  });

  const setConsent = useMutation({
    mutationFn: ({ kind, granted }: { kind: ConsentKind; granted: boolean }) => accountApi.setConsent(kind, granted),
    onMutate: async ({ kind, granted }) => {
      await queryClient.cancelQueries({ queryKey: accountKeys.consents });
      const previous = queryClient.getQueryData<ConsentsState>(accountKeys.consents);
      if (previous) queryClient.setQueryData(accountKeys.consents, { ...previous, current: { ...previous.current, [kind]: granted } });
      return { previous };
    },
    onError: (err, vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(accountKeys.consents, ctx.previous);
      toast.error(err, { action: { label: "Повторить", onClick: () => setConsent.mutate(vars) } });
    },
    onSuccess: (data) => {
      queryClient.setQueryData(accountKeys.consents, data);
      toast.success("Согласие обновлено");
    },
  });

  const toggleGg = (on: boolean) => {
    if (!on) {
      patchProfile.mutate({ gg_surfer_enabled: false });
      return;
    }
    if (years !== null && years < 18) {
      toast.error("GG Surfer доступен только участникам от 18 лет.");
      return;
    }
    setAdult(years !== null && years >= 18);
    setGgConfirm(true);
  };

  const ggOff = !profile.gg_surfer_enabled;
  const current = consents.data?.current ?? {};

  return (
    <section id="privacy" className="gv-ac-panel acc-settings-section" aria-labelledby="privacy-title">
      <h2 id="privacy-title">Приватность и сообщество</h2>
      <p className="gv-ac-desc">
        Общие предпочтения для всех направлений. Административные права не выдаются через подключение специальности.
      </p>

      <ToggleRow
        icon="heart"
        title="GG Surfer"
        description="Появляться в поиске сообщества, находить компанию для катания. Отдельное согласие для участников от 18 лет — его можно выключить без потери аккаунта."
        checked={profile.gg_surfer_enabled}
        onChange={toggleGg}
        disabled={patchProfile.isPending}
      />
      <div className={ggOff ? "acc-sub-settings is-off" : "acc-sub-settings"} aria-disabled={ggOff || undefined}>
        <div className="acc-setting-line">
          <div>
            <b id="gg-contact-label">Кто может написать мне в GG Surfer</b>
            <p className="gv-ac-muted">Обращения к вашим услугам (занятия, доски, аренда) приходят всегда.</p>
          </div>
          <Segmented
            ariaLabel="Кто может написать мне в GG Surfer"
            size="sm"
            value={profile.gg_contact_policy}
            onChange={(v) => patchProfile.mutate({ gg_contact_policy: v })}
            options={[
              { value: "everyone", label: "Все участники", disabled: ggOff },
              { value: "nobody", label: "Никто", disabled: ggOff },
            ]}
          />
        </div>
        <ToggleRow
          icon="map-pin"
          title="Показывать регион в анкете"
          description="Только регион — без точного адреса и истории перемещений."
          checked={profile.gg_show_region}
          onChange={(v) => patchProfile.mutate({ gg_show_region: v })}
          disabled={ggOff || patchProfile.isPending}
        />
        <ToggleRow
          icon="user"
          title="Показывать возраст"
          description="Участники увидят возраст, но не дату рождения."
          checked={profile.gg_show_age}
          onChange={(v) => patchProfile.mutate({ gg_show_age: v })}
          disabled={ggOff || patchProfile.isPending}
        />
      </div>

      <ToggleRow
        icon="target"
        title="Геолокация"
        description="Разрешить использовать местоположение устройства (например, «споты рядом»). Факты посещения не раскрывают вашу историю перемещений."
        checked={Boolean(current.geolocation)}
        onChange={(v) => setConsent.mutate({ kind: "geolocation", granted: v })}
        disabled={consents.isPending || setConsent.isPending}
      />
      <ToggleRow
        icon="sparkle"
        title="Поздравления с днём рождения"
        description="Короткое поздравление от проекта в день рождения. Дата не раскрывается другим участникам."
        checked={profile.birthday_greetings_consent}
        onChange={(v) => patchProfile.mutate({ birthday_greetings_consent: v })}
        disabled={patchProfile.isPending}
      />
      <ToggleRow
        icon="calendar"
        title="Показывать день рождения"
        description="Участники GG Surfer увидят день и месяц (без года), чтобы поздравить вас."
        checked={profile.show_birthday}
        onChange={(v) => patchProfile.mutate({ show_birthday: v })}
        disabled={patchProfile.isPending}
      />
      {!profile.birth_date && (profile.birthday_greetings_consent || profile.show_birthday) && (
        <p className="gv-ac-note">
          Чтобы поздравление пришло вовремя, укажите дату рождения в <Link href={routes.account.profile}>профиле</Link> — она
          остаётся закрытой.
        </p>
      )}
      <ToggleRow
        icon="mail"
        title="Новости и рассылки проекта"
        description="События клуба и новости ГДеволны. Можно отключить в любой момент."
        checked={Boolean(current.marketing)}
        onChange={(v) => setConsent.mutate({ kind: "marketing", granted: v })}
        disabled={consents.isPending || setConsent.isPending}
      />

      <Modal
        open={ggConfirm}
        onClose={() => setGgConfirm(false)}
        title="Включить GG Surfer?"
        description="Ваша анкета (имя, фото, уровень, интересы и «О себе») появится в поиске сообщества. Закрытые данные не показываются."
        footer={
          <>
            <Button variant="soft" onClick={() => setGgConfirm(false)}>
              Не сейчас
            </Button>
            <Button
              variant="primary"
              disabled={!adult}
              onClick={() => {
                setGgConfirm(false);
                patchProfile.mutate({ gg_surfer_enabled: true });
              }}
            >
              Включить
            </Button>
          </>
        }
      >
        <Checkbox
          label="Мне исполнилось 18 лет"
          description="GG Surfer — сообщество для взрослых участников. Согласие можно отозвать в любой момент."
          checked={adult}
          onChange={(e) => setAdult(e.target.checked)}
          data-autofocus
        />
      </Modal>
    </section>
  );
}
