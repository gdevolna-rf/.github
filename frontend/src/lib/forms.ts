/**
 * Form helpers: Zod validation + server field errors in one `FormErrors` map (field → message).
 * Pattern (see LoginForm): validate with `validate(schema, values)`; on ApiError merge `apiFieldErrors(err)`.
 */
import type { z } from "zod";
import { isApiError } from "./api/errors";

export type FormErrors<K extends string = string> = Partial<Record<K | "_form", string>>;

/** Returns `{data}` when valid, otherwise `{errors}` with the first message per field. */
export function validate<S extends z.ZodType>(
  schema: S,
  values: unknown,
): { data: z.infer<S>; errors: null } | { data: null; errors: FormErrors } {
  const result = schema.safeParse(values);
  if (result.success) return { data: result.data, errors: null };
  const errors: FormErrors = {};
  for (const issue of result.error.issues) {
    const key = issue.path.length ? String(issue.path[0]) : "_form";
    if (!errors[key]) errors[key] = issue.message;
  }
  return { data: null, errors };
}

/** Map an ApiError (400 with `fields`) into FormErrors; non-field message goes to `_form`. */
export function apiFieldErrors(error: unknown, fieldAliases: Record<string, string> = {}): FormErrors {
  if (!isApiError(error)) return { _form: "Что-то пошло не так. Попробуйте ещё раз." };
  const out: FormErrors = {};
  for (const [field, messages] of Object.entries(error.fields)) {
    const key = fieldAliases[field] ?? field;
    if (messages[0]) out[key] = messages[0];
  }
  if (!Object.keys(out).length || error.status !== 400) out._form = error.message;
  return out;
}
