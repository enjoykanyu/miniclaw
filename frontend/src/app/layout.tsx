import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import "./globals.css";

const displayFont = Inter({
  subsets: ["latin"],
  variable: "--font-display"
});

const monoFont = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono"
});

export const metadata: Metadata = {
  title: "MiniClaw - 个人智能助手",
  description: "基于 LangGraph 的多 Agent 个人 AI 助手"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={`${displayFont.variable} ${monoFont.variable} font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
