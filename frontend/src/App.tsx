import { AuthProvider } from "./auth/AuthContext";
import { useAuth } from "./auth/useAuth";

function Shell() {
  const { status, user } = useAuth();
  if (status === "loading") return <div>Loading…</div>;
  if (status === "anonymous") return <div>Pigeon Post — please log in (coming in Phase 2)</div>;
  return <div>Welcome, {user!.username}</div>;
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
