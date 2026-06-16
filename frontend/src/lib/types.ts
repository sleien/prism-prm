export interface UserOut {
  id: number;
  email: string;
  display_name: string;
  is_superuser: boolean;
}

export interface Me {
  user: UserOut;
  groups: string[];
  self_contact_id?: number | null;
  default_currency: string;
  phone_country_code: string;
  phone_number_format: string;
  nextcloud_configured: boolean;
  nextcloud_url?: string | null;
  nextcloud_username?: string | null;
  nextcloud_addressbook?: string | null;
  nextcloud_calendar?: string | null;
}

export interface AuthConfig {
  allow_registration: boolean;
  oidc_enabled: boolean;
  oidc_display_name: string;
}

export interface Group {
  id: number;
  name: string;
  description?: string | null;
  oidc_group?: string | null;
}

export type Visibility = "public" | "group" | "private";

export interface TypedValue {
  type: string;
  value: string;
}

export interface AddressItem {
  type: string;
  street: string;
  city: string;
  region: string;
  code: string;
  country: string;
}

export interface Contact {
  id: number;
  owner_id: number;
  display_name: string;
  first_name?: string | null;
  last_name?: string | null;
  organization?: string | null;
  job_title?: string | null;
  birthday?: string | null;
  notes?: string | null;
  emails: TypedValue[];
  phones: TypedValue[];
  addresses: AddressItem[];
  visibility: Visibility;
  group_id?: number | null;
  linked_user_id?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  nextcloud_uid?: string | null;
  last_synced_at?: string | null;
  dirty: boolean;
}

export interface RelationshipType {
  id: number;
  name: string;
  reverse_name?: string | null;
}

export interface RelatedContact {
  relationship_id: number;
  contact_id: number;
  contact_name: string;
  label: string;
}

export interface LifeEventType {
  id: number;
  name: string;
  emoji?: string | null;
}

export interface LifeEvent {
  id: number;
  contact_id: number;
  title: string;
  emoji?: string | null;
  happened_on?: string | null;
  note?: string | null;
}

export interface SyncResult {
  pushed: number;
  created: number;
  updated: number;
  deleted: number;
  conflicts: number;
  skipped_reason?: string | null;
  errors: string[];
}

export interface EventReminder {
  id: number;
  message: string;
  remind_at: string;
  channel: string;
  done: boolean;
}

export interface EventAttendee {
  id: number;
  contact_id: number | null;
  user_id: number | null;
  status: string;
}

export interface Prompt {
  id: string;
  type: string; // "scale" | "text" | "number" | "boolean"
  label: string;
  min?: number | null;
  max?: number | null;
}

export interface JournalTemplate {
  id: number;
  owner_id: number;
  name: string;
  cadence: "daily" | "weekly";
  prompts: Prompt[];
  reminder_time?: string | null;
  visibility: Visibility;
  active: boolean;
}

export interface JournalEntry {
  id: number;
  template_id: number;
  owner_id: number;
  contact_id?: number | null;
  entry_date: string;
  period_key: string;
  data: Record<string, unknown>;
  mood?: number | null;
  created_at: string;
}

export interface MoodPoint {
  entry_date: string;
  mood: number;
}

export interface Summary {
  contacts_count: number;
  events_upcoming: number;
  journal_templates: number;
  mood_trend: MoodPoint[];
  upcoming_events: CalEvent[];
  recent_entries: JournalEntry[];
}

export interface AttendeeDetail {
  attendee_id: number;
  contact_id: number | null;
  name: string;
  emails: TypedValue[];
  phones: TypedValue[];
  status: string;
  mine: boolean;
}

export interface Weather {
  date: string;
  temp_max: number | null;
  temp_min: number | null;
  weather_code: number;
  description: string;
  emoji: string;
  precipitation_probability: number | null;
}

// Named CalEvent to avoid clashing with the DOM's global Event type.
export interface CalEvent {
  id: number;
  owner_id: number;
  title: string;
  description?: string | null;
  starts_at: string;
  ends_at?: string | null;
  all_day: boolean;
  location?: string | null;
  cost_amount?: string | null;
  cost_currency?: string | null;
  visibility: Visibility;
  group_id?: number | null;
  attendees: EventAttendee[];
  reminders: EventReminder[];
  nextcloud_uid?: string | null;
  last_synced_at?: string | null;
  weather?: Weather | null;
}
