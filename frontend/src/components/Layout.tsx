import { type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { CalendarDays, LogOut, NotebookPen, Users } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  disabled?: boolean;
}

const nav: NavItem[] = [
  { to: "/contacts", label: "Contacts", icon: <Users size={18} /> },
  { to: "/events", label: "Events", icon: <CalendarDays size={18} /> },
  { to: "/journal", label: "Journal", icon: <NotebookPen size={18} />, disabled: true },
];

export function Layout({ children }: { children: ReactNode }) {
  const { me, logout } = useAuth();

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-10 border-b bg-card/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3">
          <div className="flex items-center gap-2 font-semibold">
            <img src="/icon.svg" alt="" className="h-6 w-6" />
            <span>Prism</span>
          </div>
          <nav className="flex items-center gap-1">
            {nav.map((item) =>
              item.disabled ? (
                <span
                  key={item.to}
                  title="Coming soon"
                  className="flex cursor-not-allowed items-center gap-2 rounded-md px-3 py-1.5 text-sm text-muted-foreground/50"
                >
                  {item.icon}
                  <span className="hidden sm:inline">{item.label}</span>
                </span>
              ) : (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition",
                      isActive ? "bg-accent text-accent-foreground" : "hover:bg-accent",
                    )
                  }
                >
                  {item.icon}
                  <span className="hidden sm:inline">{item.label}</span>
                </NavLink>
              ),
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="hidden text-muted-foreground md:inline">{me?.user.email}</span>
            <button
              onClick={() => void logout()}
              className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-muted-foreground transition hover:bg-accent hover:text-foreground"
              title="Log out"
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">{children}</main>
    </div>
  );
}
