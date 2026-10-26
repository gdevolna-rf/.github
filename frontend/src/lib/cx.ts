/** className joiner: cx("btn", active && "active", undefined) → "btn active" */
export function cx(...parts: Array<string | false | null | undefined | 0>): string {
  return parts.filter(Boolean).join(" ");
}
