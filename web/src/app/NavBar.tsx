"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "首页" },
  { href: "/elder", label: "老人陪伴" },
  { href: "/family", label: "家庭空间" },
  { href: "/records", label: "档案记忆" },
  { href: "/voices", label: "音色" },
  { href: "/history", label: "历史" },
];

const hiddenOn = new Set(["/login"]);

export default function NavBar() {
  const pathname = usePathname();
  if (hiddenOn.has(pathname)) return null;

  return (
    <nav className="globalNav">
      <div className="navInner">
        {navItems.map((item) => {
          const active = pathname === item.href
            || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              className={active ? "navLink navLinkActive" : "navLink"}
              href={item.href}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
