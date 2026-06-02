import type { ReactNode } from "react";
import NavSidebar from "@/components/NavSidebar";

interface ShellLayoutProps {
  children: ReactNode;
}

export default function ShellLayout({ children }: ShellLayoutProps): React.ReactElement {
  return (
    <div className="flex h-screen bg-background dark:bg-[#070B14] overflow-hidden">
      <NavSidebar />
      <div className="flex-1 min-w-0 overflow-y-auto">
        {children}
      </div>
    </div>
  );
}
