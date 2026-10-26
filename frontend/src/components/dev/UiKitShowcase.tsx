"use client";
/** Living style guide of the UI kit (/dev/ui, development only). Every block mirrors FRONTEND_GUIDE.md. */
import { useState } from "react";
import type { Media } from "@/lib/api/types";
import { STATUS, type StatusDomain } from "@/lib/labels";
import { ICONS, type IconName } from "@/components/ui/icons/registry";
import {
  Avatar,
  Badge,
  Button,
  ButtonLink,
  Card,
  CardHeader,
  CertificateBadge,
  Checkbox,
  Chip,
  ChipGroup,
  ClampText,
  CompassRose,
  EmptyState,
  ErrorState,
  HeartButton,
  Icon,
  IconButton,
  LoadingState,
  MediaImage,
  MediaUploader,
  Modal,
  NoAccess,
  Pagination,
  Rating,
  RatingInput,
  Segmented,
  Select,
  StatStrip,
  StatusBadge,
  SuccessState,
  TabPanel,
  Tabs,
  Tag,
  Textarea,
  TextInput,
  Toggle,
  ToggleRow,
  useToast,
} from "@/components/ui";
import { networkError } from "@/lib/api/errors";

const demoMedia = (id: string, url: string): Media => ({
  id,
  kind: "image",
  purpose: "board_photo",
  visibility: "public",
  status: "ready",
  url,
  thumbnail_url: url,
  poster_url: null,
  content_type: "image/webp",
  size_bytes: 1,
  width: 1,
  height: 1,
  duration_seconds: null,
  alt_text: "",
  original_filename: id,
});

export function UiKitShowcase() {
  const toast = useToast();
  const [modal, setModal] = useState(false);
  const [toggle, setToggle] = useState(true);
  const [segment, setSegment] = useState<"map" | "list">("map");
  const [tab, setTab] = useState("about");
  const [rating, setRating] = useState<number | null>(4);
  const [chips, setChips] = useState<string[]>(["surf"]);
  const [page, setPage] = useState(3);
  const [photos, setPhotos] = useState<Media[]>([
    demoMedia("p1", "/ui/feature-volcano-coast.webp"),
    demoMedia("p2", "/ui/feature-coast-aerial.webp"),
    demoMedia("p3", "/ui/feature-barrel-surfer.webp"),
  ]);
  const [video, setVideo] = useState<Media | null>({ ...demoMedia("v1", "/ui/hero-home.webp"), kind: "video", poster_url: "/ui/hero-home.webp", duration_seconds: 74, original_filename: "promo-volna.mp4", size_bytes: 48_000_000 });

  return (
    <div className="wrap gv-kit">
      <h1 className="section-title">UI kit «Гдеволна»</h1>
      <p className="muted">Компоненты из src/components/ui. Разработческая страница — в продакшене её нет.</p>

      <Card>
        <CardHeader title="Кнопки" description="primary · line · pill · link · soft · danger" />
        <div className="view-tools">
          <Button iconRight="arrow">Подробнее о споте</Button>
          <Button variant="line" icon="user">Войти</Button>
          <Button variant="pill" iconRight="arrow">Узнать о проекте</Button>
          <Button variant="link" iconRight="arrow">Перейти</Button>
          <Button variant="soft" icon="plus">Направление</Button>
          <Button variant="danger">Отменить заявку</Button>
          <Button loading>Сохраняем</Button>
          <Button disabled>Недоступно</Button>
          <ButtonLink href="/spots" variant="pill">Ссылка-кнопка</ButtonLink>
          <IconButton icon="search" label="Поиск" />
          <IconButton icon="chat" label="Сообщения" badge={12} />
          <HeartButton type="spot" id="kit-1" name="Пример" variant="light" />
          <HeartButton type="spot" id="kit-1" name="Пример" variant="pill" />
        </div>
      </Card>

      <Card>
        <CardHeader title="Иконки" description="Одна сетка 24px, толщина 1.9, оптический центр (UX-04)" />
        <div className="gv-kit-icons">
          {(Object.keys(ICONS) as IconName[]).map((n) => (
            <span key={n} title={n}>
              <Icon name={n} size={22} />
              <small>{n}</small>
            </span>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Статусы и бейджи" description="Единый словарь labels.ts (SHO-05)" />
        {(["inquiry", "booking", "rentalBooking", "session", "review", "proposal"] as StatusDomain[]).map((d) => (
          <div key={d} className="view-tools">
            <b className="small gv-kit-label">{d}</b>
            {Object.keys(STATUS[d]).map((code) => (
              <StatusBadge key={code} domain={d} status={code} />
            ))}
          </div>
        ))}
        <div className="view-tools">
          <CertificateBadge status="none" />
          <CertificateBadge status="uploaded" />
          <CertificateBadge status="verified" />
          <CertificateBadge status="rejected" audience="owner" />
          <Tag>Бич-брейк</Tag>
          <Tag variant="gg">GG Surfer · покажу споты</Tag>
          <Badge tone="new">Новое</Badge>
          <Chip icon="target">Камчатка</Chip>
        </div>
        <div className="view-tools">
          <Rating value="4.86" count={24} />
          <Rating value="3.4" count={7} variant="full" />
          <Rating value={0} count={0} />
          <Avatar name="Алексей Морозов" size={40} />
          <Avatar src="/ui/feature-volcano-coast.webp" name="Фото" size={40} />
        </div>
      </Card>

      <Card>
        <CardHeader title="Формы" description="Видимые подписи, подсказки и ошибки связаны с полем (UX-14)" />
        <div className="gv-form-grid">
          <TextInput label="Имя" required placeholder="Как к вам обращаться" />
          <TextInput label="Email" error="Проверьте адрес электронной почты" defaultValue="name@" />
          <Select label="Регион" placeholder="Все регионы" options={[{ value: "k", label: "Камчатский край" }, { value: "c", label: "Крым" }]} defaultValue="" />
          <Select label="Очень длинное значение" options={[{ value: "x", label: "Ладожское озеро и окрестности Сортавалы" }]} />
        </div>
        <Textarea label="Пара слов инструктору" maxLength={1000} value="Привет! Буду в вашем регионе." onChange={() => {}} />
        <Checkbox label="Согласен на обработку персональных данных" description="Публично — только имя и фото." />
        <ToggleRow title="Хочу быть GG Surfer" description="Появляться в поиске сообщества" icon="heart" checked={toggle} onChange={setToggle} />
        <div className="view-tools">
          <Toggle checked={!toggle} onChange={(v) => setToggle(!v)} label="Отдельный переключатель" />
          <Segmented ariaLabel="Вид" value={segment} onChange={setSegment} options={[{ value: "map", label: "На карте", icon: "target" }, { value: "list", label: "Списком", icon: "grid" }]} />
        </div>
        <ChipGroup label="Интересы" value={chips} onChange={setChips} options={[{ value: "surf", label: "Сёрфинг" }, { value: "camp", label: "Кемпинг" }, { value: "photo", label: "Фотография" }, { value: "yoga", label: "Йога" }]} />
        <RatingInput value={rating} onChange={setRating} label="Оценка споту" />
      </Card>

      <Card>
        <CardHeader title="Вкладки, пагинация, метрики" />
        <Tabs idPrefix="kit" ariaLabel="Разделы" value={tab} onChange={setTab} items={[{ id: "about", label: "О знакомстве" }, { id: "calendar", label: "Календарь занятий" }, { id: "reviews", label: "Отзывы", badge: 3 }]} />
        <TabPanel idPrefix="kit" id="about" value={tab}>
          <p className="small">Содержимое вкладки «О знакомстве».</p>
        </TabPanel>
        <TabPanel idPrefix="kit" id="calendar" value={tab}>
          <p className="small">Календарь.</p>
        </TabPanel>
        <TabPanel idPrefix="kit" id="reviews" value={tab}>
          <p className="small">Отзывы.</p>
        </TabPanel>
        <StatStrip items={[{ label: "Просмотры", value: 1284 }, { label: "Обращения", value: 37 }, { label: "Конверсия", value: "2,9 %" }, { label: "Средняя оценка", value: "4,8" }, { label: "Выручка (подтв.)", value: "184 000 ₽" }]} />
        <Pagination page={page} pageCount={12} onChange={setPage} />
      </Card>

      <Card>
        <CardHeader title="Роза ветра и свелла" description="Типично благоприятные направления, не прогноз (SPT-04)" />
        <div className="gv-rose-pair" style={{ maxWidth: 460 }}>
          <CompassRose kind="wind" directions={["NW", "NNW", { code: "N", label: "Север" }]} />
          <CompassRose kind="swell" directions={["SE"]} />
        </div>
        <div className="gv-rose-pair" style={{ maxWidth: 460, marginTop: 12 }}>
          <CompassRose kind="wind" directions={[]} />
          <CompassRose kind="swell" directions={["N", "S"]} />
        </div>
      </Card>

      <Card>
        <CardHeader title="Загрузка медиа" description="Слот сверху, сетка миниатюр, × удаление, обложка, порядок, отдельное видео (UX-08/09)" />
        <MediaUploader
          purpose="board_photo"
          value={photos}
          onChange={setPhotos}
          video={{ purpose: "board_video", value: video, onChange: setVideo }}
          uploader={async () => {
            await new Promise((r) => setTimeout(r, 1200));
            throw networkError();
          }}
        />
      </Card>

      <Card>
        <CardHeader title="Состояния экрана" description="Загрузка · пусто · ошибка · нет прав · успех (UX-13)" />
        <LoadingState />
        <LoadingState variant="skeleton" />
        <EmptyState title="Похоже, все ушли ловить волну!" text="По этим условиям инструкторы пока не нашлись." action={{ label: "Сбросить фильтры", onClick: () => toast.info("Фильтры сброшены") }} />
        <EmptyState compact title="Обращений пока нет" text="Когда клиент напишет, обращение появится здесь." />
        <ErrorState error={networkError()} onRetry={() => toast.info("Повторяем…")} />
        <NoAccess />
        <SuccessState title="Почта подтверждена" text="Теперь доступны заявки и отзывы." />
        <div className="grid grid-3" style={{ marginTop: 12 }}>
          <div className="spot-pic" style={{ height: 150, position: "relative", borderRadius: 12, overflow: "hidden" }}>
            <MediaImage media={null} alt="Спот без фото" />
          </div>
          <ClampText lines={3}>
            Очень длинное описание спота: волна держится при северо-западном ветре, на отливе обнажаются камни, вход в воду — с
            левого края пляжа, у скал течение. Летом бывает много людей, весной холодная вода и сильные ветра. Подробности уточняйте у
            местных инструкторов и проверяйте прогноз перед выездом.
          </ClampText>
          <div className="view-tools">
            <Button onClick={() => setModal(true)}>Открыть модальное окно</Button>
            <Button variant="pill" onClick={() => toast.success("Профиль сохранён")}>Тост</Button>
            <Button variant="pill" onClick={() => toast.error(networkError(), { action: { label: "Повторить", onClick: () => {} } })}>Тост-ошибка</Button>
          </div>
        </div>
      </Card>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title="Уточним данные спота?"
        description="Измените только те поля, о которых знаете."
        size="wide"
        footer={
          <>
            <Button variant="pill" onClick={() => setModal(false)}>Отмена</Button>
            <Button iconRight="arrow" onClick={() => setModal(false)}>Отправить на модерацию</Button>
          </>
        }
      >
        <TextInput label="Название спота" defaultValue="Халактырский пляж" data-autofocus="" />
        <Textarea label="Комментарий для модератора" maxLength={1400} value="" onChange={() => {}} />
      </Modal>
    </div>
  );
}
