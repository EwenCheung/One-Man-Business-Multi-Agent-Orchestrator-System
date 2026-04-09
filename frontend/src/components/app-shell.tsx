import { ReactNode } from "react";
import Sidebar from "./sidebar";
import Topbar from "./topbar";

export default function AppShell({ children, role = "owner" }: { children: ReactNode; role?: string }) {
  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <div className="flex min-h-screen">
        <Sidebar role={role} />
        <div className="flex min-h-screen flex-1 flex-col">
          <Topbar role={role} />
          <main className="flex-1 p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
