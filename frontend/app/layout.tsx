import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "RAG Multi-Tenant — Prototipo",
  description:
    "Prototipo de la plataforma empresarial RAG multi-tenant descrita en el artículo.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
