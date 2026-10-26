"use client";
/**
 * Header search (prototype «Что ищем?» modal) → /search?q= (unified search, NAV-04, built by the search page).
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { MAIN_NAV, routes } from "@/lib/routes";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";

export function SearchDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const query = q.trim();
    if (!query) {
      inputRef.current?.focus();
      return;
    }
    onClose();
    router.push(routes.search(query));
  };

  return (
    <Modal open={open} onClose={onClose} title="Что ищем?" description="Споты, инструкторов, школы, доски, снаряжение и своих людей." initialFocusRef={inputRef}>
      <form role="search" onSubmit={submit} className="gv-search-form">
        <label htmlFor="site-search" className="sr-only">
          Поиск по сайту
        </label>
        <span className="gv-search-box">
          <Icon name="search" size={18} />
          <input
            ref={inputRef}
            id="site-search"
            type="search"
            name="q"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Например: Камчатка, Алексей, Ладога"
            autoComplete="off"
            enterKeyHint="search"
          />
        </span>
        <Button type="submit" variant="primary" iconRight="arrow">
          Найти
        </Button>
      </form>
      <p className="gv-search-hint">Или откройте раздел:</p>
      <div className="chips gv-search-sections">
        {MAIN_NAV.map((item) => (
          <Link key={item.href} href={item.href} className="chip" onClick={onClose}>
            <Icon name={item.icon} size={14} />
            {item.short}
          </Link>
        ))}
      </div>
    </Modal>
  );
}
