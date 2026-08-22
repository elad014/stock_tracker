import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { loginUser } from "../../services/authService";
import AuthLayout from "../components/AuthLayout";

export default function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const data = await loginUser({ email, password });
      localStorage.setItem("access_token", data.access_token);
      navigate("/dashboard");
    } catch (err: any) {
      const msg = err.response?.data?.detail ?? "Login failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to your Stock Tracker account"
    >
      {error && <div className="error-msg">{error}</div>}

      <form onSubmit={handleSubmit}>
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

        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            required
          />
        </div>

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>

      <div className="auth-links">
        <Link to="/forgot-password">Forgot password?</Link>
        <span className="auth-links-sep">|</span>
        <Link to="/register">Create account</Link>
      </div>
    </AuthLayout>
  );
}
