import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CalendarDays, NotebookPen, Smile, Users } from "lucide-react";
import { api } from "@/lib/api";
import type { Summary } from "@/lib/types";
import { useAuth } from "@/auth/AuthContext";
import { Card } from "@/components/ui";

function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return <span className="text-sm text-muted-foreground">Not enough data yet</span>;
  const w = 220;
  const h = 44;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const step = w / (points.length - 1);
  const d = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${(h - ((p - min) / range) * h).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={w} height={h} className="overflow-visible">
      <path d={d} fill="none" stroke="hsl(var(--primary))" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Stat({ to, icon, value, label }: { to: string; icon: React.ReactNode; value: number; label: string }) {
  return (
    <Link to={to}>
      <Card className="flex items-center gap-3 p-4 transition hover:border-primary/60">
        <div className="rounded-md bg-primary/15 p-2 text-primary">{icon}</div>
        <div>
          <div className="text-2xl font-semibold">{value}</div>
          <div className="text-sm text-muted-foreground">{label}</div>
        </div>
      </Card>
    </Link>
  );
}

export function SummaryPage() {
  const { me } = useAuth();
  const { data, isLoading } = useQuery({ queryKey: ["summary"], queryFn: () => api.get<Summary>("/api/summary") });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">
          Hello, {me?.user.display_name?.split(" ")[0] ?? "there"} 👋
        </h1>
        <p className="text-sm text-muted-foreground">Here’s a look at your relationships.</p>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat to="/contacts" icon={<Users size={20} />} value={data.contacts_count} label="Contacts" />
            <Stat to="/events" icon={<CalendarDays size={20} />} value={data.events_upcoming} label="Upcoming events" />
            <Stat to="/journal" icon={<NotebookPen size={20} />} value={data.journal_templates} label="Journals" />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card className="p-5">
              <div className="mb-2 flex items-center gap-2 font-medium">
                <Smile size={18} className="text-primary" /> Mood trend
              </div>
              <Sparkline points={data.mood_trend.map((m) => m.mood)} />
            </Card>

            <Card className="p-5">
              <div className="mb-3 font-medium">Upcoming</div>
              {data.upcoming_events.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nothing scheduled.</p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {data.upcoming_events.map((ev) => (
                    <li key={ev.id} className="flex items-center justify-between gap-2">
                      <span>{ev.title}</span>
                      <span className="text-muted-foreground">
                        {new Date(ev.starts_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
