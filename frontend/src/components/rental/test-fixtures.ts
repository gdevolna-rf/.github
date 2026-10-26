/** Shared fixtures for rental tests (not a test file). */
export const ORG = "c8f82453-7543-4aef-9e09-b252a235144a";

const cover = { id: "m1", kind: "image", purpose: "item_photo", visibility: "public", status: "ready", url: "/m/1.png", thumbnail_url: "/m/1.webp", poster_url: null, content_type: "image/png", size_bytes: 1, width: 1, height: 1, duration_seconds: null, alt_text: "", original_filename: "1.png" };

export const ITEM = {
  id: "i1",
  title: "Лонгборд 9′2″ · Sea Glass с очень длинным названием для проверки переноса строк в карточке",
  kind: "board",
  kind_label: "Доска",
  purpose: "rental",
  size: "9′2″",
  condition: "good",
  condition_label: "Хорошее",
  region: { id: 1, slug: "kamchatskiy-kray", name: "Камчатский край" },
  spot: null,
  pickup_location: "Петропавловск · выдаёт Иван",
  available_hours: "Ежедневно 9–20",
  rental_price_per_day: "1700.00",
  rental_price_per_hour: null,
  min_rental_hours: 24,
  deposit_note: "",
  sale_price: null,
  currency: "RUB",
  cover,
  photos_count: 3,
  owner: { type: "organization", id: ORG, name: "Прокат", handle: null, slug: "volna", kind: "rental", avatar: null },
  variant: null,
  is_own: true,
  public_url: "/rentals/i1",
  description: "",
  restrictions: "",
  photos: [{ id: 1, position: 0, media: cover }],
  created_at: "2026-10-21T00:00:00+03:00",
  updated_at: "2026-10-21T00:00:00+03:00",
  status: "available",
  status_label: "Доступен",
  is_published: true,
  serial_number: "",
  organization_id: ORG,
};

