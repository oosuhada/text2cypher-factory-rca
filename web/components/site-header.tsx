"use client";

import {
  Activity,
  Database,
  History,
  Menu,
  MessageSquareText,
  Network,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ApiStatus } from "@/components/api-status";
import { ThemeToggle } from "@/components/theme-toggle";

const NAVIGATION = [
  { href: "/query", label: "Query", icon: MessageSquareText },
  { href: "/graph", label: "Graph", icon: Network },
  { href: "/history", label: "History", icon: History },
  { href: "/data", label: "Data", icon: Database },
  { href: "/operations", label: "Operations", icon: Activity },
];

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="site-header">
      <div className="shell header-inner">
        <Link href="/" className="brand-lockup" aria-label="FactoryGraph 홈">
          <span className="brand-mark">
            <span />
            <span />
            <span />
          </span>
          <span>FactoryGraph</span>
          <small>RCA</small>
        </Link>

        <nav className={`primary-nav ${open ? "nav-open" : ""}`}>
          {NAVIGATION.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                href={item.href}
                key={item.href}
                className={active ? "nav-link active" : "nav-link"}
                onClick={() => setOpen(false)}
              >
                <item.icon size={15} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="header-actions">
          <ApiStatus />
          <ThemeToggle />
          <button
            type="button"
            className="icon-button menu-button"
            aria-label={open ? "메뉴 닫기" : "메뉴 열기"}
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X size={19} /> : <Menu size={19} />}
          </button>
        </div>
      </div>
    </header>
  );
}
