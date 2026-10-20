import type { Metadata } from "next";
import { Manrope } from "next/font/google";
import "./globals.css";

const manrope = Manrope({ subsets: ["latin"], variable: "--font-manrope" });
export const metadata: Metadata = {
  title: "PulsePilot — Find your steady signal",
  description: "A guided webcam heart-rate measurement with honest signal quality, actionable feedback, and evidence-grounded reports.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className={manrope.variable}>{children}</body></html>;
}
