import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, UserMinus } from "lucide-react";
import { api } from "@/lib/api";
import type { Group, UserOut } from "@/lib/types";
import { useAuth } from "@/auth/AuthContext";
import { Button, Card, Input, Select } from "@/components/ui";

export function SettingsPage() {
  const qc = useQueryClient();
  const { me } = useAuth();
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: () => api.get<UserOut[]>("/api/users") });
  const { data: partners } = useQuery({
    queryKey: ["partners"],
    queryFn: () => api.get<UserOut[]>("/api/sharing/partners"),
  });
  const { data: groups } = useQuery({ queryKey: ["groups"], queryFn: () => api.get<Group[]>("/api/groups") });

  const partnerIds = new Set((partners ?? []).map((p) => p.id));
  const others = (users ?? []).filter((u) => u.id !== me?.user.id);

  async function togglePartner(id: number, on: boolean) {
    if (on) await api.put(`/api/sharing/partners/${id}`);
    else await api.del(`/api/sharing/partners/${id}`);
    await qc.invalidateQueries({ queryKey: ["partners"] });
  }

  const [groupName, setGroupName] = useState("");
  async function createGroup(e: FormEvent) {
    e.preventDefault();
    if (!groupName.trim()) return;
    await api.post<Group>("/api/groups", { name: groupName });
    setGroupName("");
    await qc.invalidateQueries({ queryKey: ["groups"] });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

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
        <div className="mb-1 font-medium">Groups</div>
        <p className="mb-3 text-sm text-muted-foreground">
          Group members can see records you share with the group.
        </p>
        <form onSubmit={createGroup} className="mb-4 flex gap-2">
          <Input
            value={groupName}
            onChange={(e) => setGroupName(e.target.value)}
            placeholder="New group name (e.g. Family)"
            className="max-w-xs"
          />
          <Button type="submit">
            <Plus size={16} /> Create
          </Button>
        </form>
        <div className="space-y-3">
          {(groups ?? []).map((g) => (
            <GroupCard key={g.id} group={g} users={users ?? []} />
          ))}
          {groups && groups.length === 0 && (
            <p className="text-sm text-muted-foreground">No groups yet.</p>
          )}
        </div>
      </Card>
    </div>
  );
}

function GroupCard({ group, users }: { group: Group; users: UserOut[] }) {
  const qc = useQueryClient();
  const { data: members } = useQuery({
    queryKey: ["group-members", group.id],
    queryFn: () => api.get<UserOut[]>(`/api/groups/${group.id}/members`),
  });
  const memberIds = new Set((members ?? []).map((m) => m.id));
  const [addId, setAddId] = useState("");

  async function add() {
    if (!addId) return;
    await api.put(`/api/groups/${group.id}/members/${addId}`);
    setAddId("");
    await qc.invalidateQueries({ queryKey: ["group-members", group.id] });
  }
  async function remove(id: number) {
    await api.del(`/api/groups/${group.id}/members/${id}`);
    await qc.invalidateQueries({ queryKey: ["group-members", group.id] });
  }

  const candidates = users.filter((u) => !memberIds.has(u.id));

  return (
    <Card className="bg-muted/30 p-4">
      <div className="mb-2 font-medium">{group.name}</div>
      <div className="flex flex-wrap gap-2">
        {(members ?? []).map((m) => (
          <span key={m.id} className="flex items-center gap-1 rounded-full border px-2 py-0.5 text-sm">
            {m.display_name}
            <button onClick={() => void remove(m.id)} className="text-muted-foreground hover:text-destructive">
              <UserMinus size={13} />
            </button>
          </span>
        ))}
      </div>
      {candidates.length > 0 && (
        <div className="mt-3 flex gap-2">
          <Select value={addId} onChange={(e) => setAddId(e.target.value)} className="max-w-xs">
            <option value="">Add member…</option>
            {candidates.map((u) => (
              <option key={u.id} value={u.id}>
                {u.display_name}
              </option>
            ))}
          </Select>
          <Button type="button" variant="secondary" onClick={() => void add()}>
            Add
          </Button>
        </div>
      )}
    </Card>
  );
}
