import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { fetchCurrentUser, updateCurrentUser, UpdateSettingsPayload } from "../api/auth";

function formatApiError(err: any): string {
  const detail = err.response?.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((item: { msg?: string }) => item.msg ?? "Invalid input").join(", ");
  }
  if (typeof err.message === "string" && err.message) {
    return err.message;
  }
  return "Failed to save settings";
}

export default function SettingsPage(): JSX.Element {
  const navigate = useNavigate();
  const feedbackRef = useRef<HTMLDivElement | null>(null);
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
  const [saving, setSaving] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [success, setSuccess] = useState<string>("");

  useEffect(() => {
    if ((error || success) && feedbackRef.current) {
      feedbackRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [error, success]);

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

  function validatePasswordChange(): string | null {
    const hasOld: boolean = oldPassword.trim().length > 0;
    const hasNew: boolean = newPassword.trim().length > 0;
    const hasConfirm: boolean = confirmPassword.trim().length > 0;

    if (!hasOld && !hasNew && !hasConfirm) {
      return null;
    }
    if (!hasOld) {
      return "Current password is required to set a new password";
    }
    if (!hasNew) {
      return "Enter a new password";
    }
    if (newPassword.length < 8) {
      return "Password must be at least 8 characters";
    }
    if (!/[A-Z]/.test(newPassword)) {
      return "Password needs an uppercase letter";
    }
    if (!/[a-z]/.test(newPassword)) {
      return "Password needs a lowercase letter";
    }
    if (!/\d/.test(newPassword)) {
      return "Password needs a digit";
    }
    if (newPassword !== confirmPassword) {
      return "Passwords do not match";
    }
    return null;
  }

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError("");
    setSuccess("");

    const passwordError: string | null = validatePasswordChange();
    if (passwordError) {
      setError(passwordError);
      return;
    }

    const trimmedUserName: string = userName.trim();
    const trimmedEmail: string = email.trim();
    const trimmedPhone: string = phone.trim();

    if (trimmedUserName && trimmedUserName.length < 3) {
      setError("Username must be at least 3 characters");
      return;
    }

    const payload: UpdateSettingsPayload = {};
    if (trimmedUserName) {
      payload.user_name = trimmedUserName;
    }
    if (trimmedEmail) {
      payload.email = trimmedEmail;
    }
    if (trimmedPhone) {
      payload.phone_number = trimmedPhone;
    }
    if (newPassword.trim()) {
      payload.old_password = oldPassword;
      payload.new_password = newPassword;
    }

    if (Object.keys(payload).length === 0) {
      setSuccess("No changes to save");
      return;
    }

    setSaving(true);
    try {
      const result = await updateCurrentUser(payload);
      if (result.access_token) {
        localStorage.setItem("access_token", result.access_token);
      }
      setCurrentUserName(result.user_name);
      setCurrentEmail(result.email);
      setCurrentPhone(result.phone_number);
      setUserName("");
      setEmail("");
      setPhone("");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSuccess(result.message);
    } catch (err: any) {
      if (err.response?.status === 401) {
        localStorage.removeItem("access_token");
        navigate("/login");
        return;
      }
      setError(formatApiError(err));
    } finally {
      setSaving(false);
    }
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
                    placeholder="Leave empty to keep current"
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
                    placeholder="Leave empty to keep current"
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
                    placeholder="Leave empty to keep current"
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

              <div ref={feedbackRef} className="settings-feedback">
                {error ? <div className="error-msg">{error}</div> : null}
                {success ? <div className="success-msg">{success}</div> : null}
              </div>

              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? "Saving..." : "Save changes"}
              </button>
            </form>
          ) : null}
        </section>
      </main>
    </div>
  );
}
