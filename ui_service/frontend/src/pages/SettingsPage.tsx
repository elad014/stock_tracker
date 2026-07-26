import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { fetchCurrentUser } from "../api/auth";

export default function SettingsPage(): JSX.Element {
  const navigate = useNavigate();
  const [currentUserName, setCurrentUserName] = useState<string>("");
  const [currentEmail, setCurrentEmail] = useState<string>("");
  const [currentPhone, setCurrentPhone] = useState<string>("");
  const [userName, setUserName] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [phone, setPhone] = useState<string>("");
  const [oldPassword, setOldPassword] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string>("");

  useEffect(() => {
    async function loadUser(): Promise<void> {
      setLoadError("");
      try {
        const user = await fetchCurrentUser();
        setCurrentUserName(user.user_name);
        setCurrentEmail(user.email);
        setCurrentPhone(user.phone_number);
      } catch (err: any) {
        if (err.response?.status === 401) {
          localStorage.removeItem("access_token");
          navigate("/login");
          return;
        }
        setLoadError(err.response?.data?.detail ?? "Failed to load account details");
      } finally {
        setLoading(false);
      }
    }

    void loadUser();
  }, [navigate]);

  function handleSubmit(e: FormEvent): void {
    e.preventDefault();
  }

  return (
    <div className="settings-page">
      <header className="settings-header">
        <span className="settings-logo">Stock Tracker</span>
        <button
          type="button"
          className="btn-outline"
          onClick={() => navigate("/dashboard")}
        >
          Back to dashboard
        </button>
      </header>

      <main className="settings-main">
        <section className="settings-panel">
          <h1>Settings</h1>
          <p className="settings-subtitle">Update your account details</p>

          {loading ? <p className="settings-hint">Loading account details...</p> : null}
          {loadError ? <div className="error-msg">{loadError}</div> : null}

          {!loading && !loadError ? (
            <form className="settings-form" onSubmit={handleSubmit}>
              <div className="settings-field-section">
                <h2 className="settings-section-title">Username</h2>
                <p className="settings-current-value">{currentUserName}</p>
                <div className="form-group">
                  <label htmlFor="settings-username">New username</label>
                  <input
                    id="settings-username"
                    type="text"
                    value={userName}
                    onChange={(e) => setUserName(e.target.value)}
                    placeholder="Your username"
                  />
                </div>
              </div>

              <div className="settings-field-section">
                <h2 className="settings-section-title">Email</h2>
                <p className="settings-current-value">{currentEmail}</p>
                <div className="form-group">
                  <label htmlFor="settings-email">New email</label>
                  <input
                    id="settings-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                  />
                </div>
              </div>

              <div className="settings-field-section">
                <h2 className="settings-section-title">Phone</h2>
                <p className="settings-current-value">{currentPhone}</p>
                <div className="form-group">
                  <label htmlFor="settings-phone">New phone</label>
                  <input
                    id="settings-phone"
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+1 234 567 8900"
                  />
                </div>
              </div>

              <div className="settings-field-section">
                <h2 className="settings-section-title">Change password</h2>
                <p className="settings-hint">
                  Enter your current password to set a new one
                </p>

                <div className="form-group">
                  <label htmlFor="settings-old-password">Current password</label>
                  <input
                    id="settings-old-password"
                    type="password"
                    value={oldPassword}
                    onChange={(e) => setOldPassword(e.target.value)}
                    placeholder="Current password"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="settings-new-password">New password</label>
                  <input
                    id="settings-new-password"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="New password"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="settings-confirm-password">Confirm new password</label>
                  <input
                    id="settings-confirm-password"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat new password"
                  />
                </div>
              </div>

              <button type="submit" className="btn-primary" disabled>
                Save changes
              </button>
            </form>
          ) : null}
        </section>
      </main>
    </div>
  );
}
