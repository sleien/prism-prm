import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Contact, Visibility } from "@/lib/types";
import { Badge, Button, Card, Input, Label, Select, Textarea } from "@/components/ui";
import { visibilityStyles } from "@/lib/contacts";

export function ContactDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["contact", id],
    queryFn: () => api.get<Contact>(`/api/contacts/${id}`),
  });

  const [form, setForm] = useState<Partial<Contact>>({});
  const [primaryEmail, setPrimaryEmail] = useState("");
  const [primaryPhone, setPrimaryPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setForm(data);
      setPrimaryEmail(data.emails[0]?.value ?? "");
      setPrimaryPhone(data.phones[0]?.value ?? "");
    }
  }, [data]);

  function set<K extends keyof Contact>(key: K, value: Contact[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setMsg(null);
    setBusy(true);
    try {
      await api.patch<Contact>(`/api/contacts/${id}`, {
        display_name: form.display_name,
        first_name: form.first_name,
        last_name: form.last_name,
        organization: form.organization,
        job_title: form.job_title,
        notes: form.notes,
        visibility: form.visibility,
        emails: primaryEmail ? [{ type: "home", value: primaryEmail }] : [],
        phones: primaryPhone ? [{ type: "cell", value: primaryPhone }] : [],
      });
      await qc.invalidateQueries({ queryKey: ["contact", id] });
      await qc.invalidateQueries({ queryKey: ["contacts"] });
      setMsg("Saved — will sync to Nextcloud.");
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
  if (error || !data)
    return (
      <div className="space-y-4">
        <Link to="/contacts" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft size={16} /> Back
        </Link>
        <p className="text-sm text-destructive">
          {error instanceof ApiError ? error.message : "Contact not found"}
        </p>
      </div>
    );

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Link to="/contacts" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft size={16} /> Back
        </Link>
        <Badge className={visibilityStyles[data.visibility]}>{data.visibility}</Badge>
        {data.dirty ? (
          <span className="text-xs text-amber-500">• pending sync</span>
        ) : data.last_synced_at ? (
          <span className="text-xs text-muted-foreground">
            synced {new Date(data.last_synced_at).toLocaleString()}
          </span>
        ) : null}
        <Button variant="ghost" className="ml-auto text-destructive" onClick={() => void remove()} disabled={busy}>
          <Trash2 size={16} /> Delete
        </Button>
      </div>

      <Card className="p-5">
        <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor="d-name">Display name</Label>
            <Input id="d-name" value={form.display_name ?? ""} onChange={(e) => set("display_name", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="d-first">First name</Label>
            <Input id="d-first" value={form.first_name ?? ""} onChange={(e) => set("first_name", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="d-last">Last name</Label>
            <Input id="d-last" value={form.last_name ?? ""} onChange={(e) => set("last_name", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="d-org">Organization</Label>
            <Input id="d-org" value={form.organization ?? ""} onChange={(e) => set("organization", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="d-title">Job title</Label>
            <Input id="d-title" value={form.job_title ?? ""} onChange={(e) => set("job_title", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="d-email">Email</Label>
            <Input id="d-email" type="email" value={primaryEmail} onChange={(e) => setPrimaryEmail(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="d-phone">Phone</Label>
            <Input id="d-phone" value={primaryPhone} onChange={(e) => setPrimaryPhone(e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="d-vis">Visibility</Label>
            <Select
              id="d-vis"
              value={form.visibility ?? "public"}
              onChange={(e) => set("visibility", e.target.value as Visibility)}
            >
              <option value="public">Public — all users</option>
              <option value="group">Group — a circle</option>
              <option value="private">Private — you + partners</option>
            </Select>
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="d-notes">Notes</Label>
            <Textarea id="d-notes" rows={4} value={form.notes ?? ""} onChange={(e) => set("notes", e.target.value)} />
          </div>
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save changes"}
            </Button>
            {msg && <span className="text-sm text-emerald-500">{msg}</span>}
            {err && <span className="text-sm text-destructive">{err}</span>}
          </div>
        </form>
      </Card>
    </div>
  );
}
