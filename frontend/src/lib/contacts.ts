import type { Visibility } from "@/lib/types";

export const visibilityStyles: Record<Visibility, string> = {
  public: "border-emerald-500/40 text-emerald-500",
  group: "border-sky-500/40 text-sky-500",
  private: "border-amber-500/40 text-amber-500",
};
