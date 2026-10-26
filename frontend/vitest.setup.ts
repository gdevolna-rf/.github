import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { navigation, navigationMock } from "./src/test/navigation";

// next/navigation has no router outside the Next runtime — use the controllable mock (src/test/navigation.ts)
vi.mock("next/navigation", () => navigationMock);

afterEach(() => {
  cleanup();
  navigation.reset();
  vi.unstubAllGlobals();
  document.body.removeAttribute("data-scroll-locked");
  document.body.style.overflow = "";
});
