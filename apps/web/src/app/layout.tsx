import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Intel Radar",
  description: "AI intelligence feed, ranking, search and source monitoring.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

