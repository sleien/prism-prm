import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Layout } from "@/components/Layout";
import { LoginPage } from "@/pages/LoginPage";
import { ContactsPage } from "@/pages/ContactsPage";
import { ContactDetailPage } from "@/pages/ContactDetailPage";
import { EventsPage } from "@/pages/EventsPage";
import { JournalPage } from "@/pages/JournalPage";
import { SummaryPage } from "@/pages/SummaryPage";
import { SettingsPage } from "@/pages/SettingsPage";

export function App() {
  const { me, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">Loading…</div>
    );
  }

  if (!me) {
    return (
      <Routes>
        <Route path="*" element={<LoginPage />} />
      </Routes>
    );
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<SummaryPage />} />
        <Route path="/contacts" element={<ContactsPage />} />
        <Route path="/contacts/:id" element={<ContactDetailPage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/journal" element={<JournalPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
