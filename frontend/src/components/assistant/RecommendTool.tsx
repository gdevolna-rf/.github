"use client";
/**
 * «Куда поехать и с кем» (AIX-01/02): region + level (+ date) → POST /assistant/recommend → spots, instructors
 * and rentals from the catalogue, each with its source and update date; typical conditions are labelled as
 * «не прогноз», the forecast is shown only when a provider has data for the date; hazards and the safety
 * disclaimer are always visible. Parameters are mirrored into the URL (?region=&level=&date=).
 */
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode, type Ref } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Avatar, Button, ErrorState, Icon, MediaImage, Rating, Select, Tag, TextInput } from "@/components/ui";
import { api } from "@/lib/api/client";
import { isApiError } from "@/lib/api/errors";
import {
  ASSISTANT_LEVELS,
  assistantApi,
  searchKeys,
  type RecommendedInstructor,
  type RecommendedRental,
  type RecommendedSpot,
  type RecommendInput,
  type RecommendResponse,
} from "@/lib/api/search";
import { formatDate, formatDateRange, formatDateTime, formatMoney, formatPriceFrom } from "@/lib/format";
import { routes } from "@/lib/routes";
import { dateBounds, RECOMMEND_PARAMS, replaceQuery, validateRecommend, type Errors, type RecommendValues } from "./assistantModel";

export interface RegionOption {
  slug: string;
  name: string;
  timezone?: string;
  spots_count?: number;
}

type Field = "region" | "level" | "date";

function sortRegions(regions: RegionOption[]): RegionOption[] {
  return [...regions].sort((a, b) => a.name.localeCompare(b.name, "ru"));
}

export function RecommendTool({
  regions: initialRegions,
  hazardLabels = {},
  initial,
}: {
  regions: RegionOption[];
  hazardLabels?: Record<string, string>;
  initial?: RecommendValues;
}) {
  const formId = useId().replace(/:/g, "");
  const [values, setValues] = useState<RecommendValues>(initial ?? { region: "", level: "", date: "" });
  const [errors, setErrors] = useState<Errors<Field>>({});
  const resultRef = useRef<HTMLHeadingElement>(null);
  const focusResult = useRef(false);

  // Regions come from the server render; if that failed, load them in the browser.
  const regionsQuery = useQuery({
    queryKey: searchKeys.regions,
    queryFn: () => api.get<RegionOption[]>("regions"),
    enabled: initialRegions.length === 0,
    staleTime: 10 * 60_000,
  });
  const regions = sortRegions(initialRegions.length ? initialRegions : (regionsQuery.data ?? []));

  const mutation = useMutation({
    mutationFn: (body: RecommendInput) => assistantApi.recommend(body),
    onSuccess: (_data, body) => {
      replaceQuery({ [RECOMMEND_PARAMS.region]: body.region, [RECOMMEND_PARAMS.level]: body.level, [RECOMMEND_PARAMS.date]: body.date ?? null });
    },
    onError: (err) => {
      if (isApiError(err) && err.isValidation && Object.keys(err.fields).length) {
        const next: Errors<Field> = {};
        for (const key of ["region", "level", "date"] as const) if (err.fields[key]?.[0]) next[key] = err.fields[key][0];
        if (!Object.keys(next).length) next._form = err.message;
        setErrors(next);
      }
    },
  });

  const autoRun = useRef(false);
  useEffect(() => {
    if (autoRun.current || !initial) return;
    autoRun.current = true;
    const { data } = validateRecommend(initial);
    if (data) mutation.mutate(data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (mutation.isSuccess && focusResult.current) {
      focusResult.current = false;
      resultRef.current?.focus();
    }
  }, [mutation.isSuccess, mutation.data]);

  const set = <K extends keyof RecommendValues>(key: K, value: RecommendValues[K]) => setValues((v) => ({ ...v, [key]: value }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const { data, errors: next } = validateRecommend(values);
    setErrors(next);
    if (!data) return;
    focusResult.current = true;
    mutation.mutate(data);
  };

  // Date bounds depend on the viewer's local date — computed after mount to keep SSR and hydration identical.
  const [bounds, setBounds] = useState<{ min: string; max: string } | null>(null);
  useEffect(() => setBounds(dateBounds()), []);
  const result = mutation.data;
  const fieldError = isApiError(mutation.error) && mutation.error.isValidation && Object.keys(mutation.error.fields).length > 0;

  return (
    <section className="gv-ax-tool" aria-labelledby={`${formId}-title`}>
      <div className="gv-ax-tool-head">
        <span className="gv-ax-tool-icon" aria-hidden="true">
          <Icon name="map-pin" size={22} />
        </span>
        <div>
          <h2 id={`${formId}-title`}>Куда поехать и с кем?</h2>
          <p>Споты под ваш уровень, инструкторы и прокат в выбранном регионе — только из данных каталога.</p>
        </div>
      </div>

      <form id={formId} className="gv-ax-form" onSubmit={submit} noValidate>
        {errors._form && (
          <div className="gv-form-error" role="alert">
            <Icon name="alert" size={18} />
            <span>{errors._form}</span>
          </div>
        )}
        <Select
          label="Регион"
          required
          placeholder={regionsQuery.isPending && !initialRegions.length ? "Загружаем регионы…" : "Выберите регион"}
          options={regions.map((r) => ({ value: r.slug, label: r.name }))}
          value={values.region}
          onChange={(e) => set("region", e.target.value)}
          error={errors.region ?? (regionsQuery.isError && !regions.length ? "Не удалось загрузить регионы — обновите страницу." : undefined)}
        />
        <Select
          label="Уровень катания"
          required
          placeholder="Выберите уровень"
          options={ASSISTANT_LEVELS}
          value={values.level}
          onChange={(e) => set("level", e.target.value as RecommendValues["level"])}
          error={errors.level}
        />
        <TextInput
          label="Когда собираетесь"
          type="date"
          min={bounds?.min}
          max={bounds?.max}
          value={values.date}
          onChange={(e) => set("date", e.target.value)}
          error={errors.date}
          hint="Необязательно. Учтём сезон, свободный прокат и прогноз, если он есть."
        />
        <div className="gv-ax-actions">
          <Button type="submit" variant="primary" iconRight="arrow" loading={mutation.isPending}>
            Подобрать
          </Button>
        </div>
      </form>

      <div className="gv-ax-result-wrap">
        <p className="sr-only" role="status" aria-live="polite">
          {mutation.isPending
            ? "Подбираем…"
            : result
              ? `Найдено: спотов ${result.spots.length}, инструкторов ${result.instructors.length}, предложений проката ${result.rentals.length}.`
              : ""}
        </p>
        {mutation.isError && !fieldError ? (
          <ErrorState
            compact
            error={mutation.error}
            title="Не удалось подобрать"
            onRetry={() => {
              const { data } = validateRecommend(values);
              if (data) mutation.mutate(data);
            }}
          />
        ) : result ? (
          <RecommendResult
            result={result}
            hazardLabels={hazardLabels}
            headingRef={resultRef}
            stale={mutation.isPending}
            timeZone={regions.find((r) => r.slug === result.region.slug)?.timezone}
          />
        ) : (
          <div className="gv-ax-placeholder">
            <Icon name="target" size={28} />
            <p>Выберите регион и уровень — покажем споты, инструкторов и прокат с источниками данных.</p>
          </div>
        )}
      </div>
    </section>
  );
}

export function RecommendResult({
  result,
  hazardLabels = {},
  headingRef,
  stale,
  timeZone,
}: {
  result: RecommendResponse;
  hazardLabels?: Record<string, string>;
  headingRef?: Ref<HTMLHeadingElement>;
  stale?: boolean;
  /** Region time zone (the response has none) for dates and the forecast window. */
  timeZone?: string;
}) {
  const tz = result.region.timezone ?? timeZone;
  const region = result.region.slug;
  return (
    <div className="gv-ax-result" aria-busy={stale || undefined}>
      <h3 ref={headingRef} tabIndex={-1} className="gv-ax-result-title">
        Подборка: {result.region.name} · {result.level_label} · {formatDate(result.date, { timeZone: tz, style: "long" })}
      </h3>
      {result.notes.map((n) => (
        <p key={n} className="notice gv-ax-note">
          <Icon name="info" size={16} /> {n}
        </p>
      ))}

      <ResultGroup
        title="Споты"
        icon="target"
        count={result.spots.length}
        empty="В этом регионе пока нет спотов под ваш уровень."
        catalogHref={`${routes.spots}?region=${encodeURIComponent(region)}`}
        catalogLabel="Все споты региона"
      >
        {result.spots.map((s) => (
          <li key={s.id}>
            <SpotCard spot={s} hazardLabels={hazardLabels} tz={tz} />
          </li>
        ))}
      </ResultGroup>

      <ResultGroup
        title="Инструкторы"
        icon="clover"
        count={result.instructors.length}
        empty="В этом регионе пока нет инструкторов для вашего уровня."
        catalogHref={`${routes.instructors}?region=${encodeURIComponent(region)}`}
        catalogLabel="Все инструкторы региона"
      >
        {result.instructors.map((i) => (
          <li key={i.id}>
            <InstructorCard instructor={i} />
          </li>
        ))}
      </ResultGroup>

      <ResultGroup
        title="Прокат и снаряжение"
        icon="board"
        count={result.rentals.length}
        empty="В этом регионе пока нет предложений проката."
        catalogHref={`${routes.rentals}?region=${encodeURIComponent(region)}`}
        catalogLabel="Вся аренда региона"
      >
        {result.rentals.map((r) => (
          <li key={r.id}>
            <RentalCard rental={r} />
          </li>
        ))}
      </ResultGroup>

      <p className="notice gv-ax-disclaimer" role="note">
        <Icon name="shield" size={16} /> <b>Безопасность.</b> {result.disclaimer}
      </p>
      <p className="gv-ax-micro">
        Правила подбора v{result.rule_version} · сформировано {formatDateTime(result.generated_at, { timeZone: tz })}
      </p>
    </div>
  );
}

function ResultGroup({
  title,
  icon,
  count,
  empty,
  catalogHref,
  catalogLabel,
  children,
}: {
  title: string;
  icon: "target" | "clover" | "board";
  count: number;
  empty: string;
  catalogHref: string;
  catalogLabel: string;
  children: ReactNode;
}) {
  return (
    <section className="gv-ax-group" aria-label={title}>
      <h4 className="gv-ax-subtitle">
        <Icon name={icon} size={18} /> {title} <span className="gv-ax-count">{count}</span>
      </h4>
      {count ? (
        <ul className="gv-ax-cards">{children}</ul>
      ) : (
        <div className="gv-ax-empty">
          <p>{empty}</p>
          <Link href={catalogHref} className="feature-link">
            {catalogLabel} <Icon name="arrow" size={14} />
          </Link>
        </div>
      )}
    </section>
  );
}

function SpotCard({ spot, hazardLabels, tz }: { spot: RecommendedSpot; hazardLabels: Record<string, string>; tz?: string }) {
  // Labels already spelled out in the notes («Камни. …») are not repeated.
  const notes = spot.hazard_notes.toLowerCase();
  const hazards = spot.hazards.map((h) => hazardLabels[h] ?? "").filter((label) => label && !notes.includes(label.toLowerCase()));
  const f = spot.forecast;
  return (
    <article className="gv-ax-card">
      <span className="gv-ax-card-img">
        <MediaImage media={spot.image} alt="" prefer="thumb" />
      </span>
      <div className="gv-ax-card-body">
        <Link href={routes.spot(spot.slug)} className="gv-ax-card-title gv-clamp-2" title={spot.title}>
          {spot.title}
        </Link>
        <small className="gv-clamp-2">{spot.subtitle}</small>
        <span className="gv-ax-card-tags">
          <Tag>{spot.difficulty_label}</Tag>
          {spot.season && <Tag>{spot.season}</Tag>}
          {spot.season_match === true && <Tag variant="verified">Сезон подходит</Tag>}
          {spot.season_match === false && <Tag variant="plain" className="gv-ax-tag-warn">Не лучший сезон</Tag>}
        </span>
        <Rating value={spot.rating_avg} count={spot.rating_count} />
        {spot.typical_conditions && (
          <p className="gv-ax-fact">
            <b>Типичные условия (не прогноз):</b> {spot.typical_conditions}
          </p>
        )}
        {f ? (
          <p className="gv-ax-fact gv-ax-forecast">
            <b>Прогноз {f.provider}</b> на {formatDateRange(f.valid_from, f.valid_to, { timeZone: tz })}:{" "}
            {[
              f.wave_height_m ? `волна ${f.wave_height_m} м` : "",
              f.wave_period_s ? `период ${f.wave_period_s} с` : "",
              f.wind_speed_ms ? `ветер ${f.wind_speed_ms} м/с${f.wind_direction ? ` ${f.wind_direction}` : ""}` : "",
              f.water_temp_c ? `вода ${f.water_temp_c} °C` : "",
            ]
              .filter(Boolean)
              .join(", ")}
            . <small>Выпущен {formatDateTime(f.issued_at, { timeZone: tz })} · {f.source}</small>
          </p>
        ) : (
          <p className="gv-ax-fact gv-ax-muted">Прогноз на дату недоступен — проверьте условия перед выходом.</p>
        )}
        {(hazards.length > 0 || spot.hazard_notes) && (
          <p className="gv-ax-hazard">
            <Icon name="alert" size={14} /> <b>Опасности:</b> {hazards.length ? `${hazards.join(", ")}. ` : ""}
            {spot.hazard_notes}
          </p>
        )}
        {spot.seasonal_warning && (
          <p className="gv-ax-hazard">
            <Icon name="alert" size={14} /> {spot.seasonal_warning}
          </p>
        )}
        <small className="gv-ax-source">Источник: {spot.source}</small>
      </div>
    </article>
  );
}

function InstructorCard({ instructor }: { instructor: RecommendedInstructor }) {
  return (
    <article className="gv-ax-card gv-ax-person">
      <Avatar media={instructor.image} name={instructor.title} size={64} />
      <div className="gv-ax-card-body">
        <Link href={routes.instructor(instructor.handle)} className="gv-ax-card-title gv-clamp-2" title={instructor.title}>
          {instructor.title}
        </Link>
        <small className="gv-clamp-2">{instructor.subtitle}</small>
        <Rating value={instructor.rating_avg} count={instructor.rating_count} />
        <span className="gv-ax-card-tags">
          {instructor.certificate_verified ? (
            <Tag variant="verified" icon="check">
              Сертификат проверен
            </Tag>
          ) : null}
        </span>
        <span className="gv-ax-price">Занятие {formatPriceFrom(instructor.price_from, instructor.currency)}</span>
        <small className="gv-ax-source">Источник: {instructor.source}</small>
      </div>
    </article>
  );
}

function RentalCard({ rental }: { rental: RecommendedRental }) {
  const prices = [
    rental.price_per_day ? `${formatMoney(rental.price_per_day, rental.currency)} / день` : "",
    rental.price_per_hour ? `${formatMoney(rental.price_per_hour, rental.currency)} / час` : "",
  ].filter(Boolean);
  return (
    <article className="gv-ax-card">
      <span className="gv-ax-card-img">
        <MediaImage media={rental.image} alt="" prefer="thumb" />
      </span>
      <div className="gv-ax-card-body">
        <Link href={routes.rental(rental.id)} className="gv-ax-card-title gv-clamp-2" title={rental.title}>
          {rental.title}
        </Link>
        <small className="gv-clamp-2">{rental.subtitle}</small>
        <span className="gv-ax-card-tags">
          <Tag>{rental.kind_label}</Tag>
          {rental.free_on_date === true && <Tag variant="verified">Свободно на дату</Tag>}
          {rental.free_on_date === false && <Tag variant="plain" className="gv-ax-tag-warn">Занято на дату</Tag>}
        </span>
        <span className="gv-ax-price">{prices.length ? prices.join(" · ") : "Цена по договорённости"}</span>
        {rental.owner_name && <small>Сдаёт: {rental.owner_name}</small>}
        <small className="gv-ax-source">Источник: {rental.source}</small>
      </div>
    </article>
  );
}
