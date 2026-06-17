import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Coins, MapPin, Trash2, UserPlus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { AttendeeDetail, CalEvent, Contact, EventType, Visibility } from "@/lib/types";
import { Button, Card, Input, Label, Select, Textarea } from "@/components/ui";
import { useDateFormat } from "@/lib/dates";
import { useAuth } from "@/auth/AuthContext";

const reminderOptions = [
  { label: "Keep current", value: "keep" },
  { label: "No reminder", value: "-1" },
  { label: "15 minutes before", value: "15" },
  { label: "1 hour before", value: "60" },
  { label: "1 day before", value: "1440" },
];

function toLocalInput(iso: string, allDay: boolean): string {
  if (allDay) return iso.slice(0, 10);
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function nowValue(allDay: boolean): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  return allDay ? date : `${date}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function EventDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { me } = useAuth();
  const { formatDateTime } = useDateFormat();

  const { data: event, isLoading, error } = useQuery({
    queryKey: ["event", id],
    queryFn: () => api.get<CalEvent>(`/api/events/${id}`),
  });
  const { data: contacts } = useQuery({
    queryKey: ["contacts"],
    queryFn: () => api.get<Contact[]>("/api/contacts"),
  });
  const { data: attendees } = useQuery({
    queryKey: ["event-attendees", id],
    queryFn: () => api.get<AttendeeDetail[]>(`/api/events/${id}/attendees`),
  });
  const { data: eventTypes } = useQuery({
    queryKey: ["event-types"],
    queryFn: () => api.get<EventType[]>("/api/event-types"),
  });

  const canEdit = !!event && me?.user.id === event.owner_id;

  // editable form state
  const [title, setTitle] = useState("");
  const [allDay, setAllDay] = useState(false);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [location, setLocation] = useState("");
  const [cost, setCost] = useState("");
  const [currency, setCurrency] = useState("CHF");
  const [visibility, setVisibility] = useState<Visibility>("private");
  const [eventType, setEventType] = useState("");
  const [picked, setPicked] = useState<number[]>([]);
  const [attendeeSearch, setAttendeeSearch] = useState("");
  const [description, setDescription] = useState("");
  const [reminder, setReminder] = useState("keep");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!event) return;
    setTitle(event.title);
    setAllDay(event.all_day);
    setStart(toLocalInput(event.starts_at, event.all_day));
    setEnd(event.ends_at ? toLocalInput(event.ends_at, event.all_day) : "");
    setLocation(event.location ?? "");
    setCost(event.cost_amount ?? "");
    setCurrency(event.cost_currency ?? me?.default_currency ?? "CHF");
    setVisibility(event.visibility);
    setEventType(event.event_type ?? "");
    setPicked(event.attendees.map((a) => a.contact_id).filter((x): x is number => x != null));
    setDescription(event.description ?? "");
    setReminder("keep");
  }, [event, me]);

  async function save(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setMsg(null);
    setBusy(true);
    try {
      const toIso = (v: string) => (allDay ? `${v}T12:00:00Z` : new Date(v).toISOString());
      const body: Record<string, unknown> = {
        title,
        all_day: allDay,
        starts_at: toIso(start),
        ends_at: end ? toIso(end) : null,
        location: location || null,
        cost_amount: cost || null,
        cost_currency: cost ? currency : null,
        visibility,
        event_type: eventType || null,
        description: description || null,
        attendee_contact_ids: picked,
      };
      if (reminder !== "keep") {
        body.reminders = reminder === "-1" ? [] : [{ minutes_before: Number(reminder) }];
      }
      await api.patch<CalEvent>(`/api/events/${id}`, body);
      await qc.invalidateQueries({ queryKey: ["event", id] });
      await qc.invalidateQueries({ queryKey: ["events"] });
      await qc.invalidateQueries({ queryKey: ["event-attendees", id] });
      setMsg("Saved");
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Delete this event? Removes it from the Nextcloud calendar too.")) return;
    setBusy(true);
    try {
      await api.del(`/api/events/${id}`);
      await qc.invalidateQueries({ queryKey: ["events"] });
      navigate("/events");
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not delete");
      setBusy(false);
    }
  }

  function togglePick(cid: number) {
    setPicked((p) => (p.includes(cid) ? p.filter((x) => x !== cid) : [...p, cid]));
  }

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error || !event)
    return (
      <div className="space-y-4">
        <BackLink />
        <p className="text-sm text-destructive">
          {error instanceof ApiError ? error.message : "Event not found"}
        </p>
      </div>
    );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <BackLink />
        {event.last_synced_at && (
          <span className="text-xs text-muted-foreground">✓ in Nextcloud calendar</span>
        )}
        {canEdit && (
          <Button variant="ghost" className="ml-auto text-destructive" onClick={() => void remove()} disabled={busy}>
            <Trash2 size={16} /> Delete
          </Button>
        )}
      </div>

      <Card className="p-5">
        {canEdit ? (
          <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label htmlFor="ev-title">Title</Label>
              <Input id="ev-title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <label htmlFor="ev-allday" className="flex items-center gap-2 text-sm sm:col-span-2">
              <input
                id="ev-allday"
                type="checkbox"
                checked={allDay}
                onChange={(e) => setAllDay(e.target.checked)}
                className="h-4 w-4 accent-[hsl(var(--primary))]"
              />
              All day (date only)
            </label>
            <div>
              <Label htmlFor="ev-start">Starts</Label>
              <div className="flex gap-2">
                <Input
                  id="ev-start"
                  type={allDay ? "date" : "datetime-local"}
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                />
                <Button type="button" variant="secondary" onClick={() => setStart(nowValue(allDay))}>
                  Today
                </Button>
              </div>
            </div>
            <div>
              <Label htmlFor="ev-end">Ends</Label>
              <Input
                id="ev-end"
                type={allDay ? "date" : "datetime-local"}
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="ev-loc">Location</Label>
              <Input id="ev-loc" value={location} onChange={(e) => setLocation(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label htmlFor="ev-cost">Cost</Label>
                <Input id="ev-cost" type="number" step="0.01" value={cost} onChange={(e) => setCost(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="ev-cur">Currency</Label>
                <Input id="ev-cur" value={currency} onChange={(e) => setCurrency(e.target.value)} />
              </div>
            </div>
            <div>
              <Label htmlFor="ev-rem">Reminder</Label>
              <Select id="ev-rem" value={reminder} onChange={(e) => setReminder(e.target.value)}>
                {reminderOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="ev-vis">Visibility</Label>
              <Select id="ev-vis" value={visibility} onChange={(e) => setVisibility(e.target.value as Visibility)}>
                <option value="private">Private</option>
                <option value="public">Public</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="ev-type">Type</Label>
              <Select id="ev-type" value={eventType} onChange={(e) => setEventType(e.target.value)}>
                <option value="">— none —</option>
                {(eventTypes ?? []).map((t) => (
                  <option key={t.id} value={t.name}>
                    {t.emoji ? `${t.emoji} ` : ""}
                    {t.name}
                  </option>
                ))}
              </Select>
            </div>
            {contacts && contacts.length > 0 && (
              <div className="sm:col-span-2">
                <Label>Attendees</Label>
                <Input
                  className="mb-2"
                  placeholder="Search contacts…"
                  value={attendeeSearch}
                  onChange={(e) => setAttendeeSearch(e.target.value)}
                />
                <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
                  {contacts
                    .filter(
                      (c) =>
                        picked.includes(c.id) ||
                        c.display_name.toLowerCase().includes(attendeeSearch.toLowerCase()),
                    )
                    .map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => togglePick(c.id)}
                        className={
                          "rounded-full border px-3 py-1 text-sm transition " +
                          (picked.includes(c.id)
                            ? "border-primary bg-primary/15 text-foreground"
                            : "text-muted-foreground hover:bg-accent")
                        }
                      >
                        {c.display_name}
                      </button>
                    ))}
                </div>
              </div>
            )}
            <div className="sm:col-span-2">
              <Label htmlFor="ev-notes">Notes (shared with everyone who can see this event)</Label>
              <Textarea
                id="ev-notes"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-3 sm:col-span-2">
              <Button type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save changes"}
              </Button>
              {msg && <span className="text-sm text-emerald-500">{msg}</span>}
              {err && <span className="text-sm text-destructive">{err}</span>}
            </div>
          </form>
        ) : (
          <div className="space-y-2">
            <div className="text-lg font-medium">{event.title}</div>
            <div className="text-sm text-muted-foreground">
              {formatDateTime(event.starts_at, !event.all_day)}
            </div>
            {event.location && (
              <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <MapPin size={14} /> {event.location}
              </div>
            )}
            {event.cost_amount && (
              <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Coins size={14} /> {event.cost_amount} {event.cost_currency}
              </div>
            )}
            {event.description && (
              <div className="whitespace-pre-wrap pt-1 text-sm">{event.description}</div>
            )}
            <p className="text-xs text-muted-foreground">Shared with you — you can’t edit it.</p>
          </div>
        )}
      </Card>

      <EventNotes eventId={id} />
      <EventAttendees eventId={id} attendees={attendees ?? []} />
    </div>
  );
}

function BackLink() {
  return (
    <Link to="/events" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft size={16} /> Back
    </Link>
  );
}

function EventNotes({ eventId }: { eventId: number }) {
  const { data } = useQuery({
    queryKey: ["event-note", eventId],
    queryFn: () => api.get<{ content: string }>(`/api/events/${eventId}/note`),
  });
  const [content, setContent] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (data) setContent(data.content);
  }, [data]);

  async function save() {
    await api.put(`/api/events/${eventId}/note`, { content });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <Card className="p-5">
      <div className="mb-1 font-medium">My private notes</div>
      <p className="mb-2 text-xs text-muted-foreground">Only you can see these.</p>
      <Textarea rows={3} value={content} onChange={(e) => setContent(e.target.value)} />
      <div className="mt-2 flex items-center gap-3">
        <Button type="button" variant="secondary" onClick={() => void save()}>
          Save note
        </Button>
        {saved && <span className="text-sm text-emerald-500">Saved</span>}
      </div>
    </Card>
  );
}

function EventAttendees({ eventId, attendees }: { eventId: number; attendees: AttendeeDetail[] }) {
  const qc = useQueryClient();
  const [importing, setImporting] = useState<number | null>(null);

  async function importContact(attendeeId: number) {
    setImporting(attendeeId);
    try {
      await api.post(`/api/events/${eventId}/attendees/${attendeeId}/import`);
      await qc.invalidateQueries({ queryKey: ["event-attendees", eventId] });
      await qc.invalidateQueries({ queryKey: ["contacts"] });
    } finally {
      setImporting(null);
    }
  }

  if (attendees.length === 0) return null;
  return (
    <Card className="p-5">
      <div className="mb-3 font-medium">Attendees</div>
      <ul className="space-y-2">
        {attendees.map((a) => (
          <li key={a.attendee_id} className="flex items-center justify-between gap-3 text-sm">
            <div>
              <div>{a.name}</div>
              {a.emails[0] && <div className="text-xs text-muted-foreground">{a.emails[0].value}</div>}
              {a.phones[0] && <div className="text-xs text-muted-foreground">{a.phones[0].value}</div>}
            </div>
            {a.mine ? (
              <span className="text-xs text-muted-foreground">in your contacts</span>
            ) : (
              <Button
                type="button"
                variant="secondary"
                onClick={() => void importContact(a.attendee_id)}
                disabled={importing === a.attendee_id}
              >
                <UserPlus size={14} /> Add to my contacts
              </Button>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
