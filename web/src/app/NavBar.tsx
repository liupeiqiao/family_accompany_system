"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "首页", group: "all" },
  { href: "/elder", label: "老人陪伴", group: "elder" },
  { href: "/family", label: "家庭空间", group: "family" },
  { href: "/records", label: "档案记忆", group: "family" },
  { href: "/voices", label: "音色", group: "family" },
  { href: "/history", label: "历史", group: "family" },
];

const hiddenOn = new Set(["/", "/login", "/voices"]);

export default function NavBar() {
  const pathname = usePathname();
  if (hiddenOn.has(pathname) || pathname === "/family") return null;

  return (
    <nav className="globalNav">
      <div className="navInner">
        {navItems.map((item, index) => {
          const active = pathname === item.href
            || (item.href !== "/" && pathname.startsWith(item.href));
          const showSeparator = index > 0 && item.group === "family" && navItems[index - 1].group === "elder";
          return (
            <span key={item.href} style={{ display: "contents" }}>
              {showSeparator ? <span className="navSeparator" aria-hidden="true" /> : null}
              <Link
                className={active ? "navLink navLinkActive" : "navLink"}
                href={item.href}
              >
                {item.label}
              </Link>
            </span>
          );
        })}
      </div>
    </nav>
  );
}
