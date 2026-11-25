import { useEffect, useState } from "react";
import { fetchMe, logout } from "./api.js";
import MapView from "./components/MapView.jsx";

export default function App() {
  const [user, setUser] = useState(null);

  useEffect(() => {
    fetchMe()
      .then((data) => {
        if (data) setUser(data);
      })
      .catch(() => {});
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      setUser(null);
    }
  };

  return (
    <MapView
      user={user}
      onAuth={(handle) => setUser({ handle })}
      onLogout={handleLogout}
    />
  );
}
