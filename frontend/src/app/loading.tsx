/** Route-level loading (UX-13): compact version of the prototype loader art inside the page. */
export default function Loading() {
  return (
    <div className="gv-route-loading" role="status" aria-live="polite" aria-label="Загружаем">
      <span className="gv-route-loading-art" aria-hidden="true" />
      <b>ГДЕВОЛНА.РФ</b>
      <span>До встречи на волне</span>
    </div>
  );
}
