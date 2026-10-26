import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { resetCsrfForTests } from "@/lib/api/client";
import { networkError } from "@/lib/api/errors";
import type { Media } from "@/lib/api/types";
import { clearCookies, CSRF_OK, json, mockApi } from "@/test/utils";
import { MediaUploader } from "./MediaUploader";

const media = (id: string, extra: Partial<Media> = {}): Media => ({
  id,
  kind: "image",
  purpose: "board_photo",
  visibility: "public",
  status: "ready",
  url: `/m/${id}.jpg`,
  thumbnail_url: `/m/${id}.thumb.webp`,
  poster_url: null,
  content_type: "image/jpeg",
  size_bytes: 1000,
  width: 10,
  height: 10,
  duration_seconds: null,
  alt_text: "",
  original_filename: `${id}.jpg`,
  ...extra,
});

const file = (name: string, type = "image/jpeg", size = 1024) => new File([new Uint8Array(size)], name, { type });

function Harness({
  initial = [],
  onChange,
  onCoverChange,
  uploader,
  withCover,
}: {
  initial?: Media[];
  onChange?: (m: Media[]) => void;
  onCoverChange?: (id: string) => void;
  uploader?: Parameters<typeof MediaUploader>[0]["uploader"];
  withCover?: boolean;
}) {
  const [items, setItems] = useState(initial);
  const [cover, setCover] = useState<string | null>(initial[0]?.id ?? null);
  return (
    <MediaUploader
      purpose="board_photo"
      value={items}
      onChange={(next) => {
        setItems(next);
        onChange?.(next);
      }}
      coverId={withCover ? cover : undefined}
      onCoverChange={
        withCover
          ? (id) => {
              setCover(id);
              onCoverChange?.(id);
            }
          : undefined
      }
      uploader={uploader}
    />
  );
}

/** Minimal XMLHttpRequest stand-in: records headers, reports progress, answers `status`. */
class FakeXHR {
  static instances: FakeXHR[] = [];
  static status = 200;
  method = "";
  url = "";
  headers: Record<string, string> = {};
  status = 0;
  upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  constructor() {
    FakeXHR.instances.push(this);
  }
  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  setRequestHeader(k: string, v: string) {
    this.headers[k] = v;
  }
  send() {
    setTimeout(() => {
      this.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 });
      this.status = FakeXHR.status;
      this.onload?.();
    }, 0);
  }
  abort() {
    this.onabort?.();
  }
}

beforeEach(() => {
  resetCsrfForTests();
  clearCookies();
  FakeXHR.instances = [];
  FakeXHR.status = 200;
});

describe("MediaUploader (UX-08/09, BRD-03)", () => {
  it("runs the presigned flow: ticket → PUT with the returned headers → complete → ready", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const api = mockApi({
      "GET /api/v1/auth/csrf": CSRF_OK,
      "POST /api/v1/media/uploads": ({ body }) =>
        json(
          {
            id: "new1",
            upload_url: "http://localhost:8080/gdevolna-media/public/board_photo/new1.jpg?X-Amz-Signature=x",
            method: "PUT",
            headers: { "Content-Type": "image/jpeg", "If-None-Match": "*" },
            media: media("new1", { status: "pending", url: null, thumbnail_url: null }),
            echo: body,
          },
          201,
        ),
      "POST /api/v1/media/new1/complete": () => json(media("new1", { status: "processing" })),
      "GET /api/v1/media/new1": () => json(media("new1")),
    });
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await user.upload(screen.getByTestId("media-input"), file("board.jpg"));

    await waitFor(() => expect(onChange).toHaveBeenCalledWith([expect.objectContaining({ id: "new1", status: "ready" })]));
    expect(api.calls("POST /api/v1/media/uploads")[0].body).toEqual({
      kind: "image",
      purpose: "board_photo",
      filename: "board.jpg",
      content_type: "image/jpeg",
      size: 1024,
    });
    expect(FakeXHR.instances).toHaveLength(1);
    expect(FakeXHR.instances[0].method).toBe("PUT");
    expect(FakeXHR.instances[0].headers).toEqual({ "Content-Type": "image/jpeg", "If-None-Match": "*" });
    expect(api.calls("POST /api/v1/media/new1/complete")).toHaveLength(1);
    expect(await screen.findByRole("img", { name: "Фото 1" })).toHaveAttribute("src", "/m/new1.thumb.webp");
    expect(screen.getByText("Обложка")).toBeInTheDocument();
  });

  it("never exceeds 10 photos and explains why extra files were skipped", async () => {
    const user = userEvent.setup();
    const uploader = vi.fn(async (f: File) => media(`up-${f.name}`));
    const initial = Array.from({ length: 9 }, (_, i) => media(`m${i}`));
    const onChange = vi.fn();
    render(<Harness initial={initial} onChange={onChange} uploader={uploader} />);
    expect(screen.getByText("9 из 10")).toBeInTheDocument();
    await user.upload(screen.getByTestId("media-input"), [file("a.jpg"), file("b.jpg"), file("c.jpg")]);
    expect(await screen.findByRole("alert")).toHaveTextContent("Можно добавить ещё 1 фото (максимум 10). Лишние файлы не добавлены.");
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith(expect.arrayContaining([expect.objectContaining({ id: "up-a.jpg" })])));
    expect(uploader).toHaveBeenCalledTimes(1);
    expect(screen.getByText("10 из 10")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Выбрать фото" })).toBeDisabled();
  });

  it("rejects wrong types and oversized files before any request", async () => {
    const user = userEvent.setup({ applyAccept: false });
    const uploader = vi.fn();
    render(<Harness uploader={uploader} />);
    await user.upload(screen.getByTestId("media-input"), [file("doc.pdf", "application/pdf"), file("huge.jpg", "image/jpeg", 16 * 1024 * 1024)]);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("«doc.pdf»: неподходящий формат");
    expect(alert).toHaveTextContent("«huge.jpg»: файл больше 15 МБ");
    expect(uploader).not.toHaveBeenCalled();
  });

  it("deletes a photo with the × button", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Harness initial={[media("m1"), media("m2"), media("m3")]} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: "Удалить фото 2" }));
    expect(onChange).toHaveBeenLastCalledWith([expect.objectContaining({ id: "m1" }), expect.objectContaining({ id: "m3" })]);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("selects the cover explicitly or moves the photo first", async () => {
    const user = userEvent.setup();
    const onCoverChange = vi.fn();
    const { unmount } = render(<Harness initial={[media("m1"), media("m2")]} withCover onCoverChange={onCoverChange} />);
    await user.click(screen.getByRole("button", { name: "Сделать фото 2 обложкой" }));
    expect(onCoverChange).toHaveBeenCalledWith("m2");
    expect(within(screen.getAllByRole("listitem")[1]).getByText("Обложка")).toBeInTheDocument();
    unmount();

    const onChange = vi.fn();
    render(<Harness initial={[media("m1"), media("m2")]} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: "Сделать фото 2 обложкой" }));
    expect(onChange).toHaveBeenLastCalledWith([expect.objectContaining({ id: "m2" }), expect.objectContaining({ id: "m1" })]);
    await user.click(screen.getByRole("button", { name: "Переместить фото 1 правее" }));
    expect(onChange).toHaveBeenLastCalledWith([expect.objectContaining({ id: "m1" }), expect.objectContaining({ id: "m2" })]);
  });

  it("shows a clear network error on the tile and retries", async () => {
    const user = userEvent.setup();
    let attempt = 0;
    const uploader = vi.fn(async () => {
      attempt += 1;
      if (attempt === 1) throw networkError();
      return media("ok");
    });
    const onChange = vi.fn();
    render(<Harness uploader={uploader} onChange={onChange} />);
    await user.upload(screen.getByTestId("media-input"), file("wave.jpg"));
    expect(await screen.findByText(/Нет соединения с сервером/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Повторить/ }));
    await waitFor(() => expect(onChange).toHaveBeenCalledWith([expect.objectContaining({ id: "ok" })]));
    expect(uploader).toHaveBeenCalledTimes(2);
  });

  it("keeps the video in a separate compact tile with duration and delete", async () => {
    const user = userEvent.setup();
    function VideoHarness() {
      const [video, setVideo] = useState<Media | null>(media("v1", { kind: "video", duration_seconds: 65, original_filename: "promo.mp4", poster_url: "/m/v1.jpg" }));
      return <MediaUploader purpose="board_photo" value={[]} onChange={() => {}} video={{ purpose: "board_video", value: video, onChange: setVideo }} />;
    }
    render(<VideoHarness />);
    expect(screen.getByText("promo.mp4")).toBeInTheDocument();
    expect(screen.getAllByText("1:05").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Удалить видео" }));
    expect(screen.getByRole("button", { name: /Добавить видео/ })).toBeInTheDocument();
  });
});
