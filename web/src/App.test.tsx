import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { applyTheme, resolveInitialTheme, toggleTheme } from "./theme";

vi.mock("react-force-graph-2d", () => ({
  default: () => <div data-testid="graph-canvas-mock">graph canvas</div>,
}));

vi.mock("./components/NigeriaMap", () => ({
  NigeriaMap: () => <div data-testid="nigeria-map">map canvas</div>,
}));

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
    expect(await screen.findByText(/no parties match/i)).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Parties" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Tenders" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Flags" })).toBeTruthy();
  });

  it("switches explore resource and shows flag hypothesis copy", async () => {
    stubMatchMedia(false);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ items: [], limit: 50, offset: 0, count: 0 }),
      }),
    );

    render(<App />);
    fireEvent.click(screen.getByRole("link", { name: "Explore" }));
    await screen.findByRole("heading", { name: "Explore" });
    fireEvent.click(screen.getByRole("tab", { name: "Flags" }));
    expect(await screen.findByText(/hypotheses pending human review/i)).toBeTruthy();
  });

  it("compares two parties side by side", async () => {
    stubMatchMedia(false);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "11111111-1111-1111-1111-111111111111",
              party_type: "agency",
              canonical_name: "Ministry A",
              aliases: [],
              merged_into_id: null,
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-02T00:00:00Z",
            },
            {
              id: "22222222-2222-2222-2222-222222222222",
              party_type: "company",
              canonical_name: "Vendor B",
              aliases: ["VB"],
              merged_into_id: null,
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-03T00:00:00Z",
            },
          ],
          limit: 50,
          offset: 0,
          count: 2,
        }),
      }),
    );

    render(<App />);
    fireEvent.click(screen.getByRole("link", { name: "Explore" }));
    expect(await screen.findByText("Ministry A")).toBeTruthy();
    fireEvent.click(screen.getByRole("checkbox", { name: /compare ministry a/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /compare vendor b/i }));
    expect(await screen.findByRole("heading", { name: "Compare" })).toBeTruthy();
    expect(screen.getAllByText("Vendor B").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByLabelText("Party types")).toBeTruthy();
  });

  it("lists sources and drills into detail", async () => {
    stubMatchMedia(false);
    const source = {
      id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      name: "Open Treasury demo",
      url: "https://example.test/treasury",
      jurisdiction: "federal",
      region: null,
      category: "payments",
      format: "html",
      fetch_method: "http",
      status: "approved",
      health_status: "ok",
      expected_cadence: 86400,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: RequestInfo) => {
        const url = String(input);
        if (url.includes("/v1/sources/") && !url.endsWith("/v1/sources")) {
          return { ok: true, json: async () => source };
        }
        if (url.includes("/v1/sources")) {
          return {
            ok: true,
            json: async () => ({ items: [source], limit: 50, offset: 0, count: 1 }),
          };
        }
        return { ok: true, json: async () => ({ items: [], limit: 50, offset: 0, count: 0 }) };
      }),
    );

    render(<App />);
    fireEvent.click(screen.getByRole("link", { name: "Sources" }));
    expect(await screen.findByRole("heading", { name: "Sources" })).toBeTruthy();
    fireEvent.click(screen.getByRole("link", { name: /open treasury demo/i }));
    expect(await screen.findByRole("heading", { name: "Open Treasury demo" })).toBeTruthy();
    expect(screen.getByText("https://example.test/treasury")).toBeTruthy();
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
    expect(screen.getByText("Export dossier")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download JSON" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download Markdown" })).toBeTruthy();
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

  it("opens the demo graph page from nav", async () => {
    stubMatchMedia(false);
    render(<App />);
    fireEvent.click(screen.getByRole("link", { name: "Graph" }));
    expect(await screen.findByRole("heading", { name: "Graph" })).toBeTruthy();
    expect(screen.getByText(/illustrative demo — not a live memgraph/i)).toBeTruthy();
    expect(screen.getByTestId("graph-canvas")).toBeTruthy();
    expect(screen.getByPlaceholderText(/search parties/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Parties" })).toBeTruthy();
  });

  it("opens the demo map page from nav", async () => {
    stubMatchMedia(false);
    render(<App />);
    fireEvent.click(screen.getByRole("link", { name: "Map" }));
    expect(await screen.findByRole("heading", { name: "Map" })).toBeTruthy();
    expect(screen.getByText(/illustrative demo — not live totals/i)).toBeTruthy();
    expect(screen.getByTestId("nigeria-map")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Contract volume" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Anomaly density" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /top /i })).toBeTruthy();
  });
});
