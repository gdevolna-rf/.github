/** Zod schemas for auth forms. Messages are user-facing Russian texts. */
import { z } from "zod";

const email = z.string().trim().min(1, "Укажите электронную почту").pipe(z.email("Проверьте адрес электронной почты"));

export const passwordRule = z
  .string()
  .min(8, "Пароль — не короче 8 символов")
  .max(128, "Пароль — не длиннее 128 символов")
  .refine((v) => !/^\d+$/.test(v), "Пароль не может состоять только из цифр");

export const loginSchema = z.object({
  email,
  password: z.string().min(1, "Введите пароль"),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const PRIMARY_TYPES = ["surfer", "instructor", "shaper", "school", "rental"] as const;
export const EXTRA_SPECIALTIES = ["instructor", "shaper", "rental"] as const;

export const registerSchema = z.object({
  first_name: z.string().trim().min(1, "Как к вам обращаться?").max(80, "Не длиннее 80 символов"),
  last_name: z.string().trim().max(80, "Не длиннее 80 символов"),
  email,
  password: passwordRule,
  primary_type: z.enum(PRIMARY_TYPES, "Выберите, кто вы в сообществе"),
  extra_specialties: z.array(z.enum(EXTRA_SPECIALTIES)),
  accept_terms: z.literal(true, "Нужно принять пользовательское соглашение"),
  accept_privacy: z.literal(true, "Нужно согласие на обработку персональных данных"),
});
export type RegisterValues = z.infer<typeof registerSchema>;

export const resetRequestSchema = z.object({ email });

export const resetConfirmSchema = z
  .object({
    new_password: passwordRule,
    repeat: z.string(),
  })
  .refine((v) => v.new_password === v.repeat, { message: "Пароли не совпадают", path: ["repeat"] });
