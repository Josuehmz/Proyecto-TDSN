"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [tenant, setTenant] = useState("acme");
  const [email, setEmail] = useState("admin@acme.test");
  const [password, setPassword] = useState("Acme_Admin_2026!");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const notice = sessionStorage.getItem("rag_notice");
    if (notice) {
      setError(notice);
      sessionStorage.removeItem("rag_notice");
    }
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const resp = await login(tenant, email, password);
      sessionStorage.setItem("rag_token", resp.access_token);
      sessionStorage.setItem("rag_principal", JSON.stringify(resp.principal));
      router.push("/chat");
    } catch (err: any) {
      setError(err.message || "Error al iniciar sesión");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">
        <h1 className="mb-1 text-2xl font-bold text-slate-900">
          RAG Multi-Tenant
        </h1>
        <p className="mb-6 text-sm text-slate-500">
          Prototipo — inicia sesión indicando tenant, usuario y contraseña.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Tenant">
            <input
              className="input"
              value={tenant}
              onChange={(e) => setTenant(e.target.value)}
              required
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </Field>
          <Field label="Contraseña">
            <input
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </Field>

          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-brand-600 py-2.5 font-semibold text-white transition hover:bg-brand-700 disabled:opacity-60"
          >
            {loading ? "Ingresando…" : "Ingresar"}
          </button>
        </form>

        <details className="mt-6 text-xs text-slate-500">
          <summary className="cursor-pointer font-semibold">
            Usuarios de demo
          </summary>
          <ul className="ml-4 mt-2 list-disc space-y-0.5">
            <li>acme / admin@acme.test / Acme_Admin_2026!</li>
            <li>acme / legal@acme.test / Acme_Legal_2026!</li>
            <li>acme / intern@acme.test / Acme_Intern_2026!</li>
            <li>globex / admin@globex.test / Globex_Admin_2026!</li>
            <li>globex / finance@globex.test / Globex_Fin_2026!</li>
            <li>globex / employee@globex.test / Globex_Emp_2026!</li>
          </ul>
        </details>
      </div>
      <style jsx>{`
        .input {
          @apply w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100;
        }
      `}</style>
    </main>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">
        {label}
      </span>
      {children}
    </label>
  );
}
