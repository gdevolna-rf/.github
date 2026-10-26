"use client";
/**
 * Организации пользователя (ACC-11, SCH-01/03): список членств, создание школы/проката и оболочка кабинета
 * с вкладками-URL. Права определяет сервер (organizations/{id}/manage → 403 для не-менеджеров).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { orgApi, sk, type MyMembership, type OrgManage } from "@/lib/api/schoolCabinet";
import { qk } from "@/lib/api/keys";
import { isApiError } from "@/lib/api/errors";
import { routes } from "@/lib/routes";
import { MEMBERSHIP_ROLE_LABELS, ORGANIZATION_KIND_LABELS } from "@/lib/labels";
import { useMe } from "@/lib/auth/hooks";
import {
  Avatar,
  Button,
  ButtonLink,
  Card,
  CardHeader,
  EmptyState,
  NavTabs,
  NoAccess,
  QueryState,
  Segmented,
  StatusBadge,
  TextInput,
  useToast,
} from "@/components/ui";

export const orgTabs = (id: string, manage: boolean) => {
  const base = routes.account.org(id);
  const all = [
    { href: base, label: "Обзор", manage: false },
    { href: `${base}/profile`, label: "Профиль школы", manage: true },
    { href: `${base}/programs`, label: "Программы", manage: true },
    { href: `${base}/schedule`, label: "Расписание", manage: true },
    { href: `${base}/students`, label: "Ученики", manage: true },
    { href: `${base}/team`, label: "Команда", manage: false },
    { href: `${base}/equipment`, label: "Оборудование", manage: true },
    { href: `${base}/inquiries`, label: "Обращения", manage: true },
    { href: `${base}/analytics`, label: "Аналитика", manage: true },
    { href: `${base}/reviews`, label: "Отзывы", manage: false },
  ];
  return all.filter((t) => manage || !t.manage);
};

function CreateOrgForm() {
  const toast = useToast();
  const router = useRouter();
  const qc = useQueryClient();
  const [kind, setKind] = useState<"school" | "rental">("school");
  const [name, setName] = useState("");
  const create = useMutation({
    mutationFn: () => orgApi.create({ kind, name }),
    onSuccess: (org) => {
      toast.success(kind === "school" ? "Школа создана — заполните профиль" : "Прокат создан — заполните профиль");
      void qc.invalidateQueries({ queryKey: qk.me });
      void qc.invalidateQueries({ queryKey: qk.myOrganizations });
      router.push(`${routes.account.org(org.id)}/profile`);
    },
  });
  return (
    <form
      className="lc-inline-form"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <Segmented
        ariaLabel="Тип организации"
        value={kind}
        onChange={(v) => setKind(v as "school" | "rental")}
        options={[
          { value: "school", label: "Сёрф-школа" },
          { value: "rental", label: "Прокат" },
        ]}
      />
      <TextInput label="Название" required value={name} onChange={(e) => setName(e.target.value)} maxLength={160} />
      <Button type="submit" variant="primary" loading={create.isPending} disabled={name.trim().length < 2}>
        Создать
      </Button>
      {create.isError && (
        <p className="gv-field-error" role="alert">
          {isApiError(create.error) ? create.error.message : "Не удалось создать организацию."}
        </p>
      )}
    </form>
  );
}

export function OrgsPage() {
  const list = useQuery({ queryKey: qk.myOrganizations, queryFn: orgApi.mine });
  return (
    <section className="gv-ac-panel" aria-labelledby="orgs-title">
      <CardHeader
        title={<span id="orgs-title">Школы и организации</span>}
        description="Сёрф-школа и прокат — организации с командой и общими данными. Мастерская шейпера создаётся в кабинете шейпера."
      />
      <QueryState
        query={list}
        isEmpty={(d) => d.length === 0}
        empty={<EmptyState compact title="Вы пока не состоите в организациях" text="Создайте школу или примите приглашение от владельца." />}
      >
        {(items: MyMembership[]) => (
          <ul className="lc-list">
            {items.map((m) => (
              <li key={m.membership_id} className="lc-list-row">
                <Avatar media={m.organization.logo} name={m.organization.name} size={44} />
                <div className="lc-grow">
                  <strong>{m.organization.name}</strong>
                  <div className="small muted">
                    {ORGANIZATION_KIND_LABELS[m.organization.kind]} · {MEMBERSHIP_ROLE_LABELS[m.role]}
                    {m.organization.region ? ` · ${m.organization.region.name}` : ""}
                  </div>
                </div>
                {m.organization.status && <StatusBadge domain="organization" status={m.organization.status} />}
                <ButtonLink
                  href={m.organization.kind === "workshop" ? `${routes.account.shaper}?organization=${m.organization.id}` : routes.account.org(m.organization.id)}
                  variant="soft"
                  iconRight="arrow"
                >
                  Открыть
                </ButtonLink>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
      <Card variant="panel">
        <CardHeader title="Создать школу или прокат" description="Вы станете владельцем и сможете пригласить менеджеров и инструкторов по email." />
        <CreateOrgForm />
      </Card>
    </section>
  );
}

/** Загружает закрытую карточку организации; не-менеджеры получают урезанный набор вкладок. */
export function OrgShell({ id, pathname, children }: { id: string; pathname: string; children: (org: OrgManage | null, role: string | null) => ReactNode }) {
  const { me } = useMe();
  const membership = me?.organizations.find((o) => o.id === id);
  const manage = useQuery({ queryKey: sk.manage(id), queryFn: () => orgApi.manage(id), retry: false, enabled: Boolean(membership) });
  if (!me) return null;
  if (!membership) {
    return <NoAccess title="Нет доступа к организации" text="Вы не состоите в этой организации или доступ был отозван." action={{ label: "Мои организации", href: routes.account.orgs }} />;
  }
  const canManage = manage.isSuccess;
  const forbidden = manage.isError && isApiError(manage.error) && manage.error.isForbidden;
  const org = manage.data ?? null;
  return (
    <section className="gv-ac-panel lc-workspace" aria-labelledby="org-title">
      <div className="gv-card-head">
        <div className="gv-card-head-text">
          <div className="gv-ac-kicker">
            {ORGANIZATION_KIND_LABELS[membership.kind]} · {MEMBERSHIP_ROLE_LABELS[membership.role as keyof typeof MEMBERSHIP_ROLE_LABELS] ?? membership.role}
          </div>
          <h2 id="org-title">{membership.name}</h2>
          {org && (
            <p className="gv-ac-desc">
              <StatusBadge domain="organization" status={org.status} /> {org.moderation_note && <span>Комментарий модератора: {org.moderation_note}</span>}
            </p>
          )}
        </div>
        <div className="gv-card-head-actions">
          {org?.status === "published" && (
            <ButtonLink href={membership.kind === "school" ? routes.school(org.slug) : `${routes.rentals}?organization=${org.slug}`} variant="soft" iconRight="arrow">
              Посмотреть на сайте
            </ButtonLink>
          )}
        </div>
      </div>
      <NavTabs ariaLabel="Разделы организации" current={pathname} items={orgTabs(id, canManage).map(({ href, label }) => ({ href, label }))} />
      {manage.isPending ? null : manage.isError && !forbidden ? (
        <QueryState query={manage}>{() => null}</QueryState>
      ) : (
        <div className="lc-tab-body">{children(org, membership.role)}</div>
      )}
    </section>
  );
}
