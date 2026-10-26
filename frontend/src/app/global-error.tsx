"use client";
/** Last-resort boundary (root layout failed): renders its own document with minimal inline styles. */
export default function GlobalError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <html lang="ru">
      <body style={{ margin: 0, fontFamily: "'Trebuchet MS','Segoe UI',Arial,sans-serif", color: "#0c517a", background: "linear-gradient(112deg,#f8fdff,#eafaff)" }}>
        <main style={{ maxWidth: 560, margin: "80px auto", padding: "0 16px", textAlign: "center" }}>
          <h1 style={{ fontSize: 26 }}>Что-то пошло не так</h1>
          <p>Мы не смогли открыть «Гдеволну». Проверьте соединение и попробуйте ещё раз.</p>
          <button
            type="button"
            onClick={() => retry()}
            style={{ border: 0, borderRadius: 9, padding: "12px 20px", color: "#fff", fontWeight: 800, background: "linear-gradient(115deg,#05648a,#0075a3)", cursor: "pointer" }}
          >
            Повторить
          </button>
        </main>
      </body>
    </html>
  );
}
