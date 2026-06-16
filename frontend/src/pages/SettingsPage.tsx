import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Contact, JournalTemplate, UserOut } from "@/lib/types";
import { useAuth } from "@/auth/AuthContext";
import { Button, Card, Input, Label, Select } from "@/components/ui";

export function SettingsPage() {
  const qc = useQueryClient();
  const { me, refresh } = useAuth();
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: () => api.get<UserOut[]>("/api/users") });
  const { data: partners } = useQuery({
    queryKey: ["partners"],
    queryFn: () => api.get<UserOut[]>("/api/sharing/partners"),
  });
  const { data: contacts } = useQuery({ queryKey: ["contacts"], queryFn: () => api.get<Contact[]>("/api/contacts") });
  const { data: journals } = useQuery({
    queryKey: ["journal-templates"],
    queryFn: () => api.get<JournalTemplate[]>("/api/journal/templates"),
  });

  const partnerIds = new Set((partners ?? []).map((p) => p.id));
  const others = (users ?? []).filter((u) => u.id !== me?.user.id);

  // Preferences + Nextcloud form state, seeded from /me.
  const [currency, setCurrency] = useState("CHF");
  const [phoneCC, setPhoneCC] = useState("+41");
  const [phoneFmt, setPhoneFmt] = useState("xxx xxx xx xx");
  const [ncUrl, setNcUrl] = useState("");
  const [ncUser, setNcUser] = useState("");
  const [ncPass, setNcPass] = useState("");
  const [ncBook, setNcBook] = useState("");
  const [ncCal, setNcCal] = useState("");
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    if (!me) return;
    setCurrency(me.default_currency);
    setPhoneCC(me.phone_country_code);
    setPhoneFmt(me.phone_number_format);
    setNcUrl(me.nextcloud_url ?? "");
    setNcUser(me.nextcloud_username ?? "");
    setNcBook(me.nextcloud_addressbook ?? "");
    setNcCal(me.nextcloud_calendar ?? "");
  }, [me]);

  async function togglePartner(id: number, on: boolean) {
    if (on) await api.put(`/api/sharing/partners/${id}`);
    else await api.del(`/api/sharing/partners/${id}`);
    await qc.invalidateQueries({ queryKey: ["partners"] });
  }
  async function toggleJournal(id: number, active: boolean) {
    await api.patch(`/api/journal/templates/${id}`, { active });
    await qc.invalidateQueries({ queryKey: ["journal-templates"] });
  }
  async function deleteJournal(id: number) {
    if (!confirm("Delete this journal and all its entries?")) return;
    await api.del(`/api/journal/templates/${id}`);
    await qc.invalidateQueries({ queryKey: ["journal-templates"] });
  }
  async function setSelfContact(value: string) {
    await api.put("/api/auth/self-contact", { contact_id: value ? Number(value) : null });
    await refresh();
  }
  async function savePrefs() {
    await api.put("/api/auth/preferences", {
      default_currency: currency,
      phone_country_code: phoneCC,
      phone_number_format: phoneFmt,
    });
    await refresh();
    setFlash("Preferences saved");
  }
  async function saveNextcloud() {
    try {
      const body: Record<string, unknown> = {
        nextcloud_url: ncUrl,
        nextcloud_username: ncUser,
        nextcloud_addressbook: ncBook,
        nextcloud_calendar: ncCal,
      };
      if (ncPass) body.nextcloud_app_password = ncPass; // only changes when entered
      await api.put("/api/auth/nextcloud", body);
      setNcPass("");
      await refresh();
      setFlash("Nextcloud settings saved");
    } catch (e) {
      setFlash(e instanceof ApiError ? e.message : "Could not save Nextcloud settings");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Settings</h1>
        {flash && <span className="text-sm text-emerald-500">{flash}</span>}
      </div>

      <Card className="p-5">
        <div className="mb-3 font-medium">Preferences</div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <Label htmlFor="p-cur">Default currency</Label>
            <Input id="p-cur" value={currency} onChange={(e) => setCurrency(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="p-cc">Phone country code</Label>
            <Input id="p-cc" value={phoneCC} onChange={(e) => setPhoneCC(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="p-fmt">Phone number format</Label>
            <Input id="p-fmt" value={phoneFmt} onChange={(e) => setPhoneFmt(e.target.value)} />
          </div>
        </div>
        <Button className="mt-3" onClick={() => void savePrefs()}>
          Save preferences
        </Button>
      </Card>

      <Card className="p-5">
        <div className="mb-1 flex items-center gap-2 font-medium">
          Nextcloud
          {me?.nextcloud_configured && (
            <span className="rounded-full border border-emerald-500/40 px-2 py-0.5 text-xs text-emerald-500">
              connected
            </span>
          )}
        </div>
        <p className="mb-3 text-sm text-muted-foreground">
          Your own Nextcloud. Contacts sync from here and events/reminders are pushed to it. Use an
          app password (Nextcloud → Settings → Security → Devices &amp; sessions).
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor="nc-url">Server URL</Label>
            <Input id="nc-url" value={ncUrl} onChange={(e) => setNcUrl(e.target.value)} placeholder="https://cloud.example.com" />
          </div>
          <div>
            <Label htmlFor="nc-user">Username</Label>
            <Input id="nc-user" value={ncUser} onChange={(e) => setNcUser(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="nc-pass">App password</Label>
            <Input
              id="nc-pass"
              type="password"
              value={ncPass}
              onChange={(e) => setNcPass(e.target.value)}
              placeholder={me?.nextcloud_username ? "•••••• (leave blank to keep)" : ""}
            />
          </div>
          <div>
            <Label htmlFor="nc-book">Address book</Label>
            <Input id="nc-book" value={ncBook} onChange={(e) => setNcBook(e.target.value)} placeholder="contacts" />
          </div>
          <div>
            <Label htmlFor="nc-cal">Calendar</Label>
            <Input id="nc-cal" value={ncCal} onChange={(e) => setNcCal(e.target.value)} placeholder="personal" />
          </div>
        </div>
        <Button className="mt-3" onClick={() => void saveNextcloud()}>
          Save Nextcloud settings
        </Button>
      </Card>

      <Card className="p-5">
        <div className="mb-1 font-medium">Partners</div>
        <p className="mb-3 text-sm text-muted-foreground">
          Partners can see records you mark <span className="text-amber-500">private</span>.
        </p>
        {others.length === 0 ? (
          <p className="text-sm text-muted-foreground">No other users yet.</p>
        ) : (
          <ul className="divide-y divide-border/50">
            {others.map((u) => (
              <li key={u.id} className="flex items-center justify-between gap-3 py-2">
                <div>
                  <div className="text-sm">{u.display_name}</div>
                  <div className="text-xs text-muted-foreground">{u.email}</div>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={partnerIds.has(u.id)}
                    onChange={(e) => void togglePartner(u.id, e.target.checked)}
                    className="h-4 w-4 accent-[hsl(var(--primary))]"
                  />
                  Partner
                </label>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-5">
        <div className="mb-1 font-medium">This is me</div>
        <p className="mb-3 text-sm text-muted-foreground">
          Pick the contact that represents you, so you can appear in relationships (e.g. “Partner: You”).
        </p>
        <Select
          className="max-w-sm"
          value={me?.self_contact_id ? String(me.self_contact_id) : ""}
          onChange={(e) => void setSelfContact(e.target.value)}
        >
          <option value="">Not set</option>
          {(contacts ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.display_name}
            </option>
          ))}
        </Select>
      </Card>

      <Card className="p-5">
        <div className="mb-1 font-medium">Journals</div>
        <p className="mb-3 text-sm text-muted-foreground">
          Hide a journal to remove it from the Journal page without losing its entries, or delete
          it. Edit journals from the Journal page.
        </p>
        {(journals ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">No journals yet.</p>
        ) : (
          <ul className="divide-y divide-border/50">
            {(journals ?? []).map((j) => (
              <li key={j.id} className="flex items-center justify-between gap-3 py-2">
                <span className={j.active ? "" : "text-muted-foreground line-through"}>
                  {j.name} <span className="text-xs text-muted-foreground">({j.cadence})</span>
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => void toggleJournal(j.id, !j.active)}
                    title={j.active ? "Hide" : "Show"}
                    className="rounded-md p-1.5 text-muted-foreground transition hover:bg-accent hover:text-foreground"
                  >
                    {j.active ? <Eye size={16} /> : <EyeOff size={16} />}
                  </button>
                  <button
                    onClick={() => void deleteJournal(j.id)}
                    title="Delete"
                    className="rounded-md p-1.5 text-muted-foreground transition hover:text-destructive"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
