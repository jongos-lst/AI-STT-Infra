import { describe, expect, it, beforeEach, vi } from "vitest";
import { ApiClientError, api, uploadToSignedUrl } from "@/lib/api";

describe("api client", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("createTask issues a POST and parses CreateTaskResponse", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          task_id: "11111111-1111-1111-1111-111111111111",
          upload_url: "https://signed.example.com/abc",
          upload_method: "PUT",
          upload_headers: { "Content-Type": "audio/mpeg", "X-Goog-Content-Length-Range": "0,1024" },
          expires_in_seconds: 900,
        }),
        { status: 201 },
      ),
    );

    const out = await api.createTask({
      filename: "x.mp3",
      content_type: "audio/mpeg",
      audio_sha256: "a".repeat(64),
      audio_bytes: 1024,
    });

    expect(out.task_id).toMatch(/^[0-9a-f-]{36}$/);
    expect(out.upload_method).toBe("PUT");
    const call = fetchMock.mock.calls[0];
    expect(String(call[0])).toMatch(/\/v1\/tasks$/);
    expect((call[1] as RequestInit).method).toBe("POST");
  });

  it("wraps non-2xx in ApiClientError carrying status + parsed body", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "rate_limited", message: "slow down" } }), {
        status: 429,
      }),
    );

    await expect(api.getTask("xx")).rejects.toMatchObject({
      status: 429,
      message: "slow down",
    });
    await expect(api.getTask("xx")).rejects.toBeInstanceOf(ApiClientError);
  });

  it("uploadToSignedUrl sends file as the request body with provided headers", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(new Response("", { status: 200 }));
    const file = new File(["hello"], "x.mp3", { type: "audio/mpeg" });

    await uploadToSignedUrl(
      "https://signed.example.com/abc",
      { "Content-Type": "audio/mpeg", "X-Goog-Content-Length-Range": "0,5" },
      file,
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://signed.example.com/abc");
    expect((init as RequestInit).method).toBe("PUT");
    expect((init as RequestInit).body).toBe(file);
    const headers = (init as RequestInit).headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("audio/mpeg");
  });
});
