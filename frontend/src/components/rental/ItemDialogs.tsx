"use client";
/**
 * Status change (available / maintenance / retired / sold) and delete confirmations for an inventory item.
 * Server rules (apps.inventory.services.items): a status other than «Доступен» is refused while the item has
 * confirmed future bookings (409 item_has_active_bookings); delete of an item with history → «списан» (retired).
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { inventoryApi, inventoryKeys, MANUAL_STATUSES, type InventoryItem } from "@/lib/api/inventory";
import { errorMessage, isApiError } from "@/lib/api/errors";
import { STATUS } from "@/lib/labels";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import styles from "./rental.module.css";

const STATUS_HINTS: Record<string, string> = {
  available: "Можно бронировать; виден в каталоге, если опубликован.",
  maintenance: "Временно не выдаётся: ремонт, чистка, проверка. Из каталога скрыт.",
  retired: "Больше не используется. Скрыт из каталога, история броней сохраняется.",
  sold: "Экземпляр продан. Редактировать его больше нельзя.",
};

function conflictText(err: unknown, fallback: string): string {
  if (isApiError(err) && err.code === "item_has_active_bookings") {
    return "У экземпляра есть подтверждённые брони. Сначала отмените или завершите их в разделе «Бронирования», затем повторите.";
  }
  if (isApiError(err) && err.code === "item_sold") return "Экземпляр уже продан — статус изменить нельзя.";
  return errorMessage(err, fallback);
}

export function StatusDialog({
  item,
  onClose,
  bookingsHref,
}: {
  item: InventoryItem | null;
  onClose: () => void;
  bookingsHref: string;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [value, setValue] = useState(item?.status ?? "available");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setValue(item?.status ?? "available");
    setError(null);
  }, [item]);

  const mutation = useMutation({
    mutationFn: (status: string) => inventoryApi.setStatus(item!.id, status),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
      toast.success(`Статус «${saved.title}»: ${STATUS.inventory[saved.status as keyof typeof STATUS.inventory]?.label ?? saved.status_label}`);
      onClose();
    },
    onError: (err) => {
      setError(conflictText(err, "Не удалось изменить статус."));
      if (isApiError(err) && err.retryable) toast.error(err, { action: { label: "Повторить", onClick: () => mutation.mutate(value) } });
    },
  });

  const options = MANUAL_STATUSES.filter((s) => s !== "sold" || item?.purpose !== "rental");
  const risky = value === "retired" || value === "sold";
  const unchanged = value === item?.status;

  return (
    <Modal
      open={Boolean(item)}
      onClose={onClose}
      title="Статус экземпляра"
      description={item ? `«${item.title}»` : undefined}
      footer={
        <>
          <Button variant="pill" onClick={onClose}>
            Отмена
          </Button>
          <Button variant="primary" loading={mutation.isPending} disabled={unchanged} onClick={() => mutation.mutate(value)}>
            {risky ? (value === "sold" ? "Отметить проданным" : "Списать") : "Сохранить"}
          </Button>
        </>
      }
    >
      <fieldset className={styles.statusList}>
        <legend className="sr-only">Новый статус</legend>
        {options.map((status) => (
          <label key={status} className={styles.statusOption}>
            <input type="radio" name="inventory-status" value={status} checked={value === status} onChange={() => setValue(status)} />
            <span>
              <b>{STATUS.inventory[status].label}</b>
              <small>{STATUS_HINTS[status]}</small>
            </span>
          </label>
        ))}
      </fieldset>
      {risky && !unchanged && (
        <p className={styles.warning} role="note">
          {value === "sold"
            ? "После отметки «Продан» экземпляр нельзя будет редактировать и бронировать. Отменить действие нельзя."
            : "Списанный экземпляр скрывается из каталога и не бронируется. Вернуть его можно, выбрав «Доступен»."}
        </p>
      )}
      {error && (
        <div className="gv-form-error" role="alert">
          <span>
            {error}{" "}
            {isApiError(mutation.error) && mutation.error.code === "item_has_active_bookings" && (
              <Link href={bookingsHref}>Открыть бронирования</Link>
            )}
          </span>
        </div>
      )}
    </Modal>
  );
}

export function DeleteDialog({ item, onClose, bookingsHref }: { item: InventoryItem | null; onClose: () => void; bookingsHref: string }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setError(null), [item]);

  const mutation = useMutation({
    mutationFn: () => inventoryApi.remove(item!.id),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
      if (res?.result === "retired") {
        toast.success("Экземпляр списан и скрыт из каталога: по нему были брони или обращения, история сохранена.");
      } else {
        toast.success("Экземпляр удалён");
      }
      onClose();
    },
    onError: (err) => setError(conflictText(err, "Не удалось удалить экземпляр.")),
  });

  return (
    <Modal
      open={Boolean(item)}
      onClose={onClose}
      title="Удалить экземпляр?"
      description={item ? `«${item.title}»` : undefined}
      footer={
        <>
          <Button variant="pill" onClick={onClose}>
            Отмена
          </Button>
          <Button variant="danger" icon="trash" loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Удалить
          </Button>
        </>
      }
    >
      <p className="gv-ac-desc" style={{ margin: 0 }}>
        Экземпляр без истории удаляется полностью. Если по нему уже были брони или обращения, он будет списан и скрыт из
        каталога — история и акты сохранятся.
      </p>
      {error && (
        <div className="gv-form-error" role="alert" style={{ marginTop: 12 }}>
          <span>
            {error} {isApiError(mutation.error) && mutation.error.code === "item_has_active_bookings" && <Link href={bookingsHref}>Открыть бронирования</Link>}
          </span>
        </div>
      )}
    </Modal>
  );
}
