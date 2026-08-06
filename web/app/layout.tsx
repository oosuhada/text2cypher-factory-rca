import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { ProjectProvider } from "@/components/project-context";

import "./globals.css";

const geist = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: {
    default: "FactoryGraph RCA",
    template: "%s · FactoryGraph RCA",
  },
  description:
    "제조 데이터를 지식그래프로 연결하고 자연어 질문을 검증 가능한 Cypher와 RCA 근거 경로로 전환합니다.",
  openGraph: {
    title: "FactoryGraph RCA",
    description:
      "자연어 질문에서 읽기 전용 Cypher와 제조 RCA 근거 경로까지.",
    images: [
      {
        url: "/factory-graph-social.png",
        width: 1200,
        height: 630,
        alt: "제조 부품부터 품질 결과까지 이어지는 지식그래프",
      },
    ],
    locale: "ko_KR",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "FactoryGraph RCA",
    description:
      "자연어 질문에서 읽기 전용 Cypher와 제조 RCA 근거 경로까지.",
    images: ["/factory-graph-social.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="ko"
      suppressHydrationWarning
      data-scroll-behavior="smooth"
    >
      <body className={`${geist.variable} ${geistMono.variable}`}>
        <ProjectProvider>
          <SiteHeader />
          <main>{children}</main>
          <SiteFooter />
        </ProjectProvider>
      </body>
    </html>
  );
}
