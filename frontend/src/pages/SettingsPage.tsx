import { type FormEvent, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Contact, JournalTemplate, RelationshipType, Tag, UserOut } from "@/lib/types";
import { useAuth } from "@/auth/AuthContext";
import { DATE_FORMATS } from "@/lib/dates";
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
  const [phoneIncCC, setPhoneIncCC] = useState(false);
  const [dateFmt, setDateFmt] = useState("dd.mm.yyyy");
  const [phoneType, setPhoneType] = useState("mobile");
  const [emailType, setEmailType] = useState("home");
  const [addressType, setAddressType] = useState("home");
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
    setPhoneIncCC(me.phone_include_country_code);
    setDateFmt(me.date_format);
    setPhoneType(me.default_phone_type);
    setEmailType(me.default_email_type);
    setAddressType(me.default_address_type);
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
      phone_include_country_code: phoneIncCC,
      date_format: dateFmt,
      default_phone_type: phoneType,
      default_email_type: emailType,
      default_address_type: addressType,
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
          <div>
            <Label htmlFor="p-date">Date format</Label>
            <Select id="p-date" value={dateFmt} onChange={(e) => setDateFmt(e.target.value)}>
              {DATE_FORMATS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="p-ptype">Default phone label</Label>
            <Input id="p-ptype" value={phoneType} onChange={(e) => setPhoneType(e.target.value)} placeholder="mobile" />
          </div>
          <div>
            <Label htmlFor="p-etype">Default email label</Label>
            <Input id="p-etype" value={emailType} onChange={(e) => setEmailType(e.target.value)} placeholder="home" />
          </div>
          <div>
            <Label htmlFor="p-atype">Default address label</Label>
            <Input id="p-atype" value={addressType} onChange={(e) => setAddressType(e.target.value)} placeholder="home" />
          </div>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          The label prefilled when you add a new phone, email, or address to a contact (e.g.{" "}
          <code>mobile</code>, <code>home</code>, <code>work</code>).
        </p>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={phoneIncCC}
            onChange={(e) => setPhoneIncCC(e.target.checked)}
            className="h-4 w-4 accent-[hsl(var(--primary))]"
          />
          Include country code in saved numbers
        </label>
        <p className="mt-1 text-xs text-muted-foreground">
          Wrap the trunk digit in parentheses (e.g. <code>(x)xx xxx xx xx</code>) so it’s dropped
          when the country code is shown. Example:{" "}
          <span className="text-foreground">
            {phoneIncCC ? `${phoneCC} 79 123 12 12` : "079 123 12 12"}
          </span>
          .
        </p>
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

      <RelationshipTypeManager />
      <TypeCatalog
        title="Life-event types"
        description="The milestone presets offered on a contact's timeline."
        endpoint="/api/life-event-types"
        queryKey="life-event-types"
        kind="emoji"
      />
      <TypeCatalog
        title="Event types"
        description="The categories offered when creating an event."
        endpoint="/api/event-types"
        queryKey="event-types"
        kind="emoji"
      />
      <TagManager />
    </div>
  );
}

type RelField =
  | "name"
  | "reverse_name"
  | "name_male"
  | "name_female"
  | "reverse_name_male"
  | "reverse_name_female";

function RelationshipTypeManager() {
  const qc = useQueryClient();
  const { data: types } = useQuery({
    queryKey: ["relationship-types"],
    queryFn: () => api.get<RelationshipType[]>("/api/relationship-types"),
  });
  const [name, setName] = useState("");
  const [reverse, setReverse] = useState("");

  const refresh = () => qc.invalidateQueries({ queryKey: ["relationship-types"] });
  async function add(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await api.post("/api/relationship-types", {
      name: name.trim(),
      reverse_name: reverse.trim() || null,
    });
    setName("");
    setReverse("");
    await refresh();
  }
  async function patch(id: number, field: RelField, value: string) {
    await api.patch(`/api/relationship-types/${id}`, { [field]: value });
    await refresh();
  }
  async function remove(id: number) {
    await api.del(`/api/relationship-types/${id}`);
    await refresh();
  }

  return (
    <Card className="p-5">
      <div className="mb-1 font-medium">Relationship types</div>
      <p className="mb-3 text-sm text-muted-foreground">
        The kinds offered when linking contacts. The male/female versions are shown automatically
        based on the related contact’s gender (e.g. a “Parent” who is female reads “Mother”).
      </p>
      <div className="space-y-3">
        {(types ?? []).map((t) => (
          <RelTypeRow key={t.id} t={t} onPatch={patch} onRemove={remove} />
        ))}
      </div>
      <form onSubmit={add} className="mt-3 flex flex-wrap gap-2">
        <Input className="max-w-[12rem]" placeholder="Name (e.g. Mentor)" value={name} onChange={(e) => setName(e.target.value)} />
        <Input className="max-w-[12rem]" placeholder="Reverse (e.g. Mentee)" value={reverse} onChange={(e) => setReverse(e.target.value)} />
        <Button type="submit" variant="secondary">
          Add
        </Button>
      </form>
    </Card>
  );
}

function RelTypeRow({
  t,
  onPatch,
  onRemove,
}: {
  t: RelationshipType;
  onPatch: (id: number, field: RelField, value: string) => void;
  onRemove: (id: number) => void;
}) {
  const field = (f: RelField, placeholder: string, className: string) => (
    <Input
      className={className}
      placeholder={placeholder}
      defaultValue={(t[f] as string | null) ?? ""}
      onBlur={(e) => {
        const v = e.target.value;
        if (f === "name" && !v.trim()) return; // name is required
        if (v !== ((t[f] as string | null) ?? "")) onPatch(t.id, f, v);
      }}
    />
  );
  const m = <span className="text-xs text-muted-foreground">♂</span>;
  const f = <span className="text-xs text-muted-foreground">♀</span>;
  return (
    <div className="rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2">
        {field("name", "Name", "w-36")}
        {m}
        {field("name_male", "male", "w-28")}
        {f}
        {field("name_female", "female", "w-28")}
        <button
          onClick={() => void onRemove(t.id)}
          title="Delete"
          className="ml-auto rounded-md p-1.5 text-muted-foreground transition hover:text-destructive"
        >
          <Trash2 size={16} />
        </button>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="w-4 text-center text-muted-foreground">↔</span>
        {field("reverse_name", "Reverse (optional)", "w-36")}
        {m}
        {field("reverse_name_male", "male", "w-28")}
        {f}
        {field("reverse_name_female", "female", "w-28")}
      </div>
    </div>
  );
}

function TagManager() {
  const qc = useQueryClient();
  const { data: tags } = useQuery({ queryKey: ["tags"], queryFn: () => api.get<Tag[]>("/api/tags") });
  const [name, setName] = useState("");

  async function refresh() {
    await qc.invalidateQueries({ queryKey: ["tags"] });
    await qc.invalidateQueries({ queryKey: ["contacts"] });
  }
  async function add(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await api.post("/api/tags", { name: name.trim() });
    setName("");
    await refresh();
  }
  async function rename(t: Tag, value: string) {
    if (value.trim() && value !== t.name) {
      await api.patch(`/api/tags/${t.id}`, { name: value.trim() });
      await refresh();
    }
  }
  async function recolor(t: Tag, color: string) {
    await api.patch(`/api/tags/${t.id}`, { color });
    await refresh();
  }
  async function remove(t: Tag) {
    if (!confirm(`Delete the tag "${t.name}"? It will be removed from all contacts.`)) return;
    await api.del(`/api/tags/${t.id}`);
    await refresh();
  }

  return (
    <Card className="p-5">
      <div className="mb-1 font-medium">Tags</div>
      <p className="mb-3 text-sm text-muted-foreground">
        Organize contacts with tags. Recolor, rename, or delete them here.
      </p>
      <ul className="mb-3 divide-y divide-border/50">
        {(tags ?? []).map((t) => (
          <li key={t.id} className="flex items-center gap-3 py-2">
            <input
              type="color"
              value={t.color ?? "#94a3b8"}
              onChange={(e) => void recolor(t, e.target.value)}
              className="h-6 w-6 cursor-pointer rounded border-0 bg-transparent p-0"
              title="Tag color"
            />
            <Input
              defaultValue={t.name}
              onBlur={(e) => void rename(t, e.target.value)}
              className="max-w-xs"
            />
            <span className="text-xs text-muted-foreground">
              {t.count ?? 0} contact{(t.count ?? 0) === 1 ? "" : "s"}
            </span>
            <button
              onClick={() => void remove(t)}
              title="Delete"
              className="ml-auto rounded-md p-1.5 text-muted-foreground transition hover:text-destructive"
            >
              <Trash2 size={16} />
            </button>
          </li>
        ))}
        {tags && tags.length === 0 && <li className="py-2 text-sm text-muted-foreground">No tags yet.</li>}
      </ul>
      <form onSubmit={add} className="flex flex-wrap gap-2">
        <Input
          className="max-w-xs"
          placeholder="New tag"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button type="submit" variant="secondary">
          Add
        </Button>
      </form>
    </Card>
  );
}

interface CatalogItem {
  id: number;
  name: string;
  emoji?: string | null;
  reverse_name?: string | null;
}

function TypeCatalog({
  title,
  description,
  endpoint,
  queryKey,
  kind,
}: {
  title: string;
  description: string;
  endpoint: string;
  queryKey: string;
  kind: "emoji" | "relation";
}) {
  const qc = useQueryClient();
  const { data: items } = useQuery({ queryKey: [queryKey], queryFn: () => api.get<CatalogItem[]>(endpoint) });
  const [name, setName] = useState("");
  const [extra, setExtra] = useState("");

  async function add(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const body =
      kind === "emoji" ? { name, emoji: extra || null } : { name, reverse_name: extra || null };
    await api.post(endpoint, body);
    setName("");
    setExtra("");
    await qc.invalidateQueries({ queryKey: [queryKey] });
  }
  async function remove(itemId: number) {
    await api.del(`${endpoint}/${itemId}`);
    await qc.invalidateQueries({ queryKey: [queryKey] });
  }

  return (
    <Card className="p-5">
      <div className="mb-1 font-medium">{title}</div>
      <p className="mb-3 text-sm text-muted-foreground">{description}</p>
      <div className="mb-3 flex flex-wrap gap-2">
        {(items ?? []).map((it) => (
          <span key={it.id} className="flex items-center gap-1 rounded-full border px-3 py-1 text-sm">
            {kind === "emoji" && it.emoji ? `${it.emoji} ` : ""}
            {it.name}
            {kind === "relation" && it.reverse_name ? (
              <span className="text-muted-foreground"> ↔ {it.reverse_name}</span>
            ) : null}
            <button onClick={() => void remove(it.id)} className="text-muted-foreground hover:text-destructive">
              <Trash2 size={13} />
            </button>
          </span>
        ))}
        {items && items.length === 0 && <span className="text-sm text-muted-foreground">None yet.</span>}
      </div>
      <form onSubmit={add} className="flex flex-wrap gap-2">
        {kind === "emoji" && (
          <Input className="w-16" placeholder="🎂" value={extra} onChange={(e) => setExtra(e.target.value)} />
        )}
        <Input
          className="max-w-xs"
          placeholder={kind === "relation" ? "Name (e.g. Mentor)" : "Name"}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        {kind === "relation" && (
          <Input
            className="max-w-xs"
            placeholder="Reverse (e.g. Mentee)"
            value={extra}
            onChange={(e) => setExtra(e.target.value)}
          />
        )}
        <Button type="submit" variant="secondary">
          Add
        </Button>
      </form>
    </Card>
  );
}
