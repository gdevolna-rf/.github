"use client";
import { useEffect, useRef, useState } from "react";
import { useOnlineStatus } from "@/lib/hooks/useOnlineStatus";
import { Icon } from "./Icon";

/** Global «нет сети» banner (UX-13). Mounted once in the root layout; also tells when the link is back. */
export function OfflineBanner() {
  const online = useOnlineStatus();
  const [restored, setRestored] = useState(false);
  const wasOffline = useRef(false);

  useEffect(() => {
    if (!online) {
      wasOffline.current = true;
      setRestored(false);
      return;
    }
    if (wasOffline.current) {
      wasOffline.current = false;
      setRestored(true);
      const t = setTimeout(() => setRestored(false), 3000);
      return () => clearTimeout(t);
    }
  }, [online]);

  if (online && !restored) return null;
  return (
    <div className={online ? "gv-offline is-restored" : "gv-offline"} role="status" aria-live="polite">
      <Icon name={online ? "check" : "wifi-off"} size={16} />
      <span>
        {online
          ? "Связь восстановлена."
          : "Нет подключения к интернету. Показываем то, что уже загружено; действия можно будет повторить, когда связь вернётся."}
      </span>
    </div>
  );
}
