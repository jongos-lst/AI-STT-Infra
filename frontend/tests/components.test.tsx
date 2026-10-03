import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { StatusBadge } from "@/components/StatusBadge";
import { ProgressBar } from "@/components/ProgressBar";

describe("React component transforms", () => {
  it("renders a task status using the automatic JSX runtime", () => {
    const container = document.createElement("div");
    container.innerHTML = renderToStaticMarkup(<StatusBadge status="DONE" />);

    expect(container.textContent).toBe("Done");
    expect(container.querySelector("span")?.classList.contains("bg-emerald-100")).toBe(true);
  });

  it("renders failed progress at 100 percent with the failure style", () => {
    const container = document.createElement("div");
    container.innerHTML = renderToStaticMarkup(<ProgressBar status="FAILED" />);
    const progress = container.querySelector<HTMLElement>('[role="progressbar"]');

    expect(progress?.getAttribute("aria-valuenow")).toBe("100");
    expect(progress?.style.width).toBe("100%");
    expect(progress?.classList.contains("bg-rose-500")).toBe(true);
  });
});
