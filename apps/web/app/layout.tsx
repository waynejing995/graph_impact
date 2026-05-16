import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ASIP Evidence Workbench",
  description: "Hybrid evidence retrieval workbench for AMD GPU engineering corpora"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html data-theme="dark" lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
