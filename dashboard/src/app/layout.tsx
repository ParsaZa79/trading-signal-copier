import type { Metadata } from "next";
import { JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ClerkRootProvider } from "@/components/auth/clerk-root-provider";
import { DashboardLayout } from "@/components/layout/dashboard-layout";

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "Signal Copier | Dashboard",
  description: "Beginner-first MT5 copy trading dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${jetbrainsMono.variable} font-sans antialiased bg-mesh noise-overlay`}
      >
        <ClerkRootProvider>
          <DashboardLayout>{children}</DashboardLayout>
        </ClerkRootProvider>
      </body>
    </html>
  );
}
