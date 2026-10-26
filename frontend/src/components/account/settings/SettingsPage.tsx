"use client";
/**
 * «Настройки» (ACC-09/13, MSG-12, COM-05/07/08, CABINET_SCREENS §5.7): соседняя с «Профилем» вкладка.
 * Разделы — якоря на одной странице (быстрый переход с телефона), выход из аккаунта очищает данные прошлого
 * пользователя (resetPrivateData в useLogout).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { accountApi, accountKeys, type AccountBlock } from "@/lib/api/account";
import { authApi } from "@/lib/api/auth";
import { isApiError } from "@/lib/api/errors";
import type { Paginated } from "@/lib/api/types";
import { useMe } from "@/lib/auth/hooks";
import { formatDate } from "@/lib/format";
import { routes } from "@/lib/routes";
import { Avatar } from "@/components/ui/Avatar";
import { Button, ButtonLink } from "@/components/ui/Button";
import { QueryState } from "@/components/ui/QueryState";
import { EmptyState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ProfileSettingsTabs } from "../shared/ProfileSettingsTabs";
import { viewerTimeZone } from "../shared/utils";
import { DataSection } from "./DataSection";
import { NotificationPrefsSection } from "./NotificationPrefsSection";
import { PrivacySection } from "./PrivacySection";
import { SecuritySection } from "./SecuritySection";

function BlocksSection() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: accountKeys.blocks, queryFn: accountApi.blocks });
  const unblock = useMutation({
    mutationFn: (b: AccountBlock) => accountApi.unblock(b.account.id),
    onSuccess: (_d, b) => {
      queryClient.setQueryData<Paginated<AccountBlock>>(accountKeys.blocks, (old) =>
        old ? { ...old, count: old.count - 1, results: old.results.filter((x) => x.account.id !== b.account.id) } : old,
      );
      toast.success(`${b.account.display_name} разблокирован(а)`);
    },
    onError: (err, b) => toast.error(err, { action: { label: "Повторить", onClick: () => unblock.mutate(b) } }),
  });
  return (
    <section id="blocks" className="gv-ac-panel acc-settings-section" aria-labelledby="blocks-title">
      <h2 id="blocks-title">Заблокированные</h2>
      <p className="gv-ac-desc">Заблокированные участники не могут писать вам в GG Surfer и по обращениям. Заблокировать можно из переписки.</p>
      <QueryState query={query} isEmpty={(d) => d.results.length === 0} empty={<EmptyState compact title="Вы никого не блокировали" />}>
        {(data) => (
          <ul className="acc-plain-list">
            {data.results.map((b) => (
              <li key={b.account.id} className="gv-ac-line">
                <Avatar media={b.account.avatar} name={b.account.display_name} size={36} />
                <div className="gv-ac-line-main">
                  <strong>{b.account.display_name}</strong>
                  <small>Заблокирован(а) {formatDate(b.created_at, { timeZone: viewerTimeZone() })}</small>
                </div>
                <Button variant="soft" size="sm" loading={unblock.isPending && unblock.variables?.account.id === b.account.id} onClick={() => unblock.mutate(b)}>
                  Разблокировать
                </Button>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </section>
  );
}

const SECTIONS = [
  { id: "privacy", label: "Приватность" },
  { id: "notifications", label: "Уведомления" },
  { id: "security", label: "Безопасность" },
  { id: "data", label: "Данные и удаление" },
  { id: "blocks", label: "Блокировки" },
];

/**
 * Logout = server logout + a full page load to «/»: the in-memory cache of the previous user (orders, chats,
 * favourites, drafts) disappears completely, the next user starts clean (CABINET_NOTES G «Logout keeps…»).
 */
function useHardLogout() {
  const [pending, setPending] = useState(false);
  const toast = useToast();
  const run = async () => {
    setPending(true);
    try {
      await authApi.logout();
    } catch (err) {
      if (!(isApiError(err) && (err.status === 401 || err.status === 403))) {
        setPending(false);
        toast.error(err, { action: { label: "Повторить", onClick: () => void run() } });
        return;
      }
    }
    window.location.replace(routes.home);
  };
  return { run, pending };
}

export function SettingsPage() {
  const { me } = useMe();
  const logout = useHardLogout();
  if (!me) return <LoadingState label="Загружаем настройки…" />;

  return (
    <>
      <ProfileSettingsTabs />
      <nav className="acc-anchor-nav" aria-label="Разделы настроек">
        {SECTIONS.map((s) => (
          <a key={s.id} href={`#${s.id}`}>
            {s.label}
          </a>
        ))}
      </nav>
      <PrivacySection me={me} />
      <NotificationPrefsSection />
      <SecuritySection me={me} />
      <DataSection />
      <BlocksSection />
      <section className="gv-ac-panel acc-settings-section" aria-labelledby="session-title">
        <h2 id="session-title">Сеанс</h2>
        <div className="gv-ac-row">
          <ButtonLink href={routes.account.specialties} variant="soft" iconRight="arrow">
            Управление направлениями
          </ButtonLink>
          <Button variant="danger" icon="logout" loading={logout.pending} onClick={() => void logout.run()}>
            Выйти из аккаунта
          </Button>
        </div>
      </section>
    </>
  );
}
