import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Cake, MapPin, Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type {
  AddressItem,
  Contact,
  LifeEvent,
  LifeEventType,
  RelatedContact,
  RelationshipType,
  Tag,
  TypedValue,
  UserOut,
  Visibility,
} from "@/lib/types";
import { Button, Card, Input, Label, Select, Textarea } from "@/components/ui";
import { useDateFormat } from "@/lib/dates";
import { useAuth } from "@/auth/AuthContext";

function ageFrom(bday?: string | null): number | null {
  if (!bday) return null;
  const d = new Date(bday);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age--;
  return age >= 0 && age < 150 ? age : null;
}

export function ContactDetailPage() {
  const params = useParams<{ id: string }>();
  const isNew = params.id === "new"; // /contacts/new renders this form in create mode
  const id = Number(params.id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { me } = useAuth();
  const phoneCc = me?.phone_country_code ?? "+41";
  const phonePlaceholder = `${phoneCc} ${me?.phone_number_format ?? "xxx xxx xx xx"}`;

  const { data, isLoading, error } = useQuery({
    queryKey: ["contact", id],
    queryFn: () => api.get<Contact>(`/api/contacts/${id}`),
    enabled: !isNew,
  });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: () => api.get<UserOut[]>("/api/users") });

  const [form, setForm] = useState<Partial<Contact>>({});
  const [emails, setEmails] = useState<TypedValue[]>([]);
  const [phones, setPhones] = useState<TypedValue[]>([]);
  const [addresses, setAddresses] = useState<AddressItem[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setForm(data);
      setEmails(data.emails ?? []);
      setPhones(data.phones ?? []);
      setAddresses(data.addresses ?? []);
      setTags((data.tags ?? []).map((t) => t.name));
    } else if (isNew) {
      setForm({ visibility: "public" });
    }
  }, [data, isNew]);

  function set<K extends keyof Contact>(key: K, value: Contact[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setMsg(null);
    setBusy(true);
    const payload = {
      display_name: form.display_name,
      first_name: form.first_name,
      middle_name: form.middle_name,
      last_name: form.last_name,
      organization: form.organization,
      job_title: form.job_title,
      birthday: form.birthday || null,
      notes: form.notes,
      gender: form.gender ?? null,
      telegram: form.telegram?.trim() ? form.telegram.trim().replace(/^@/, "") : null,
      visibility: form.visibility,
      linked_user_id: form.linked_user_id ?? null,
      emails: emails.filter((x) => x.value),
      phones: phones.filter((x) => x.value),
      addresses: addresses.filter((a) => a.street || a.city || a.country),
      tags,
    };
    try {
      if (isNew) {
        const created = await api.post<Contact>("/api/contacts", payload);
        await qc.invalidateQueries({ queryKey: ["contacts"] });
        await qc.invalidateQueries({ queryKey: ["tags"] });
        navigate(`/contacts/${created.id}`, { replace: true });
        return;
      }
      await api.patch<Contact>(`/api/contacts/${id}`, payload);
      await qc.invalidateQueries({ queryKey: ["contact", id] });
      await qc.invalidateQueries({ queryKey: ["contacts"] });
      await qc.invalidateQueries({ queryKey: ["tags"] });
      setMsg("Saved — syncing to Nextcloud.");
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Delete this contact? This removes it from Nextcloud too.")) return;
    setErr(null);
    setBusy(true);
    try {
      await api.del(`/api/contacts/${id}`);
      await qc.invalidateQueries({ queryKey: ["contacts"] });
      navigate("/contacts");
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not delete");
      setBusy(false);
    }
  }

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (!isNew && (error || !data))
    return (
      <div className="space-y-4">
        <BackLink />
        <p className="text-sm text-destructive">
          {error instanceof ApiError ? error.message : "Contact not found"}
        </p>
      </div>
    );

  const age = ageFrom(form.birthday);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <BackLink />
        {isNew ? (
          <span className="font-medium">New contact</span>
        ) : data ? (
          <>
            {data.dirty ? (
              <span className="text-xs text-amber-500">• pending sync</span>
            ) : data.last_synced_at ? (
              <span className="text-xs text-muted-foreground">
                synced {new Date(data.last_synced_at).toLocaleString()}
              </span>
            ) : null}
            <Button
              variant="ghost"
              className="ml-auto text-destructive"
              onClick={() => void remove()}
              disabled={busy}
            >
              <Trash2 size={16} /> Delete
            </Button>
          </>
        ) : null}
      </div>

      <Card className="p-5">
        <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor="d-name">Display name</Label>
            <Input id="d-name" value={form.display_name ?? ""} onChange={(e) => set("display_name", e.target.value)} />
          </div>
          <Field label="First name" value={form.first_name} onChange={(v) => set("first_name", v)} />
          <Field label="Middle name" value={form.middle_name} onChange={(v) => set("middle_name", v)} />
          <Field label="Last name" value={form.last_name} onChange={(v) => set("last_name", v)} />
          <Field label="Organization" value={form.organization} onChange={(v) => set("organization", v)} />
          <Field label="Job title" value={form.job_title} onChange={(v) => set("job_title", v)} />
          <div>
            <Label htmlFor="d-tg">Telegram</Label>
            <Input
              id="d-tg"
              value={form.telegram ?? ""}
              onChange={(e) => set("telegram", e.target.value)}
              placeholder="username"
            />
            {form.telegram?.trim() && (
              <a
                href={`https://t.me/${form.telegram.trim().replace(/^@/, "")}`}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-block text-xs text-primary hover:underline"
              >
                t.me/{form.telegram.trim().replace(/^@/, "")} ↗
              </a>
            )}
          </div>
          <div>
            <Label htmlFor="d-gender">Gender</Label>
            <Select
              id="d-gender"
              value={form.gender ?? ""}
              onChange={(e) => set("gender", (e.target.value || null) as Contact["gender"])}
            >
              <option value="">— unspecified —</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="d-bday">Birthday</Label>
            <div className="flex items-center gap-2">
              <Input
                id="d-bday"
                type="date"
                value={form.birthday ?? ""}
                onChange={(e) => set("birthday", e.target.value)}
              />
              {age != null && (
                <span className="flex items-center gap-1 whitespace-nowrap text-sm text-muted-foreground">
                  <Cake size={14} /> {age}
                </span>
              )}
            </div>
          </div>
          <div>
            <Label htmlFor="d-vis">Visibility</Label>
            <Select
              id="d-vis"
              value={form.visibility ?? "public"}
              onChange={(e) => set("visibility", e.target.value as Visibility)}
            >
              <option value="private">Private</option>
              <option value="public">Public</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="d-link">Linked user</Label>
            <Select
              id="d-link"
              value={form.linked_user_id ? String(form.linked_user_id) : ""}
              onChange={(e) => set("linked_user_id", e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">— none —</option>
              {(users ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.display_name}
                </option>
              ))}
            </Select>
            <p className="mt-1 text-xs text-muted-foreground">
              Linking this contact to a user lets them see events they’re invited to.
            </p>
          </div>

          <div className="sm:col-span-2">
            <ValueListEditor
              label="Emails"
              placeholder="name@example.com"
              newType={me?.default_email_type ?? "home"}
              items={emails}
              onChange={setEmails}
            />
          </div>
          <div className="sm:col-span-2">
            <ValueListEditor
              label="Phones"
              placeholder={phonePlaceholder}
              newValue={`${phoneCc} `}
              newType={me?.default_phone_type ?? "mobile"}
              items={phones}
              onChange={setPhones}
            />
          </div>
          <div className="sm:col-span-2">
            <AddressListEditor
              newType={me?.default_address_type ?? "home"}
              items={addresses}
              onChange={setAddresses}
            />
          </div>
          <div className="sm:col-span-2">
            <TagEditor tags={tags} onChange={setTags} />
          </div>

          <div className="sm:col-span-2">
            <Label htmlFor="d-notes">Notes</Label>
            <Textarea id="d-notes" rows={3} value={form.notes ?? ""} onChange={(e) => set("notes", e.target.value)} />
          </div>
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button type="submit" disabled={busy}>
              {busy ? "Saving…" : isNew ? "Create contact" : "Save changes"}
            </Button>
            {msg && <span className="text-sm text-emerald-500">{msg}</span>}
            {err && <span className="text-sm text-destructive">{err}</span>}
          </div>
        </form>
      </Card>

      {data?.latitude != null && data?.longitude != null && (
        <Card className="overflow-hidden">
          <div className="flex items-center gap-2 p-3 text-sm text-muted-foreground">
            <MapPin size={15} /> {addresses[0]?.city || addresses[0]?.street || "Address location"}
          </div>
          <iframe
            title="Address map"
            className="h-64 w-full border-0"
            loading="lazy"
            src={mapSrc(data.latitude, data.longitude)}
          />
        </Card>
      )}

      {!isNew && (
        <>
          <RelationshipsSection contactId={id} />
          <LifeEventsSection contactId={id} />
        </>
      )}
    </div>
  );
}

function BackLink() {
  return (
    <Link
      to="/contacts"
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft size={16} /> Back
    </Link>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value?: string | null;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <Input value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function mapSrc(lat: number, lon: number): string {
  const d = 0.01;
  const bbox = `${lon - d},${lat - d},${lon + d},${lat + d}`;
  return `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(
    bbox,
  )}&layer=mapnik&marker=${lat},${lon}`;
}

function ValueListEditor({
  label,
  placeholder,
  items,
  onChange,
  newValue = "",
  newType = "home",
}: {
  label: string;
  placeholder: string;
  items: TypedValue[];
  onChange: (v: TypedValue[]) => void;
  newValue?: string;
  newType?: string;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="space-y-2">
        {items.map((item, i) => (
          <div key={i} className="flex gap-2">
            <Input
              className="w-28"
              placeholder="type"
              value={item.type}
              onChange={(e) => onChange(items.map((x, j) => (j === i ? { ...x, type: e.target.value } : x)))}
            />
            <Input
              className="flex-1"
              placeholder={placeholder}
              value={item.value}
              onChange={(e) => onChange(items.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))}
            />
            <button
              type="button"
              onClick={() => onChange(items.filter((_, j) => j !== i))}
              className="text-muted-foreground hover:text-destructive"
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
      </div>
      <Button
        type="button"
        variant="ghost"
        className="mt-1"
        onClick={() => onChange([...items, { type: newType, value: newValue }])}
      >
        <Plus size={14} /> Add {label.toLowerCase().replace(/s$/, "")}
      </Button>
    </div>
  );
}

function AddressListEditor({
  items,
  onChange,
  newType = "home",
}: {
  items: AddressItem[];
  onChange: (v: AddressItem[]) => void;
  newType?: string;
}) {
  const upd = (i: number, patch: Partial<AddressItem>) =>
    onChange(items.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  return (
    <div>
      <Label>Addresses</Label>
      <div className="space-y-3">
        {items.map((a, i) => (
          <div key={i} className="rounded-md border p-3">
            <div className="grid gap-2 sm:grid-cols-2">
              <Input placeholder="Street" value={a.street} onChange={(e) => upd(i, { street: e.target.value })} />
              <Input placeholder="City" value={a.city} onChange={(e) => upd(i, { city: e.target.value })} />
              <Input placeholder="Region" value={a.region} onChange={(e) => upd(i, { region: e.target.value })} />
              <Input placeholder="Postcode" value={a.code} onChange={(e) => upd(i, { code: e.target.value })} />
              <Input placeholder="Country" value={a.country} onChange={(e) => upd(i, { country: e.target.value })} />
            </div>
            <button
              type="button"
              onClick={() => onChange(items.filter((_, j) => j !== i))}
              className="mt-2 flex items-center gap-1 text-sm text-muted-foreground hover:text-destructive"
            >
              <Trash2 size={14} /> Remove address
            </button>
          </div>
        ))}
      </div>
      <Button
        type="button"
        variant="ghost"
        className="mt-1"
        onClick={() =>
          onChange([...items, { type: newType, street: "", city: "", region: "", code: "", country: "" }])
        }
      >
        <Plus size={14} /> Add address (geocoded to a map)
      </Button>
    </div>
  );
}

function TagEditor({ tags, onChange }: { tags: string[]; onChange: (t: string[]) => void }) {
  const { data: catalog } = useQuery({ queryKey: ["tags"], queryFn: () => api.get<Tag[]>("/api/tags") });
  const [input, setInput] = useState("");
  const [open, setOpen] = useState(false);

  const colorOf = (name: string) =>
    catalog?.find((c) => c.name.toLowerCase() === name.toLowerCase())?.color ?? undefined;

  const q = input.trim().toLowerCase();
  const suggestions = (catalog ?? [])
    .filter((c) => !tags.some((t) => t.toLowerCase() === c.name.toLowerCase()))
    .filter((c) => !q || c.name.toLowerCase().includes(q))
    .slice(0, 8);

  function add(name: string) {
    const n = name.trim();
    if (n && !tags.some((t) => t.toLowerCase() === n.toLowerCase())) onChange([...tags, n]);
    setInput("");
  }

  return (
    <div>
      <Label>Tags</Label>
      <div className="mb-2 flex flex-wrap gap-2">
        {tags.map((t) => (
          <span key={t} className="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-sm">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: colorOf(t) ?? "hsl(var(--muted-foreground))" }}
            />
            {t}
            <button
              type="button"
              onClick={() => onChange(tags.filter((x) => x !== t))}
              className="text-muted-foreground hover:text-destructive"
              aria-label={`Remove ${t}`}
            >
              ×
            </button>
          </span>
        ))}
        {tags.length === 0 && <span className="text-sm text-muted-foreground">No tags.</span>}
      </div>
      <div className="relative max-w-xs">
        <Input
          placeholder="Add tag…"
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add(input);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
        />
        {open && suggestions.length > 0 && (
          <ul className="absolute z-20 mt-1 max-h-52 w-full overflow-auto rounded-md border bg-[hsl(var(--card))] py-1 shadow-lg">
            {suggestions.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  // mousedown (not click) fires before the input blur, so the
                  // selection registers before the dropdown closes.
                  onMouseDown={(e) => {
                    e.preventDefault();
                    add(c.name);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-accent"
                >
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: c.color ?? "hsl(var(--muted-foreground))" }}
                  />
                  {c.name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function RelationshipsSection({ contactId }: { contactId: number }) {
  const qc = useQueryClient();
  const { data: rels } = useQuery({
    queryKey: ["relationships", contactId],
    queryFn: () => api.get<RelatedContact[]>(`/api/contacts/${contactId}/relationships`),
  });
  const { data: contacts } = useQuery({ queryKey: ["contacts"], queryFn: () => api.get<Contact[]>("/api/contacts") });
  const { data: types } = useQuery({
    queryKey: ["relationship-types"],
    queryFn: () => api.get<RelationshipType[]>("/api/relationship-types"),
  });

  const [other, setOther] = useState("");
  const [typeId, setTypeId] = useState("");

  async function add() {
    if (!other || !typeId) return;
    await api.post("/api/relationships", {
      from_contact_id: contactId,
      to_contact_id: Number(other),
      type_id: Number(typeId),
    });
    setOther("");
    setTypeId("");
    await qc.invalidateQueries({ queryKey: ["relationships", contactId] });
  }
  async function remove(rid: number) {
    await api.del(`/api/relationships/${rid}`);
    await qc.invalidateQueries({ queryKey: ["relationships", contactId] });
  }

  const { me } = useAuth();
  const selfId = me?.self_contact_id ?? null;
  const others = (contacts ?? []).filter((c) => c.id !== contactId && c.id !== selfId);

  return (
    <Card className="p-5">
      <div className="mb-3 font-medium">Relationships</div>
      <div className="mb-3 flex flex-wrap gap-2">
        {(rels ?? []).map((r) => (
          <span
            key={`${r.relationship_id}:${r.contact_id}`}
            className={`flex items-center gap-1 rounded-full border px-3 py-1 text-sm ${
              r.derived ? "border-dashed text-muted-foreground" : ""
            }`}
          >
            <span className="text-muted-foreground">{r.label}:</span>
            <Link to={`/contacts/${r.contact_id}`} className="hover:underline">
              {r.contact_name}
              {r.contact_id === selfId ? " (you)" : ""}
            </Link>
            {!r.derived && (
              <button
                onClick={() => void remove(r.relationship_id)}
                className="text-muted-foreground hover:text-destructive"
                title="Remove"
              >
                <Trash2 size={13} />
              </button>
            )}
          </span>
        ))}
        {rels && rels.length === 0 && <span className="text-sm text-muted-foreground">No relationships yet.</span>}
      </div>
      <div className="flex flex-wrap gap-2">
        <Select value={typeId} onChange={(e) => setTypeId(e.target.value)} className="w-40">
          <option value="">Relationship…</option>
          {(types ?? []).map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </Select>
        <Select value={other} onChange={(e) => setOther(e.target.value)} className="w-48">
          <option value="">Who…</option>
          {selfId && selfId !== contactId && <option value={selfId}>⭐ Me</option>}
          {others.map((c) => (
            <option key={c.id} value={c.id}>
              {c.display_name}
            </option>
          ))}
        </Select>
        <Button type="button" variant="secondary" onClick={() => void add()}>
          Link
        </Button>
      </div>
    </Card>
  );
}

function LifeEventsSection({ contactId }: { contactId: number }) {
  const qc = useQueryClient();
  const { data: events } = useQuery({
    queryKey: ["life-events", contactId],
    queryFn: () => api.get<LifeEvent[]>(`/api/contacts/${contactId}/life-events`),
  });
  const { data: types } = useQuery({
    queryKey: ["life-event-types"],
    queryFn: () => api.get<LifeEventType[]>("/api/life-event-types"),
  });

  const { formatDate } = useDateFormat();
  const [title, setTitle] = useState("");
  const [emoji, setEmoji] = useState("");
  const [date, setDate] = useState("");
  const [note, setNote] = useState("");

  function pick(t: LifeEventType) {
    setTitle(t.name);
    setEmoji(t.emoji ?? "");
  }
  async function add() {
    if (!title) return;
    await api.post("/api/life-events", {
      contact_id: contactId,
      title,
      emoji: emoji || null,
      happened_on: date || null,
      note: note || null,
    });
    setTitle("");
    setEmoji("");
    setDate("");
    setNote("");
    await qc.invalidateQueries({ queryKey: ["life-events", contactId] });
  }
  async function remove(eid: number) {
    await api.del(`/api/life-events/${eid}`);
    await qc.invalidateQueries({ queryKey: ["life-events", contactId] });
  }

  return (
    <Card className="p-5">
      <div className="mb-3 font-medium">Life events</div>
      <ul className="mb-4 space-y-2">
        {(events ?? []).map((ev) => (
          <li key={ev.id} className="flex items-center gap-2 text-sm">
            <span className="text-lg">{ev.emoji || "•"}</span>
            <span className="font-medium">{ev.title}</span>
            {ev.happened_on && <span className="text-muted-foreground">{formatDate(ev.happened_on)}</span>}
            {ev.note && <span className="text-muted-foreground">— {ev.note}</span>}
            <button onClick={() => void remove(ev.id)} className="ml-auto text-muted-foreground hover:text-destructive">
              <Trash2 size={14} />
            </button>
          </li>
        ))}
        {events && events.length === 0 && <li className="text-sm text-muted-foreground">No life events yet.</li>}
      </ul>
      <div className="mb-2 flex flex-wrap gap-1.5">
        {(types ?? []).map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => pick(t)}
            className="rounded-full border px-2.5 py-1 text-sm text-muted-foreground transition hover:bg-accent"
          >
            {t.emoji} {t.name}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Input className="w-16" placeholder="🎉" value={emoji} onChange={(e) => setEmoji(e.target.value)} />
        <Input className="w-48" placeholder="What happened" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Input className="w-40" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <Input className="flex-1" placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
        <Button type="button" variant="secondary" onClick={() => void add()}>
          Add
        </Button>
      </div>
    </Card>
  );
}
