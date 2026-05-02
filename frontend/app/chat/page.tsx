"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Principal, QueryResponse, sendQuery } from "@/lib/api";

type Message =
  | { role: "user"; content: string }
  | { role: "assistant"; content: QueryResponse };

export default function ChatPage() {
  const router = useRouter();
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const viewportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = sessionStorage.getItem("rag_token");
    const p = sessionStorage.getItem("rag_principal");
    if (!t || !p) {
      router.replace("/");
      return;
    }
    setToken(t);
    setPrincipal(JSON.parse(p));
  }, [router]);

  useEffect(() => {
    viewportRef.current?.scrollTo({
      top: viewportRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const headerLabel = useMemo(() => {
    if (!principal) return "";
    return `${principal.email} — tenant ${principal.tenant} · clearance ${principal.clearance} · roles ${principal.roles.join(", ") || "—"}`;
  }, [principal]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || !token) return;
    const userMsg: Message = { role: "user", content: input.trim() };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const response = await sendQuery(token, userMsg.content);
      setMessages((m) => [...m, { role: "assistant", content: response }]);
    } catch (err: any) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: {
            request_id: "error",
            answered: false,
            answer: `Error: ${err.message}`,
            citations: [],
            policy_reasons: [],
            retrieved: 0,
            top_score: 0,
            latency_ms: 0,
            tokens: {},
          },
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    sessionStorage.clear();
    router.replace("/");
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-4 p-4">
      <header className="flex items-center justify-between rounded-xl bg-white px-5 py-3 shadow">
        <div>
          <h1 className="text-lg font-bold">RAG Multi-Tenant</h1>
          <p className="text-xs text-slate-500">{headerLabel}</p>
        </div>
        <button
          onClick={logout}
          className="text-sm font-semibold text-brand-700 hover:underline"
        >
          Cerrar sesión
        </button>
      </header>

      <section
        ref={viewportRef}
        className="flex-1 space-y-4 overflow-y-auto rounded-xl bg-white p-5 shadow"
      >
        {messages.length === 0 && (
          <p className="text-sm text-slate-400">
            Prueba con: <em>“¿Cuál es la palabra clave pública de la
            organización?”</em> o con una pregunta intencionalmente fuera de
            alcance para validar el modo <code>NO_ANSWER</code>.
          </p>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <UserBubble key={i} text={m.content} />
          ) : (
            <AssistantBubble key={i} data={m.content} />
          )
        )}
        {loading && <p className="text-sm text-slate-400">Pensando…</p>}
      </section>

      <form onSubmit={handleSend} className="flex gap-2">
        <input
          className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          placeholder="Escribe tu pregunta…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-xl bg-brand-600 px-5 py-3 font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
        >
          Enviar
        </button>
      </form>
    </main>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-brand-600 px-4 py-2 text-white">
        {text}
      </div>
    </div>
  );
}

function AssistantBubble({ data }: { data: QueryResponse }) {
  const badge = data.answered
    ? "bg-green-100 text-green-700"
    : "bg-yellow-100 text-yellow-800";
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <span className={`rounded-full px-2 py-0.5 font-semibold ${badge}`}>
          {data.answered ? "ANSWERED" : "NO_ANSWER"}
        </span>
        <span>
          top={data.top_score.toFixed(3)} · {data.retrieved} recuperados ·{" "}
          {data.latency_ms.toFixed(0)} ms
        </span>
      </div>
      <div className="whitespace-pre-wrap rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-3 text-sm">
        {data.answer}
      </div>
      {data.citations.length > 0 && (
        <details className="text-xs text-slate-600">
          <summary className="cursor-pointer font-semibold">
            Citas ({data.citations.length})
          </summary>
          <ol className="mt-2 space-y-2">
            {data.citations.map((c) => (
              <li
                key={c.chunk_id}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2"
              >
                <div className="font-semibold">
                  [#{c.index}] {c.document_title} · fragmento {c.ordinal}{" "}
                  <span className="font-normal text-slate-400">
                    (score {c.score.toFixed(3)})
                  </span>
                </div>
                <div className="mt-1 text-slate-600">{c.snippet}</div>
              </li>
            ))}
          </ol>
        </details>
      )}
      {data.policy_reasons.length > 0 && (
        <details className="text-xs text-slate-500">
          <summary className="cursor-pointer">Trazas de política</summary>
          <ul className="ml-4 mt-1 list-disc">
            {data.policy_reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
