import { useState } from "react";
import { login, signup } from "../api.js";

function errorMessage(error) {
  if (error.status === 401) return "Wrong handle or password";
  if (error.status === 409) return "That handle is taken";
  if (error.status === 422) {
    return "Handle: 3-20 letters, digits or underscore. Password: 8-128 characters.";
  }
  if (error.status === 429) return "Too many attempts, try again later";
  return "Cannot reach the backend. Is it running on port 8000?";
}

export default function AuthPanel({ user, onAuth, onLogout }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState("login");
  const [handle, setHandle] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) {
    return (
      <div className="auth">
        <span className="auth-user">@{user.handle}</span>
        <button type="button" className="auth-btn" onClick={onLogout}>
          Log out
        </button>
      </div>
    );
  }

  const changeMode = (next) => {
    setMode(next);
    setMessage("");
  };

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const data =
        mode === "login"
          ? await login(handle, password)
          : await signup(handle, password);
      onAuth(data.handle);
      setOpen(false);
      setHandle("");
      setPassword("");
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        className="auth-btn"
        onClick={() => setOpen(true)}
      >
        Log in / Sign up
      </button>
    );
  }

  return (
    <form className="auth-form" onSubmit={submit}>
      <div className="auth-tabs">
        <button
          type="button"
          className={`auth-tab ${mode === "login" ? "auth-tab-on" : ""}`}
          onClick={() => changeMode("login")}
        >
          Log in
        </button>
        <button
          type="button"
          className={`auth-tab ${mode === "signup" ? "auth-tab-on" : ""}`}
          onClick={() => changeMode("signup")}
        >
          Sign up
        </button>
      </div>

      <input
        className="auth-input"
        placeholder="handle"
        aria-label="handle"
        autoComplete="username"
        value={handle}
        onChange={(event) => setHandle(event.target.value)}
      />
      <input
        className="auth-input"
        type="password"
        placeholder="password"
        aria-label="password"
        autoComplete={mode === "login" ? "current-password" : "new-password"}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />

      {message && <p className="auth-message">{message}</p>}

      <div className="auth-actions">
        <button type="submit" className="auth-btn" disabled={busy}>
          {busy ? "Please wait..." : mode === "login" ? "Log in" : "Sign up"}
        </button>
        <button
          type="button"
          className="auth-btn auth-btn-plain"
          onClick={() => {
            setOpen(false);
            setMessage("");
          }}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
