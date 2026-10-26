/**
 * Whose inventory the rental cabinet shows (RENT-02): a personal one (specialty «Прокат») or an organization's
 * (any active member of a rental/school organization). Pure functions → unit-tested.
 *
 *   ?organization=<uuid>  → that organization (the server answers 403 for non-members → NoAccess)
 *   ?owner=personal       → personal inventory (only with the rental specialty)
 *   no params             → first rental organization → personal (specialty) → first school organization → none
 */
import type { Me, MyOrganization } from "@/lib/api/auth";
import { ORGANIZATION_KIND_LABELS } from "@/lib/labels";

export type RentalOwner =
  | { type: "personal" }
  | { type: "organization"; id: string; name: string; kind: string | null }
  | { type: "none" };

export interface OwnerOption {
  /** "personal" or the organization id */
  value: string;
  label: string;
}

export const PERSONAL = "personal";

/** Organizations whose inventory can be managed here (rental shops and schools: equipment, SCH-03). */
const INVENTORY_ORG_KINDS = new Set(["rental", "school"]);

function inventoryOrgs(me: Pick<Me, "organizations">): MyOrganization[] {
  return me.organizations.filter((o) => o.id && INVENTORY_ORG_KINDS.has(o.kind) && o.status !== "archived");
}

export function hasRentalSpecialty(me: Pick<Me, "specialties">): boolean {
  return me.specialties.includes("rental");
}

export function resolveOwner(
  me: Pick<Me, "specialties" | "organizations">,
  params: { organization?: string | null; owner?: string | null },
): RentalOwner {
  if (params.organization) {
    const org = me.organizations.find((o) => o.id === params.organization);
    return { type: "organization", id: params.organization, name: org?.name ?? "Организация", kind: org?.kind ?? null };
  }
  if (params.owner === PERSONAL && hasRentalSpecialty(me)) return { type: "personal" };
  const orgs = inventoryOrgs(me);
  const rental = orgs.find((o) => o.kind === "rental");
  if (rental) return { type: "organization", id: rental.id, name: rental.name, kind: rental.kind };
  if (hasRentalSpecialty(me)) return { type: "personal" };
  const school = orgs[0];
  if (school) return { type: "organization", id: school.id, name: school.name, kind: school.kind };
  return { type: "none" };
}

/** Options of the owner switcher; an explicitly requested organization is always kept. */
export function ownerOptions(me: Pick<Me, "specialties" | "organizations">, current: RentalOwner): OwnerOption[] {
  const options: OwnerOption[] = [];
  if (hasRentalSpecialty(me)) options.push({ value: PERSONAL, label: "Личный инвентарь" });
  for (const org of inventoryOrgs(me)) {
    options.push({ value: org.id, label: `${org.name} · ${ORGANIZATION_KIND_LABELS[org.kind] ?? "Организация"}` });
  }
  if (current.type === "organization" && !options.some((o) => o.value === current.id)) {
    options.push({ value: current.id, label: current.name });
  }
  return options;
}

export function ownerValue(owner: RentalOwner): string {
  return owner.type === "organization" ? owner.id : PERSONAL;
}

/** URL search string for a switcher value (keeps other params such as `view`). */
export function ownerSearch(value: string, current: URLSearchParams): string {
  const p = new URLSearchParams(current.toString());
  p.delete("organization");
  p.delete("owner");
  if (value === PERSONAL) p.set("owner", PERSONAL);
  else p.set("organization", value);
  return p.toString();
}

/** Organization id for API calls (null = personal). */
export function ownerOrganization(owner: RentalOwner): string | null {
  return owner.type === "organization" ? owner.id : null;
}

export function ownerTitle(owner: RentalOwner): string {
  if (owner.type === "organization") return owner.name;
  if (owner.type === "personal") return "Личный инвентарь";
  return "";
}
