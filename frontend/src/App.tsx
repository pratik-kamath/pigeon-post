import { AuthProvider } from "./auth/AuthContext";
import { useAuth } from "./auth/useAuth";
import { AuthScreen } from "./screens/AuthScreen";
import { Dashboard } from "./screens/Dashboard";

function Shell() {
  const { status } = useAuth();
  if (status === "loading") return <div>Loading…</div>;
  if (status === "anonymous") return <AuthScreen />;
  return <Dashboard />;
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
