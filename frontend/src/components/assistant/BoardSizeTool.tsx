"use client";
/**
 * «Какой объём доски мне нужен» (AIX-03): weight + level + wave → POST /assistant/board-size → volume range,
 * recommended board types, explanation of the rule, warnings and matching boards from the catalogue.
 * Parameters are mirrored into the URL (?weight=&board_level=&wave=) so the result can be shared; a shared link
 * recalculates on open.
 */
import { useEffect, useId, useRef, useState, type FormEvent, type Ref } from "react";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { Button, ButtonLink, ErrorState, Icon, MediaImage, Select, StatusBadge, Tag, TextInput } from "@/components/ui";
import { isApiError } from "@/lib/api/errors";
import { ASSISTANT_LEVELS, ASSISTANT_WAVES, assistantApi, type BoardSizeInput, type BoardSizeResponse, type MatchingBoard } from "@/lib/api/search";
import { formatMoney } from "@/lib/format";
import { routes } from "@/lib/routes";
import {
  BOARD_PARAMS,
  formatLiters,
  replaceQuery,
  validateBoard,
  WEIGHT_MAX,
  WEIGHT_MIN,
  type BoardValues,
  type Errors,
} from "./assistantModel";

type Field = "weight_kg" | "level" | "wave";

export function BoardSizeTool({ initial }: { initial?: BoardValues }) {
  const formId = useId().replace(/:/g, "");
  const [values, setValues] = useState<BoardValues>(initial ?? { weight: "", level: "", wave: "" });
  const [errors, setErrors] = useState<Errors<Field>>({});
  const resultRef = useRef<HTMLHeadingElement>(null);
  const focusResult = useRef(false);

  const mutation = useMutation({
    mutationFn: (body: BoardSizeInput) => assistantApi.boardSize(body),
    onSuccess: (_data, body) => {
      replaceQuery({ [BOARD_PARAMS.weight]: String(body.weight_kg), [BOARD_PARAMS.level]: body.level, [BOARD_PARAMS.wave]: body.wave });
    },
    onError: (err) => {
      if (isApiError(err) && err.isValidation && Object.keys(err.fields).length) {
        const next: Errors<Field> = {};
        for (const key of ["weight_kg", "level", "wave"] as const) if (err.fields[key]?.[0]) next[key] = err.fields[key][0];
        setErrors(next);
      }
    },
  });

  // A shared link (?weight=…) recalculates once on open.
  const autoRun = useRef(false);
  useEffect(() => {
    if (autoRun.current || !initial) return;
    autoRun.current = true;
    const { data } = validateBoard(initial);
    if (data) mutation.mutate(data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (mutation.isSuccess && focusResult.current) {
      focusResult.current = false;
      resultRef.current?.focus();
    }
  }, [mutation.isSuccess, mutation.data]);

  const set = <K extends keyof BoardValues>(key: K, value: BoardValues[K]) => setValues((v) => ({ ...v, [key]: value }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const { data, errors: next } = validateBoard(values);
    setErrors(next);
    if (!data) return;
    focusResult.current = true;
    mutation.mutate(data);
  };

  const result = mutation.data;
  const serverError = mutation.isError && !(isApiError(mutation.error) && mutation.error.isValidation && Object.keys(mutation.error.fields).length);

  return (
    <section className="gv-ax-tool" aria-labelledby={`${formId}-title`}>
      <div className="gv-ax-tool-head">
        <span className="gv-ax-tool-icon" aria-hidden="true">
          <Icon name="ruler" size={22} />
        </span>
        <div>
          <h2 id={`${formId}-title`}>Какой объём доски мне нужен?</h2>
          <p>Расчёт по гильд-фактору: вес × коэффициент уровня × поправка на волну.</p>
        </div>
      </div>

      <form id={formId} className="gv-ax-form" onSubmit={submit} noValidate aria-describedby={`${formId}-note`}>
        <TextInput
          label="Ваш вес, кг"
          required
          inputMode="decimal"
          autoComplete="off"
          placeholder="Например, 72"
          maxLength={6}
          value={values.weight}
          onChange={(e) => set("weight", e.target.value)}
          error={errors.weight_kg}
          hint={`От ${WEIGHT_MIN} до ${WEIGHT_MAX} кг`}
        />
        <Select
          label="Уровень катания"
          required
          placeholder="Выберите уровень"
          options={ASSISTANT_LEVELS}
          value={values.level}
          onChange={(e) => set("level", e.target.value as BoardValues["level"])}
          error={errors.level}
        />
        <Select
          label="Волна, на которой катаетесь"
          required
          placeholder="Выберите волну"
          options={ASSISTANT_WAVES}
          value={values.wave}
          onChange={(e) => set("wave", e.target.value as BoardValues["wave"])}
          error={errors.wave}
        />
        <div className="gv-ax-actions">
          <Button type="submit" variant="primary" iconRight="arrow" loading={mutation.isPending}>
            Рассчитать объём
          </Button>
        </div>
        <p id={`${formId}-note`} className="gv-ax-micro">
          Данные никуда не сохраняются: расчёт идёт по открытой формуле, без ИИ.
        </p>
      </form>

      <div className="gv-ax-result-wrap">
        <p className="sr-only" role="status" aria-live="polite">
          {mutation.isPending
            ? "Считаем объём…"
            : result
              ? `Рекомендованный объём от ${formatLiters(result.volume_l.min)} до ${formatLiters(result.volume_l.max)} литров.`
              : ""}
        </p>
        {serverError ? (
          <ErrorState
            compact
            error={mutation.error}
            title="Не удалось рассчитать"
            onRetry={() => {
              const { data } = validateBoard(values);
              if (data) mutation.mutate(data);
            }}
          />
        ) : result ? (
          <BoardSizeResult result={result} headingRef={resultRef} stale={mutation.isPending} />
        ) : (
          <div className="gv-ax-placeholder">
            <Icon name="board" size={28} />
            <p>Заполните три поля — покажем диапазон объёма, подходящие типы досок и модели из каталога.</p>
          </div>
        )}
      </div>
    </section>
  );
}

export function BoardSizeResult({
  result,
  headingRef,
  stale,
}: {
  result: BoardSizeResponse;
  headingRef?: Ref<HTMLHeadingElement>;
  stale?: boolean;
}) {
  return (
    <div className="gv-ax-result" aria-busy={stale || undefined}>
      <h3 ref={headingRef} tabIndex={-1} className="gv-ax-result-title">
        Рекомендованный объём
      </h3>
      <p className="gv-ax-volume">
        <b>
          {formatLiters(result.volume_l.min)}–{formatLiters(result.volume_l.max)}
        </b>{" "}
        л
      </p>
      {result.board_types.length > 0 && (
        <div className="gv-ax-types">
          <span className="gv-ax-label">Подходящие типы досок:</span>
          <ul>
            {result.board_types.map((t) => (
              <li key={t.code}>
                <Tag>{t.name}</Tag>
              </li>
            ))}
          </ul>
        </div>
      )}
      {result.warnings.map((w) => (
        <p key={w} className="notice gv-ax-warning" role="note">
          <Icon name="alert" size={16} /> {w}
        </p>
      ))}
      <p className="gv-ax-explain">{result.explanation}</p>
      <details className="gv-ax-formula">
        <summary>Как считали</summary>
        <ul>
          <li>
            Гильд-фактор уровня: {formatLiters(result.formula.guild_factor.min)}–{formatLiters(result.formula.guild_factor.max)}
          </li>
          <li>Поправка на волну: ×{formatLiters(result.formula.wave_factor)}</li>
          <li>Версия правил: {result.formula.rule_version}</li>
        </ul>
      </details>

      <h4 className="gv-ax-subtitle">Доски в каталоге с подходящим объёмом</h4>
      {result.matching_boards.length ? (
        <ul className="gv-ax-boards">
          {result.matching_boards.map((b) => (
            <li key={b.variant_id}>
              <MatchingBoardCard board={b} />
            </li>
          ))}
        </ul>
      ) : (
        <div className="gv-ax-empty">
          <p>В каталоге пока нет досок такого объёма. Посмотрите все доски или напишите шейперу — он сделает под вас.</p>
          <ButtonLink href={routes.boardsCatalog} variant="pill" iconRight="arrow">
            Все доски
          </ButtonLink>
        </div>
      )}
      <p className="notice gv-ax-disclaimer" role="note">
        <Icon name="info" size={16} /> {result.disclaimer}
      </p>
    </div>
  );
}

function MatchingBoardCard({ board }: { board: MatchingBoard }) {
  const dims = [board.length_label, `${formatLiters(board.width_in)}″`, `${formatLiters(board.volume_l)} л`].filter(Boolean).join(" · ");
  return (
    <Link href={routes.board(board.model_id)} className="gv-ax-card gv-ax-board">
      <span className="gv-ax-card-img">
        <MediaImage media={board.image} alt="" prefer="thumb" />
      </span>
      <span className="gv-ax-card-body">
        <b className="gv-clamp-2" title={board.title}>
          {board.title}
        </b>
        <small className="gv-clamp-1">{board.subtitle}</small>
        <span className="gv-ax-card-meta">{dims}</span>
        <span className="gv-ax-card-tags">
          <StatusBadge domain="availability" status={board.availability} />
          {board.type_match && <Tag variant="verified">Тип подходит</Tag>}
        </span>
        {board.price && <span className="gv-ax-price">{formatMoney(board.price, board.currency)}</span>}
        <small className="gv-ax-source">{board.source}</small>
      </span>
    </Link>
  );
}
