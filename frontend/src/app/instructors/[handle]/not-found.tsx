import { ButtonLink } from "@/components/ui";
import { routes } from "@/lib/routes";

/** Unknown, unpublished or hidden instructor profile. */
export default function InstructorNotFound() {
  return (
    <div className="gv-special">
      <div className="empty surfer-empty gv-empty">
        <span className="gv-empty-art" aria-hidden="true" />
        <h1 className="gv-special-title">Инструктор не найден</h1>
        <p>Профиль снят с публикации или ссылка устарела. Посмотрите других инструкторов в каталоге.</p>
        <div className="view-tools">
          <ButtonLink href={routes.instructors} variant="primary" iconRight="arrow">
            Каталог инструкторов
          </ButtonLink>
        </div>
      </div>
    </div>
  );
}
