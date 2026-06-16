export interface UserOut {
  id: number;
  email: string;
  display_name: string;
  is_superuser: boolean;
}

export interface Me {
  user: UserOut;
  groups: string[];
}

export interface AuthConfig {
  allow_registration: boolean;
  oidc_enabled: boolean;
  oidc_display_name: string;
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
  nextcloud_uid?: string | null;
  last_synced_at?: string | null;
  dirty: boolean;
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
