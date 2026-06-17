import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, Plus, RefreshCw } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Contact, SyncResult, Tag } from "@/lib/types";
import { Badge, Button, Card } from "@/components/ui";
import { visibilityStyles } from "@/lib/contacts";

export function ContactsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  const { data: contacts, isLoading, error } = useQuery({
    queryKey: ["contacts"],
    queryFn: () => api.get<Contact[]>("/api/contacts"),
  });

  const [busy, setBusy] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [activeTag, setActiveTag] = useState<string | null>(null);

  async function syncNow() {
    setSyncMsg(null);
    setBusy(true);
    try {
      const r = await api.post<SyncResult>("/api/contacts/sync");
      setSyncMsg(
        r.skipped_reason
          ? `Sync skipped: ${r.skipped_reason}`
          : `Synced — +${r.created} new, ~${r.updated} updated, -${r.deleted} removed, ` +
            `${r.pushed} pushed${r.conflicts ? `, ${r.conflicts} conflicts` : ""}`,
      );
      await qc.invalidateQueries({ queryKey: ["contacts"] });
    } catch (err) {
      setSyncMsg(err instanceof ApiError ? `Sync failed: ${err.message}` : "Sync failed");
    } finally {
      setBusy(false);
    }
  }

  const tagMap = new Map<string, Tag>();
  for (const c of contacts ?? []) for (const t of c.tags ?? []) tagMap.set(t.name, t);
  const allTags = [...tagMap.values()].sort((a, b) => a.name.localeCompare(b.name));
  const filtered = activeTag
    ? (contacts ?? []).filter((c) => c.tags?.some((t) => t.name === activeTag))
    : contacts;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Contacts</h1>
        <span className="text-sm text-muted-foreground">{contacts?.length ?? 0} people</span>
        <div className="ml-auto flex gap-2">
          <Button variant="secondary" onClick={() => void syncNow()} disabled={busy}>
            <RefreshCw size={16} className={busy ? "animate-spin" : ""} /> Sync now
          </Button>
          <Button onClick={() => navigate("/contacts/new")}>
            <Plus size={16} /> New contact
          </Button>
        </div>
      </div>

      {syncMsg && (
        <Card className="bg-muted/40 px-4 py-2.5 text-sm text-muted-foreground">{syncMsg}</Card>
      )}

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {error && (
        <p className="text-sm text-destructive">
          {error instanceof ApiError ? error.message : "Failed to load contacts"}
        </p>
      )}

      {contacts && contacts.length === 0 && !isLoading && (
        <Card className="p-8 text-center text-muted-foreground">
          No contacts yet. Add one, or hit <strong>Sync now</strong> to pull them from Nextcloud.
        </Card>
      )}

      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {allTags.map((t) => (
            <button
              key={t.name}
              onClick={() => setActiveTag(activeTag === t.name ? null : t.name)}
              className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition ${
                activeTag === t.name ? "border-primary bg-accent" : "hover:bg-accent"
              }`}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: t.color ?? "hsl(var(--muted-foreground))" }}
              />
              {t.name}
            </button>
          ))}
          {activeTag && (
            <button
              onClick={() => setActiveTag(null)}
              className="rounded-full px-3 py-1 text-sm text-muted-foreground hover:text-foreground"
            >
              Clear ×
            </button>
          )}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {filtered?.map((c) => (
          <Link key={c.id} to={`/contacts/${c.id}`}>
            <Card className="h-full p-4 transition hover:border-primary/60">
              <div className="flex items-start justify-between gap-2">
                <div className="font-medium">{c.display_name || "Unnamed"}</div>
                <Badge className={visibilityStyles[c.visibility]}>{c.visibility}</Badge>
              </div>
              {c.organization && (
                <div className="mt-0.5 text-sm text-muted-foreground">{c.organization}</div>
              )}
              {c.emails[0] && (
                <div className="mt-2 flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Mail size={14} /> {c.emails[0].value}
                </div>
              )}
              {c.tags && c.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {c.tags.map((t) => (
                    <span
                      key={t.id}
                      className="flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs"
                    >
                      <span
                        className="h-1.5 w-1.5 rounded-full"
                        style={{ background: t.color ?? "hsl(var(--muted-foreground))" }}
                      />
                      {t.name}
                    </span>
                  ))}
                </div>
              )}
              {c.dirty && (
                <div className="mt-2 text-xs text-amber-500">• pending sync to Nextcloud</div>
              )}
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
