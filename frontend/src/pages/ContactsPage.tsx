import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, Plus, RefreshCw } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Contact, SyncResult, Visibility } from "@/lib/types";
import { Badge, Button, Card, Input, Label, Select } from "@/components/ui";
import { visibilityStyles } from "@/lib/contacts";
import { useAuth } from "@/auth/AuthContext";

export function ContactsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { me } = useAuth();
  const cc = me?.phone_country_code ?? "+41";
  const phoneFmt = me?.phone_number_format ?? "xxx xxx xx xx";

  const { data: contacts, isLoading, error } = useQuery({
    queryKey: ["contacts"],
    queryFn: () => api.get<Contact[]>("/api/contacts"),
  });

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [birthday, setBirthday] = useState("");
  const [organization, setOrganization] = useState("");
  const [visibility, setVisibility] = useState<Visibility>("private");
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState<string | null>(null);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  function openForm() {
    setPhone(`${cc} `); // prefill the country code
    setShowForm(true);
  }

  async function createContact(e: FormEvent) {
    e.preventDefault();
    setFormErr(null);
    setBusy(true);
    try {
      const trimmedPhone = phone.trim();
      const created = await api.post<Contact>("/api/contacts", {
        display_name: name,
        emails: email ? [{ type: "home", value: email }] : [],
        phones: trimmedPhone && trimmedPhone !== cc ? [{ type: "cell", value: trimmedPhone }] : [],
        birthday: birthday || null,
        organization: organization || null,
        visibility,
      });
      setName("");
      setEmail("");
      setPhone("");
      setBirthday("");
      setOrganization("");
      setVisibility("private");
      setShowForm(false);
      await qc.invalidateQueries({ queryKey: ["contacts"] });
      navigate(`/contacts/${created.id}`); // open detail to add more (addresses, etc.)
    } catch (err) {
      setFormErr(err instanceof ApiError ? err.message : "Could not create contact");
    } finally {
      setBusy(false);
    }
  }

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

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Contacts</h1>
        <span className="text-sm text-muted-foreground">{contacts?.length ?? 0} people</span>
        <div className="ml-auto flex gap-2">
          <Button variant="secondary" onClick={() => void syncNow()} disabled={busy}>
            <RefreshCw size={16} className={busy ? "animate-spin" : ""} /> Sync now
          </Button>
          <Button onClick={() => (showForm ? setShowForm(false) : openForm())}>
            <Plus size={16} /> New contact
          </Button>
        </div>
      </div>

      {syncMsg && (
        <Card className="bg-muted/40 px-4 py-2.5 text-sm text-muted-foreground">{syncMsg}</Card>
      )}

      {showForm && (
        <Card className="p-4">
          <form onSubmit={createContact} className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label htmlFor="c-name">Name</Label>
              <Input
                id="c-name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Grace Hopper"
              />
            </div>
            <div>
              <Label htmlFor="c-email">Email</Label>
              <Input
                id="c-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="grace@example.com"
              />
            </div>
            <div>
              <Label htmlFor="c-phone">Phone</Label>
              <Input
                id="c-phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder={`${cc} ${phoneFmt}`}
              />
            </div>
            <div>
              <Label htmlFor="c-bday">Birthday</Label>
              <Input id="c-bday" type="date" value={birthday} onChange={(e) => setBirthday(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="c-org">Organization</Label>
              <Input id="c-org" value={organization} onChange={(e) => setOrganization(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="c-vis">Visibility</Label>
              <Select
                id="c-vis"
                value={visibility}
                onChange={(e) => setVisibility(e.target.value as Visibility)}
              >
                <option value="private">Private — you + partners</option>
                <option value="public">Public — all users</option>
              </Select>
            </div>
            <div className="flex items-end gap-2">
              <Button type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
            {formErr && <p className="text-sm text-destructive sm:col-span-2">{formErr}</p>}
          </form>
        </Card>
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

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {contacts?.map((c) => (
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
