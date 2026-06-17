import { type FormEvent, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { JournalEntry, JournalTemplate, Prompt } from "@/lib/types";
import { useDateFormat } from "@/lib/dates";
import { Badge, Button, Card, Input, Label, Select, Textarea } from "@/components/ui";

type Answer = string | number | boolean;

function slug(s: string, fallback: string): string {
  const out = s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return out || fallback;
}

const PROMPT_TYPES = ["scale", "text", "number", "boolean"];

export function JournalPage() {
  const qc = useQueryClient();
  const { data: templates } = useQuery({
    queryKey: ["journal-templates"],
    queryFn: () => api.get<JournalTemplate[]>("/api/journal/templates"),
  });

  // Hidden (inactive) journals are managed from Settings and don't show here.
  const visible = (templates ?? []).filter((t) => t.active);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = visible.find((t) => t.id === selectedId) ?? visible[0] ?? null;

  // --- create-template form ---
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [cadence, setCadence] = useState<"daily" | "weekly">("daily");
  const [reminderTime, setReminderTime] = useState("");
  const [prompts, setPrompts] = useState<Prompt[]>([
    { id: "mood", type: "scale", label: "Mood", min: 1, max: 10 },
  ]);
  const [createErr, setCreateErr] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);

  function addPrompt() {
    setPrompts((p) => [...p, { id: `p${p.length}`, type: "text", label: "" }]);
  }
  function updatePrompt(i: number, patch: Partial<Prompt>) {
    setPrompts((p) => p.map((q, idx) => (idx === i ? { ...q, ...patch } : q)));
  }
  function removePrompt(i: number) {
    setPrompts((p) => p.filter((_, idx) => idx !== i));
  }

  function resetForm() {
    setShowCreate(false);
    setEditingId(null);
    setName("");
    setCadence("daily");
    setReminderTime("");
    setPrompts([{ id: "mood", type: "scale", label: "Mood", min: 1, max: 10 }]);
    setCreateErr(null);
  }
  function newJournal() {
    resetForm();
    setShowCreate(true);
  }
  function startEdit(t: JournalTemplate) {
    setEditingId(t.id);
    setName(t.name);
    setCadence(t.cadence);
    setReminderTime(t.reminder_time ? t.reminder_time.slice(0, 5) : "");
    setPrompts(
      t.prompts.length ? t.prompts : [{ id: "mood", type: "scale", label: "Mood", min: 1, max: 10 }],
    );
    setCreateErr(null);
    setShowCreate(true);
  }

  async function saveTemplate(e: FormEvent) {
    e.preventDefault();
    setCreateErr(null);
    try {
      const body: Record<string, unknown> = {
        name,
        cadence,
        prompts: prompts.map((p, i) => ({ ...p, id: slug(p.label, `prompt_${i}`) })),
        reminder_time: reminderTime || null,
      };
      let savedId = editingId;
      if (editingId) {
        await api.patch<JournalTemplate>(`/api/journal/templates/${editingId}`, body);
      } else {
        savedId = (await api.post<JournalTemplate>("/api/journal/templates", body)).id;
      }
      resetForm();
      await qc.invalidateQueries({ queryKey: ["journal-templates"] });
      await qc.invalidateQueries({ queryKey: ["summary"] });
      if (savedId) setSelectedId(savedId);
    } catch (err) {
      setCreateErr(err instanceof ApiError ? err.message : "Could not save journal");
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Journal</h1>
        <div className="ml-auto flex gap-2">
          {selected && (
            <Button variant="secondary" onClick={() => startEdit(selected)}>
              Edit
            </Button>
          )}
          <Button onClick={newJournal}>
            <Plus size={16} /> New journal
          </Button>
        </div>
      </div>

      {showCreate && (
        <Card className="p-4">
          <form onSubmit={saveTemplate} className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-1">
                <Label htmlFor="j-name">Name</Label>
                <Input id="j-name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Daily check-in" />
              </div>
              <div>
                <Label htmlFor="j-cadence">Cadence</Label>
                <Select id="j-cadence" value={cadence} onChange={(e) => setCadence(e.target.value as "daily" | "weekly")}>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </Select>
              </div>
              <div>
                <Label htmlFor="j-rem">Reminder time</Label>
                <Input id="j-rem" type="time" value={reminderTime} onChange={(e) => setReminderTime(e.target.value)} />
              </div>
            </div>

            <div>
              <Label>Prompts</Label>
              <div className="space-y-2">
                {prompts.map((p, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2">
                    <Select
                      className="w-28"
                      value={p.type}
                      onChange={(e) => updatePrompt(i, { type: e.target.value })}
                    >
                      {PROMPT_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </Select>
                    <Input
                      className="flex-1"
                      placeholder="Question label"
                      value={p.label}
                      onChange={(e) => updatePrompt(i, { label: e.target.value })}
                    />
                    {p.type === "scale" && (
                      <>
                        <Input
                          className="w-16"
                          type="number"
                          value={p.min ?? 1}
                          onChange={(e) => updatePrompt(i, { min: Number(e.target.value) })}
                        />
                        <Input
                          className="w-16"
                          type="number"
                          value={p.max ?? 10}
                          onChange={(e) => updatePrompt(i, { max: Number(e.target.value) })}
                        />
                      </>
                    )}
                    <button type="button" onClick={() => removePrompt(i)} className="text-muted-foreground hover:text-destructive">
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
              <Button type="button" variant="ghost" className="mt-2" onClick={addPrompt}>
                <Plus size={14} /> Add prompt
              </Button>
            </div>

            <div className="flex items-center gap-2">
              <Button type="submit">{editingId ? "Save changes" : "Create journal"}</Button>
              <Button type="button" variant="ghost" onClick={resetForm}>
                Cancel
              </Button>
              {createErr && <span className="text-sm text-destructive">{createErr}</span>}
            </div>
          </form>
        </Card>
      )}

      {visible.length === 0 && !showCreate && (
        <Card className="p-8 text-center text-muted-foreground">
          No journals yet. Create one — add a mood scale and a prompt or two, set a reminder time,
          and it’ll nudge you from your Nextcloud calendar. (Hidden journals live in Settings.)
        </Card>
      )}

      {visible.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {visible.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedId(t.id)}
              className={
                "rounded-full border px-3 py-1 text-sm transition " +
                (selected?.id === t.id ? "border-primary bg-primary/15" : "text-muted-foreground hover:bg-accent")
              }
            >
              {t.name}
            </button>
          ))}
        </div>
      )}

      {selected && <JournalEntryEditor template={selected} />}
    </div>
  );
}

function JournalEntryEditor({ template }: { template: JournalTemplate }) {
  const qc = useQueryClient();
  const { data: entries } = useQuery({
    queryKey: ["journal-entries", template.id],
    queryFn: () => api.get<JournalEntry[]>(`/api/journal/templates/${template.id}/entries`),
  });

  const { formatDate } = useDateFormat();
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Prefill from the most recent entry when the template or its entries change.
  useEffect(() => {
    setAnswers((entries?.[0]?.data as Record<string, Answer>) ?? {});
    setMsg(null);
  }, [template.id, entries]);

  function setAnswer(id: string, value: Answer) {
    setAnswers((a) => ({ ...a, [id]: value }));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await api.put(`/api/journal/templates/${template.id}/entries`, { data: answers });
      await qc.invalidateQueries({ queryKey: ["journal-entries", template.id] });
      await qc.invalidateQueries({ queryKey: ["summary"] });
      setMsg("Saved ✓");
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="font-medium">{template.name}</span>
        <Badge className="border-border text-muted-foreground">{template.cadence}</Badge>
        {template.reminder_time && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Bell size={12} /> {template.reminder_time}
          </span>
        )}
      </div>

      <form onSubmit={submit} className="space-y-4">
        {template.prompts.map((p) => (
          <div key={p.id}>
            <Label htmlFor={`a-${p.id}`}>{p.label || p.id}</Label>
            {p.type === "scale" ? (
              <div className="flex items-center gap-3">
                <input
                  id={`a-${p.id}`}
                  type="range"
                  min={p.min ?? 1}
                  max={p.max ?? 10}
                  value={Number(answers[p.id] ?? p.min ?? 1)}
                  onChange={(e) => setAnswer(p.id, Number(e.target.value))}
                  className="flex-1 accent-[hsl(var(--primary))]"
                />
                <span className="w-8 text-right text-sm tabular-nums">{Number(answers[p.id] ?? p.min ?? 1)}</span>
              </div>
            ) : p.type === "number" ? (
              <Input
                id={`a-${p.id}`}
                type="number"
                value={String(answers[p.id] ?? "")}
                onChange={(e) => setAnswer(p.id, Number(e.target.value))}
              />
            ) : p.type === "boolean" ? (
              <input
                id={`a-${p.id}`}
                type="checkbox"
                checked={Boolean(answers[p.id])}
                onChange={(e) => setAnswer(p.id, e.target.checked)}
                className="h-4 w-4 accent-[hsl(var(--primary))]"
              />
            ) : (
              <Textarea
                id={`a-${p.id}`}
                rows={2}
                value={String(answers[p.id] ?? "")}
                onChange={(e) => setAnswer(p.id, e.target.value)}
              />
            )}
          </div>
        ))}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save entry"}
          </Button>
          {msg && <span className="text-sm text-emerald-500">{msg}</span>}
        </div>
      </form>

      {entries && entries.length > 0 && (
        <div className="mt-6">
          <div className="mb-2 text-sm font-medium text-muted-foreground">History</div>
          <ul className="space-y-1 text-sm">
            {entries.map((en) => (
              <li key={en.id} className="flex items-center justify-between gap-2 border-b border-border/50 py-1">
                <span>{formatDate(en.entry_date)}</span>
                {en.mood != null && <span className="text-muted-foreground">mood {en.mood}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
