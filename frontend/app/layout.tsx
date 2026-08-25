import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = { title: "GoldAgent", description: "Gold market intelligence and advisory Agent" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body><Providers><AppShell>{children}</AppShell></Providers></body></html>;
}
