/**
 * Next.js Route Handler — SSE stream proxy (T-604 streaming fix).
 *
 * Next.js dev rewrites buffer SSE chunks because the Node.js HTTP proxy layer
 * accumulates data before forwarding. This Route Handler pipes the upstream SSE
 * response directly as a ReadableStream, flushing each chunk immediately so the
 * browser receives text_delta events incrementally.
 *
 * The rewrite in next.config.js still covers all other /api/* paths.
 * This file takes precedence over the rewrite for this specific path only.
 */
import { type NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

interface RouteParams {
  params: Promise<{ sessionId: string }>;
}

export async function GET(req: NextRequest, { params }: RouteParams): Promise<NextResponse | Response> {
  const { sessionId } = await params;
  const upstreamUrl = `${API_URL}/api/v1/sessions/${sessionId}/stream`;

  // Forward the original request headers (including X-Dev-User auth header).
  const forwardHeaders: Record<string, string> = {};
  req.headers.forEach((value, key) => {
    // Skip host/connection headers that should not be forwarded verbatim.
    if (key !== "host" && key !== "connection" && key !== "keep-alive") {
      forwardHeaders[key] = value;
    }
  });

  let upstreamRes: globalThis.Response;
  try {
    upstreamRes = await fetch(upstreamUrl, {
      method: "GET",
      headers: forwardHeaders,
      // @ts-expect-error -- Node.js fetch supports duplex for streaming; type not in lib
      duplex: "half",
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "upstream unreachable";
    return NextResponse.json({ error: message }, { status: 502 });
  }

  if (!upstreamRes.body) {
    return new Response(null, { status: 204 });
  }

  // Stream the upstream body directly to the client without buffering.
  return new Response(upstreamRes.body, {
    status: upstreamRes.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
      "Transfer-Encoding": "identity",
    },
  });
}
