import "./globals.css";

export const metadata = {
  title: "亲情陪伴系统",
  description: "家庭记忆驱动的老年陪伴应用",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
