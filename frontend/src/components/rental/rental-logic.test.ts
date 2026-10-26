import { describe, expect, it } from "vitest";
import type { Me } from "@/lib/api/auth";
import type { InventoryItem, ItemPhoto } from "@/lib/api/inventory";
import type { Media } from "@/lib/api/types";
import { desiredOrder, diffPhotos, emptyValues, toPayload, validateValues, valuesFromItem } from "./form";
import { ownerOptions, ownerSearch, resolveOwner } from "./owner";
import { addDays, bookedShare, presetRange, rangeError, timelineSegments } from "./timeline";

type MeLite = Pick<Me, "specialties" | "organizations">;
const org = (id: string, kind: "rental" | "school" | "workshop", name = id) => ({ id, slug: id, name, kind, role: "owner" as const, status: "published" });

describe("resolveOwner", () => {
  const rentalOrg = org("r1", "rental", "Прокат «Волна рядом»");
  const school = org("s1", "school", "Kamchatka Surf School");
  const workshop = org("w1", "workshop", "Kamchatka Boards");

  it("explicit ?organization wins, even for an unknown org (server answers 403)", () => {
    const me: MeLite = { specialties: ["rental"], organizations: [rentalOrg] };
    expect(resolveOwner(me, { organization: "zzz" })).toEqual({ type: "organization", id: "zzz", name: "Организация", kind: null });
    expect(resolveOwner(me, { organization: "r1" })).toMatchObject({ type: "organization", id: "r1", name: "Прокат «Волна рядом»" });
  });

  it("defaults to the first rental organization, then personal, then a school", () => {
    expect(resolveOwner({ specialties: ["rental"], organizations: [school, rentalOrg] }, {})).toMatchObject({ id: "r1" });
    expect(resolveOwner({ specialties: ["rental"], organizations: [school] }, {})).toEqual({ type: "personal" });
    expect(resolveOwner({ specialties: ["surfer"], organizations: [workshop, school] }, {})).toMatchObject({ id: "s1" });
  });

  it("?owner=personal only with the rental specialty", () => {
    expect(resolveOwner({ specialties: ["rental"], organizations: [rentalOrg] }, { owner: "personal" })).toEqual({ type: "personal" });
    expect(resolveOwner({ specialties: ["surfer"], organizations: [rentalOrg] }, { owner: "personal" })).toMatchObject({ id: "r1" });
  });

  it("no specialty and no rental/school organization → none (workshops do not count)", () => {
    expect(resolveOwner({ specialties: ["surfer", "shaper"], organizations: [workshop] }, {})).toEqual({ type: "none" });
  });

  it("switcher lists personal + rental/school orgs and keeps an explicitly requested org", () => {
    const me: MeLite = { specialties: ["rental"], organizations: [rentalOrg, workshop, school] };
    const opts = ownerOptions(me, { type: "organization", id: "x9", name: "Чужая", kind: null });
    expect(opts.map((o) => o.value)).toEqual(["personal", "r1", "s1", "x9"]);
    expect(opts[1].label).toBe("Прокат «Волна рядом» · Прокат");
  });

  it("ownerSearch swaps organization/owner and keeps other params", () => {
    expect(ownerSearch("personal", new URLSearchParams("organization=r1&view=availability"))).toBe("view=availability&owner=personal");
    expect(ownerSearch("s1", new URLSearchParams("owner=personal&kind=board"))).toBe("kind=board&organization=s1");
  });
});

describe("timeline math", () => {
  const from = "2026-10-21T00:00:00+03:00";
  const to = "2026-10-22T00:00:00+03:00"; // 24 h

  it("positions intervals in % of the period and clips the edges", () => {
    const segs = timelineSegments(from, to, [
      { starts_at: "2026-10-21T06:00:00+03:00", ends_at: "2026-10-21T12:00:00+03:00" },
      { starts_at: "2026-10-20T20:00:00+03:00", ends_at: "2026-10-21T03:00:00+03:00" },
      { starts_at: "2026-10-21T18:00:00+03:00", ends_at: "2026-10-22T06:00:00+03:00" },
    ]);
    expect(segs.map((s) => [s.left, s.width, s.clippedStart, s.clippedEnd])).toEqual([
      [0, 12.5, true, false],
      [25, 25, false, false],
      [75, 25, false, true],
    ]);
  });

  it("drops intervals outside the period and keeps tiny ones visible inside the bar", () => {
    const segs = timelineSegments(from, to, [
      { starts_at: "2026-10-22T01:00:00+03:00", ends_at: "2026-10-22T02:00:00+03:00" },
      { starts_at: "2026-10-21T23:59:00+03:00", ends_at: "2026-10-22T00:00:00+03:00" },
    ]);
    expect(segs).toHaveLength(1);
    expect(segs[0].width).toBe(1.5);
    expect(segs[0].left + segs[0].width).toBeLessThanOrEqual(100);
  });

  it("returns nothing for an empty or inverted period", () => {
    expect(timelineSegments(to, from, [{ starts_at: from, ends_at: to }])).toEqual([]);
  });

  it("bookedShare merges overlaps", () => {
    expect(
      bookedShare(from, to, [
        { starts_at: "2026-10-21T00:00:00+03:00", ends_at: "2026-10-21T12:00:00+03:00" },
        { starts_at: "2026-10-21T06:00:00+03:00", ends_at: "2026-10-21T18:00:00+03:00" },
      ]),
    ).toBe(75);
    expect(bookedShare(from, to, [])).toBe(0);
  });

  it("presets and custom ranges", () => {
    const now = new Date("2026-10-21T22:30:00Z"); // 01:30 on Oct 22 in Moscow
    expect(presetRange("today", now)).toEqual({ from: "2026-10-22", to: "2026-10-22" });
    expect(presetRange("week", now)).toEqual({ from: "2026-10-22", to: "2026-10-28" });
    expect(addDays("2026-12-30", 3)).toBe("2027-01-02");
    expect(rangeError("2026-10-10", "2026-10-01")).toMatch(/раньше/);
    expect(rangeError("2026-01-01", "2027-03-01")).toMatch(/года/);
    expect(rangeError("2026-10-01", "")).toMatch(/обе даты/);
    expect(rangeError("2026-10-01", "2026-10-01")).toBeNull();
  });
});

const media = (id: string): Media => ({
  id,
  kind: "image",
  purpose: "item_photo",
  visibility: "public",
  status: "ready",
  url: `/m/${id}.jpg`,
  thumbnail_url: null,
  poster_url: null,
  content_type: "image/jpeg",
  size_bytes: 10,
  width: 1,
  height: 1,
  duration_seconds: null,
  alt_text: "",
  original_filename: `${id}.jpg`,
});
const photo = (id: number, mediaId: string, position: number): ItemPhoto => ({ id, position, media: media(mediaId) });

describe("inventory form model", () => {
  it("requires a title and a rental rate for rental items; checks numbers", () => {
    const v = { ...emptyValues(), title: " ", rental_price_per_day: "", rental_price_per_hour: "" };
    expect(validateValues(v)).toMatchObject({ title: "Укажите название.", rental_price_per_day: expect.stringMatching(/за день или за час/) });
    expect(validateValues({ ...v, title: "Доска", rental_price_per_hour: "12a" })).toMatchObject({ rental_price_per_hour: expect.any(String) });
    expect(validateValues({ ...v, title: "Доска", purpose: "sale" })).toEqual({});
  });

  it("builds the create payload with organization, photos and cleared prices of other purposes", () => {
    const v = { ...emptyValues({ region_id: "5" }), title: " Лонгборд 9′2″ ", rental_price_per_day: "1700,5", sale_price: "30000", variant_id: "v1" };
    const body = toPayload(v, { create: true, organizationId: "org-1", photoIds: ["m1", "m2"], variantsAllowed: true });
    expect(body).toMatchObject({
      title: "Лонгборд 9′2″",
      region_id: 5,
      spot_id: null,
      rental_price_per_day: "1700.5",
      rental_price_per_hour: null,
      sale_price: null,
      min_rental_hours: 1,
      organization_id: "org-1",
      photo_ids: ["m1", "m2"],
      variant_id: "v1",
    });
    const edit = toPayload({ ...v, kind: "wetsuit" }, { create: false, variantsAllowed: true });
    expect(edit).not.toHaveProperty("organization_id");
    expect(edit).not.toHaveProperty("photo_ids");
    expect(edit.variant_id).toBeNull();
    expect(toPayload(v, { create: false, variantsAllowed: false })).not.toHaveProperty("variant_id");
  });

  it("round-trips an item into form values", () => {
    const item = {
      kind: "board",
      purpose: "both",
      title: "Шортборд",
      description: "",
      size: "5′10″",
      condition: "good",
      region: { id: 5, slug: "p", name: "Приморский край" },
      spot: { id: "s1", slug: "s", name: "Спот" },
      pickup_location: "",
      available_hours: "",
      rental_price_per_day: "1600.00",
      rental_price_per_hour: null,
      deposit_note: "",
      min_rental_hours: 24,
      restrictions: "",
      sale_price: "30000.00",
      serial_number: "",
      is_published: false,
      variant: null,
    } as unknown as InventoryItem;
    expect(valuesFromItem(item)).toMatchObject({ region_id: "5", spot_id: "s1", rental_price_per_day: "1600", sale_price: "30000", min_rental_hours: "24", is_published: false });
  });

  it("photo diff and order", () => {
    const saved = [photo(1, "a", 0), photo(2, "b", 1), photo(3, "c", 2)];
    expect(diffPhotos(saved, [media("c"), media("a"), media("d")])).toEqual({ remove: [2], add: ["d"] });
    expect(desiredOrder(saved, [media("a"), media("b"), media("c")])).toBeNull();
    expect(desiredOrder(saved, [media("c"), media("a"), media("b")])).toEqual([3, 1, 2]);
  });
});
