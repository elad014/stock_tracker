import { Link } from "react-router-dom";

import HomeNav from "../components/HomeNav";

export default function HelpPage(): JSX.Element {
  return (
    <div className="help-page">
      <HomeNav />

      <main className="help-content">
        <h1>Help</h1>
        <p className="help-intro">
          Stock Tracker helps you monitor investments, manage a portfolio, and
          get AI-powered insights. Here is how to get started.
        </p>

        <section className="help-section">
          <h2>Getting started</h2>
          <ol>
            <li>Create an account with the Sign up button on the home page.</li>
            <li>Sign in with your email and password.</li>
            <li>Build your portfolio and track stocks, indices, and crypto.</li>
          </ol>
        </section>

        <section className="help-section">
          <h2>Account</h2>
          <ul>
            <li>
              <strong>Register</strong> — create a new account with username, email,
              phone, and password.
            </li>
            <li>
              <strong>Log in</strong> — sign in with your email and password.
            </li>
            <li>
              <strong>Forgot password</strong> — request a reset token by email,
              then set a new password.
            </li>
          </ul>
        </section>

        <section className="help-section">
          <h2>What you can do</h2>
          <ul>
            <li>Track real-time stock, index, and crypto data.</li>
            <li>Manage a personal investment portfolio.</li>
            <li>Follow financial news related to your assets.</li>
            <li>Receive AI-based analysis and notifications.</li>
          </ul>
        </section>

        <section className="help-section">
          <h2>Important note</h2>
          <p>
            Stock Tracker is not an investment advisory service. It helps you
            understand market data through tracking, alerts, and AI analysis.
          </p>
        </section>

        <div className="help-actions">
          <Link to="/register" className="btn-solid btn-large">Create account</Link>
          <Link to="/login" className="btn-outline btn-large">Log in</Link>
        </div>
      </main>
    </div>
  );
}
