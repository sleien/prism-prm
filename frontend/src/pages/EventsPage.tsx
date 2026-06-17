import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Coins, MapPin, Plus, Search, Trash2, Users } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { CalEvent, Contact, EventType, Visibility } from "@/lib/types";
import { Badge, Button, Card, Input, Label, Select, Textarea } from "@/components/ui";
import { formatDate, formatDateTime, type DateFormat } from "@/lib/dates";
import { useAuth } from "@/auth/AuthContext";

const reminderOptions = [
  { label: "No reminder", value: -1 },
  { label: "15 minutes before", value: 15 },
  { label: "1 hour before", value: 60 },
  { label: "1 day before", value: 1440 },
];

function fmt(iso: string, allDay: boolean, df: DateFormat): string {
  return allDay ? formatDate(iso, df) : formatDateTime(iso, df);
}

// A local-time value for a date or datetime-local input set to "now".
function nowValue(allDay: boolean): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  return allDay ? date : `${date}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function EventsPage() {
  const qc = useQueryClient();
  const { me } = useAuth();
  const df = (me?.date_format ?? "dd.mm.yyyy") as DateFormat;
  const { data: events, isLoading, error } = useQuery({
    queryKey: ["events"],
    queryFn: () => api.get<CalEvent[]>("/api/events"),
  });
  const { data: contacts } = useQuery({
    queryKey: ["contacts"],
    queryFn: () => api.get<Contact[]>("/api/contacts"),
  });
  const { data: eventTypes } = useQuery({
    queryKey: ["event-types"],
    queryFn: () => api.get<EventType[]>("/api/event-types"),
  });
  const contactName = (id: number | null) =>
    contacts?.find((c) => c.id === id)?.display_name ?? "Someone";
  const typeEmoji = (name?: string | null) =>
    eventTypes?.find((t) => t.name === name)?.emoji ?? "";

  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [location, setLocation] = useState("");
  const [cost, setCost] = useState("");
  const [currency, setCurrency] = useState(me?.default_currency ?? "CHF");
  const [visibility, setVisibility] = useState<Visibility>("private");
  const [eventType, setEventType] = useState("");
  const [allDay, setAllDay] = useState(false);
  const [attendees, setAttendees] = useState<number[]>([]);
  const [attendeeSearch, setAttendeeSearch] = useState("");
  const [description, setDescription] = useState("");
  const [reminder, setReminder] = useState(-1);
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  function toggleAttendee(id: number) {
    setAttendees((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));
  }

  const attendeeMatches = (contacts ?? []).filter(
    (c) => attendees.includes(c.id) || c.display_name.toLowerCase().includes(attendeeSearch.toLowerCase()),
  );

  async function createEvent(e: FormEvent) {
    e.preventDefault();
    setFormErr(null);
    setBusy(true);
    try {
      // For all-day events we anchor at noon UTC so the date stays stable across
      // time zones; the all_day flag tells the calendar to ignore the time.
      const toIso = (v: string) => (allDay ? `${v}T12:00:00Z` : new Date(v).toISOString());
      const body: Record<string, unknown> = {
        title,
        starts_at: toIso(start),
        all_day: allDay,
        event_type: eventType || null,
        visibility,
        attendee_contact_ids: attendees,
        reminders: reminder >= 0 ? [{ minutes_before: reminder }] : [],
      };
      if (end) body.ends_at = toIso(end);
      if (location) body.location = location;
      if (description) body.description = description;
      if (cost) {
        body.cost_amount = cost;
        body.cost_currency = currency;
      }
      await api.post<CalEvent>("/api/events", body);
      setTitle("");
      setStart("");
      setEnd("");
      setLocation("");
      setCost("");
      setAttendees([]);
      setAttendeeSearch("");
      setDescription("");
      setEventType("");
      setShowForm(false);
      await qc.invalidateQueries({ queryKey: ["events"] });
    } catch (err) {
      setFormErr(err instanceof ApiError ? err.message : "Could not create event");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    if (!confirm("Delete this event? Removes it from the Nextcloud calendar too.")) return;
    try {
      await api.del(`/api/events/${id}`);
      await qc.invalidateQueries({ queryKey: ["events"] });
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Could not delete");
    }
  }

  const eq = search.trim().toLowerCase();
  const filteredEvents = (events ?? []).filter((ev) => {
    if (!eq) return true;
    const hay = [
      ev.title,
      ev.description,
      ev.location,
      ev.event_type,
      ...ev.attendees.map((a) => contactName(a.contact_id)),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(eq);
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Events</h1>
        <span className="text-sm text-muted-foreground">{filteredEvents.length} events</span>
        <Button className="ml-auto" onClick={() => setShowForm((v) => !v)}>
          <Plus size={16} /> New event
        </Button>
      </div>

      {showForm && (
        <Card className="p-4">
          <form onSubmit={createEvent} className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label htmlFor="e-title">Title</Label>
              <Input
                id="e-title"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Dinner with Grace"
              />
            </div>
            <label htmlFor="e-allday" className="flex items-center gap-2 text-sm sm:col-span-2">
              <input
                id="e-allday"
                type="checkbox"
                checked={allDay}
                onChange={(e) => setAllDay(e.target.checked)}
                className="h-4 w-4 accent-[hsl(var(--primary))]"
              />
              All day (date only)
            </label>
            <div>
              <Label htmlFor="e-start">Starts</Label>
              <div className="flex gap-2">
                <Input
                  id="e-start"
                  type={allDay ? "date" : "datetime-local"}
                  required
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                />
                <Button type="button" variant="secondary" onClick={() => setStart(nowValue(allDay))}>
                  Today
                </Button>
              </div>
            </div>
            <div>
              <Label htmlFor="e-end">Ends (optional)</Label>
              <Input
                id="e-end"
                type={allDay ? "date" : "datetime-local"}
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="e-loc">Location</Label>
              <Input id="e-loc" value={location} onChange={(e) => setLocation(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label htmlFor="e-cost">Cost</Label>
                <Input
                  id="e-cost"
                  type="number"
                  step="0.01"
                  value={cost}
                  onChange={(e) => setCost(e.target.value)}
                  placeholder="0.00"
                />
              </div>
              <div>
                <Label htmlFor="e-cur">Currency</Label>
                <Input id="e-cur" value={currency} onChange={(e) => setCurrency(e.target.value)} />
              </div>
            </div>
            <div>
              <Label htmlFor="e-rem">Reminder</Label>
              <Select
                id="e-rem"
                value={String(reminder)}
                onChange={(e) => setReminder(Number(e.target.value))}
              >
                {reminderOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="e-vis">Visibility</Label>
              <Select
                id="e-vis"
                value={visibility}
                onChange={(e) => setVisibility(e.target.value as Visibility)}
              >
                <option value="private">Private</option>
                <option value="public">Public</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="e-type">Type</Label>
              <Select id="e-type" value={eventType} onChange={(e) => setEventType(e.target.value)}>
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
                  {attendeeMatches.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => toggleAttendee(c.id)}
                      className={
                        "rounded-full border px-3 py-1 text-sm transition " +
                        (attendees.includes(c.id)
                          ? "border-primary bg-primary/15 text-foreground"
                          : "text-muted-foreground hover:bg-accent")
                      }
                    >
                      {c.display_name}
                    </button>
                  ))}
                  {attendeeMatches.length === 0 && (
                    <span className="text-sm text-muted-foreground">No matches.</span>
                  )}
                </div>
              </div>
            )}
            <div className="sm:col-span-2">
              <Label htmlFor="e-notes">Notes (shared with everyone who can see this event)</Label>
              <Textarea
                id="e-notes"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2 sm:col-span-2">
              <Button type="submit" disabled={busy}>
                {busy ? "Saving…" : "Create event"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
              {formErr && <span className="text-sm text-destructive">{formErr}</span>}
            </div>
          </form>
        </Card>
      )}

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {error && (
        <p className="text-sm text-destructive">
          {error instanceof ApiError ? error.message : "Failed to load events"}
        </p>
      )}
      {events && events.length === 0 && !isLoading && (
        <Card className="p-8 text-center text-muted-foreground">
          No events yet. Log something you did with the people you track — it’s saved to your
          Nextcloud calendar too.
        </Card>
      )}

      {events && events.length > 0 && (
        <div className="relative">
          <Search
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            className="pl-9"
            placeholder="Search events by title, description, location, attendee…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      )}
      {events && events.length > 0 && filteredEvents.length === 0 && (
        <Card className="p-8 text-center text-muted-foreground">No events match your search.</Card>
      )}

      <div className="space-y-3">
        {filteredEvents.map((ev) => (
          <Card key={ev.id} className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Link to={`/events/${ev.id}`} className="font-medium hover:underline">
                    {ev.title}
                  </Link>
                  {ev.event_type && (
                    <Badge className="border-border text-muted-foreground">
                      {typeEmoji(ev.event_type)} {ev.event_type}
                    </Badge>
                  )}
                </div>
                <div className="mt-1 text-sm text-muted-foreground">
                  {fmt(ev.starts_at, ev.all_day, df)}
                  {ev.ends_at && ` — ${fmt(ev.ends_at, ev.all_day, df)}`}
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                  {ev.location && (
                    <span className="flex items-center gap-1">
                      <MapPin size={14} /> {ev.location}
                    </span>
                  )}
                  {ev.cost_amount && (
                    <span className="flex items-center gap-1">
                      <Coins size={14} /> {ev.cost_amount} {ev.cost_currency}
                    </span>
                  )}
                  {ev.attendees.length > 0 && (
                    <span className="flex items-center gap-1">
                      <Users size={14} />{" "}
                      {ev.attendees.map((a) => contactName(a.contact_id)).join(", ")}
                    </span>
                  )}
                  {ev.reminders.length > 0 && (
                    <span className="flex items-center gap-1">
                      <Bell size={14} /> {ev.reminders.length} reminder
                      {ev.reminders.length > 1 ? "s" : ""}
                    </span>
                  )}
                  {ev.weather && (
                    <span className="flex items-center gap-1" title={ev.weather.description}>
                      {ev.weather.emoji} {Math.round(Number(ev.weather.temp_max))}° /{" "}
                      {Math.round(Number(ev.weather.temp_min))}°
                      {ev.weather.precipitation_probability != null &&
                        ` · ${ev.weather.precipitation_probability}% rain`}
                    </span>
                  )}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {ev.last_synced_at ? "✓ in Nextcloud calendar" : "• not synced"}
                </div>
              </div>
              <button
                onClick={() => void remove(ev.id)}
                className="text-muted-foreground transition hover:text-destructive"
                title="Delete event"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
