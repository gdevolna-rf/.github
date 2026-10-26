// Чтение писем из Mailpit (подтверждение email, сброс пароля, приглашения).
const MAILPIT = process.env.MAILPIT_URL ?? "http://localhost:8025";

type MessageSummary = { ID: string; To: { Address: string }[]; Subject: string; Created: string };

export async function latestMessageTo(email: string, { timeoutMs = 20_000, subjectIncludes = "" } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await fetch(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:"${email}"`)}`);
    if (res.ok) {
      const data = (await res.json()) as { messages: MessageSummary[] };
      const found = data.messages.find((m) => m.Subject.includes(subjectIncludes));
      if (found) {
        const full = await (await fetch(`${MAILPIT}/api/v1/message/${found.ID}`)).json();
        return full as { Subject: string; Text: string; HTML: string };
      }
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`no email to ${email} (${subjectIncludes}) within ${timeoutMs}ms`);
}

export function firstLink(text: string, pathIncludes: string): string {
  const match = text.match(new RegExp(`https?://[^\\s"<>]*${pathIncludes}[^\\s"<>]*`));
  if (!match) throw new Error(`no link with ${pathIncludes}`);
  return match[0];
}
