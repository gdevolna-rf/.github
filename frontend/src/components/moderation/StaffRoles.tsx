"use client";
/**
 * /moderation/staff — admins only (BR-04, TRUST-06, DATA-09): grant / revoke server roles «Модератор» and
 * «Организатор клуба» by e-mail with an explicit confirmation; the history of revoked roles stays visible.
 * Admin roles are granted only through Django Admin (not from the site UI).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { isApiError } from "@/lib/api/errors";
import { modKeys, staffApi, type GrantableRole, type StaffRoleRecord } from "@/lib/api/moderation";
import { useMe } from "@/lib/auth/hooks";
import { STAFF_ROLE_LABELS } from "@/lib/labels";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox, Select, TextInput } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { QueryState } from "@/components/ui/QueryState";
import { EmptyState, NoAccess } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { PersonLine, When } from "./Bits";
import { useModQuery } from "./hooks";
import { STAFF_ROLE_HINTS } from "./labels";

const GRANTABLE: GrantableRole[] = ["moderator", "organizer"];
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function roleLabel(role: string): string {
  return STAFF_ROLE_LABELS[role as keyof typeof STAFF_ROLE_LABELS] ?? role;
}

type Pending = { type: "grant"; email: string; role: GrantableRole } | { type: "revoke"; record: StaffRoleRecord };

export function StaffRoles() {
  const { me } = useMe();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [showRevoked, setShowRevoked] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<GrantableRole>("moderator");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);

  const q = useModQuery({ queryKey: modKeys.staffRoles(showRevoked), queryFn: () => staffApi.roles(showRevoked), enabled: Boolean(me?.isAdmin) });

  const m = useMutation({
    mutationFn: async (p: Pending) => (p.type === "grant" ? staffApi.grant(p.email, p.role) : staffApi.revoke(p.record.id)),
    onSuccess: (_r, p) => {
      toast.success(p.type === "grant" ? `Роль «${roleLabel(p.role)}» выдана` : `Роль «${roleLabel(p.record.role)}» отозвана`);
      if (p.type === "grant") setEmail("");
      setPending(null);
      void queryClient.invalidateQueries({ queryKey: ["moderation", "staff-roles"] });
    },
  });

  if (!me?.isAdmin) {
    return <NoAccess text="Выдавать и отзывать служебные роли могут только администраторы." />;
  }

  const ask = (e: FormEvent) => {
    e.preventDefault();
    const v = email.trim();
    if (!EMAIL_RE.test(v)) {
      setEmailError("Введите email аккаунта, которому выдаёте роль.");
      return;
    }
    setEmailError(null);
    m.reset();
    setPending({ type: "grant", email: v, role });
  };

  const apiErr = isApiError(m.error) ? m.error : null;

  return (
    <section className="gv-ac-panel gv-mod-panel" aria-labelledby="staff-title">
      <div className="gv-card-head">
        <div className="gv-card-head-text">
          <h2 id="staff-title">Служебные роли</h2>
          <p className="gv-ac-desc">Роли выдаются только здесь и только администратором; переключателей в кабинете для них нет. Каждое действие попадает в журнал.</p>
        </div>
      </div>

      <form className="gv-mod-grant" onSubmit={ask} noValidate aria-label="Выдать роль">
        <TextInput label="Email аккаунта" type="email" autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} error={emailError} required maxLength={254} />
        <Select
          label="Роль"
          value={role}
          onChange={(e) => setRole(e.target.value as GrantableRole)}
          options={GRANTABLE.map((r) => ({ value: r, label: roleLabel(r) }))}
          hint={STAFF_ROLE_HINTS[role]}
        />
        <div className="gv-mod-grant-submit">
          <Button type="submit" variant="primary" icon="plus">
            Выдать роль
          </Button>
        </div>
      </form>

      <div className="gv-mod-staff-head">
        <h3>Выданные роли</h3>
        <Checkbox label="Показать отозванные" checked={showRevoked} onChange={(e) => setShowRevoked(e.target.checked)} />
      </div>
      <QueryState query={q} isEmpty={(d) => d.length === 0} empty={<EmptyState compact title="Служебных ролей нет" />}>
        {(rows) => (
          <ul className="gv-mod-rows gv-mod-staff">
            {rows.map((r) => {
              const revoked = Boolean(r.revoked_at);
              const self = r.account.id === me.id;
              const isAdminRole = r.role === "admin";
              return (
                <li key={r.id} className={revoked ? "is-revoked" : undefined}>
                  <div className="gv-mod-row-main">
                    <PersonLine person={r.account} role={r.account_email} />
                    <div className="gv-mod-tags">
                      <Badge tone={revoked ? "muted" : "verified"} icon="shield">
                        {roleLabel(r.role)}
                      </Badge>
                      {!r.two_factor_enabled && !revoked && r.role !== "organizer" && <Badge tone="new">2FA не включена</Badge>}
                      {revoked && <Badge tone="muted">Отозвана</Badge>}
                    </div>
                    <small>
                      Выдана <When value={r.granted_at} />
                      {r.granted_by ? ` · ${r.granted_by.display_name}` : " · при развёртывании"}
                      {revoked && (
                        <>
                          {" "}
                          · отозвана <When value={r.revoked_at} />
                        </>
                      )}
                    </small>
                  </div>
                  {!revoked && !isAdminRole && (
                    <Button variant="danger" size="sm" onClick={() => (m.reset(), setPending({ type: "revoke", record: r }))} aria-label={`Отозвать роль «${roleLabel(r.role)}» у ${r.account.display_name}`}>
                      Отозвать
                    </Button>
                  )}
                  {!revoked && isAdminRole && <small className="gv-mod-muted">{self ? "Это вы" : "Через Django Admin"}</small>}
                </li>
              );
            })}
          </ul>
        )}
      </QueryState>

      <Modal
        open={Boolean(pending)}
        onClose={() => !m.isPending && setPending(null)}
        title={pending?.type === "grant" ? "Выдать служебную роль?" : "Отозвать служебную роль?"}
        footer={
          <>
            <Button variant="pill" onClick={() => setPending(null)} disabled={m.isPending}>
              Отмена
            </Button>
            <Button variant={pending?.type === "revoke" ? "danger" : "primary"} loading={m.isPending} onClick={() => pending && m.mutate(pending)}>
              {pending?.type === "grant" ? "Выдать" : "Отозвать"}
            </Button>
          </>
        }
      >
        {apiErr && (
          <div className="gv-form-error" role="alert">
            <Icon name="alert" size={18} />
            <span>{apiErr.message}</span>
          </div>
        )}
        {pending?.type === "grant" && (
          <p>
            Аккаунт <b>{pending.email}</b> получит роль «{roleLabel(pending.role)}». {STAFF_ROLE_HINTS[pending.role]}
            {pending.role === "moderator" && " При первом входе в модерацию пользователь настроит 2FA."}
          </p>
        )}
        {pending?.type === "revoke" && (
          <p>
            <b>{pending.record.account.display_name}</b> ({pending.record.account_email}) потеряет роль «{roleLabel(pending.record.role)}» сразу — в том
            числе в уже открытых сессиях. История останется в журнале.
          </p>
        )}
      </Modal>
    </section>
  );
}
