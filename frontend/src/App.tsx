import { AuthProvider } from "./auth/AuthContext";
import { useAuth } from "./auth/useAuth";
import { AuthScreen } from "./screens/AuthScreen";

function Shell() {
  const { status, user } = useAuth();
  if (status === "loading") return <div>Loading…</div>;
  if (status === "anonymous") return <AuthScreen />;
  return <div>Welcome, {user!.username}</div>;
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
