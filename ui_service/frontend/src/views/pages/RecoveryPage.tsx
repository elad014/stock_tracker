import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { confirmPasswordReset, requestPasswordReset } from "../../services/authService";
import AuthLayout from "../components/AuthLayout";

type Step = "request" | "confirm" | "done";

export default function RecoveryPage(): JSX.Element {
  const [step, setStep] = useState<Step>("request");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleRequestReset(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    try {
      const msg = await requestPasswordReset(email);
      setSuccess(msg);
      setStep("confirm");
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Request failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmReset(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    try {
      await confirmPasswordReset(token, newPassword);
      setStep("done");
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Reset failed");
    } finally {
      setLoading(false);
    }
  }

  const subtitle: string | undefined =
    step === "done"
      ? undefined
      : step === "request"
        ? "Enter your email to receive a reset token"
        : "Enter the token and your new password";

  return (
    <AuthLayout title="Reset password" subtitle={subtitle}>
      <div className="step-indicator">
        <div className={`step ${step === "request" ? "active" : ""}`} />
        <div className={`step ${step === "confirm" ? "active" : ""}`} />
        <div className={`step ${step === "done" ? "active" : ""}`} />
      </div>

      {error && <div className="error-msg">{error}</div>}
      {success && step === "confirm" ? (
        <div className="success-msg">{success}</div>
      ) : null}

      {step === "done" ? (
        <div>
          <div className="success-msg">Password changed successfully!</div>
          <Link to="/login">
            <button type="button" className="btn-primary" style={{ marginTop: "1rem" }}>
              Go to login
            </button>
          </Link>
        </div>
      ) : step === "request" ? (
        <form onSubmit={handleRequestReset}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Sending..." : "Send reset token"}
          </button>
        </form>
      ) : (
        <form onSubmit={handleConfirmReset}>
          <div className="form-group">
            <label htmlFor="token">Reset token</label>
            <input
              id="token"
              type="text"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste the token from your email"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="newPassword">New password</label>
            <input
              id="newPassword"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Min 8 chars, upper + lower + digit"
              required
            />
          </div>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Resetting..." : "Reset password"}
          </button>
        </form>
      )}

      {step !== "done" && (
        <div className="auth-links">
          <Link to="/login">Back to sign in</Link>
        </div>
      )}
    </AuthLayout>
  );
}
