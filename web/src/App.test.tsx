import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { applyTheme, resolveInitialTheme, toggleTheme } from "./theme";

afterEach(() => {
  cleanup();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  vi.unstubAllGlobals();
});

function stubMatchMedia(dark = false): void {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: dark && query.includes("dark"),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

describe("theme", () => {
  it("applies light or dark to documentElement", () => {
    stubMatchMedia(false);
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("toggles and persists", () => {
    stubMatchMedia(false);
    applyTheme("light");
    expect(toggleTheme("light")).toBe("dark");
    expect(localStorage.getItem("naijaledger-theme")).toBe("dark");
    expect(resolveInitialTheme()).toBe("dark");
  });
});

function stubIntersectionObserver(): void {
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe(): void {}
      unobserve(): void {}
      disconnect(): void {}
    },
  );
}

describe("App routes", () => {
  it("renders brand-first home and navigates to explore", async () => {
    stubMatchMedia(false);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ items: [], limit: 50, offset: 0, count: 0 }),
      }),
    );

    render(<App />);
    expect(screen.getAllByText("NaijaLedger").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("heading", { name: /follow the money/i })).toBeTruthy();

    fireEvent.click(screen.getByRole("link", { name: "Explore" }));
    expect(await screen.findByRole("heading", { name: "Explore" })).toBeTruthy();
    expect(await screen.findByText(/no parties yet/i)).toBeTruthy();
  });

  it("lists stories and opens the demo scrollytelling narrative", async () => {
    stubMatchMedia(false);
    stubIntersectionObserver();

    render(<App />);
    fireEvent.click(screen.getByRole("link", { name: "Stories" }));
    expect(await screen.findByRole("heading", { name: "Stories" })).toBeTruthy();
    expect(screen.getByText("Follow the ledger")).toBeTruthy();

    fireEvent.click(screen.getByRole("link", { name: /follow the ledger/i }));
    expect(await screen.findByRole("heading", { name: "Follow the ledger" })).toBeTruthy();
    expect(screen.getByText(/illustrative demo — not a published claim/i)).toBeTruthy();
    expect(screen.getByRole("heading", { name: /start from a public source/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Browse sources" })).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "Explore parties" }).length).toBeGreaterThanOrEqual(
      1,
    );
  });

  it("shows not-found for unknown story slugs", async () => {
    stubMatchMedia(false);
    stubIntersectionObserver();
    window.history.pushState({}, "", "/stories/does-not-exist");

    render(<App />);
    expect(await screen.findByRole("heading", { name: "Story not found" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to stories" })).toBeTruthy();
  });
});
