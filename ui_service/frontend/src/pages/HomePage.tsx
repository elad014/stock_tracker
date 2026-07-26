import { Link } from "react-router-dom";

export default function HomePage(): JSX.Element {
  return (
    <div className="home-page">
      <nav className="home-nav">
        <span className="home-logo">Stock Tracker</span>
        <div className="home-nav-actions">
          <Link to="/admin" className="btn-outline">Admin</Link>
          <Link to="/help" className="btn-outline">Help</Link>
          <Link to="/login" className="btn-outline">Log in</Link>
          <Link to="/register" className="btn-solid">Sign up</Link>
        </div>
      </nav>

      <main className="home-hero">
        <div className="home-hero-content">
          <h1>Track your investments<br />with confidence</h1>
          <p>
            Monitor real-time stock data, build your portfolio, and get
            AI-powered insights — all in one place.
          </p>
          <div className="home-hero-actions">
            <Link to="/register" className="btn-solid btn-large">Get started</Link>
            <Link to="/login" className="btn-outline btn-large">Log in</Link>
          </div>
        </div>

        <div className="home-features">
          <div className="feature-card">
            <h3>Real-time Data</h3>
            <p>Live stock prices, indices, and crypto updated throughout the trading day.</p>
          </div>
          <div className="feature-card">
            <h3>Portfolio Tracking</h3>
            <p>Build and manage your personal portfolio with detailed performance metrics.</p>
          </div>
          <div className="feature-card">
            <h3>AI Insights</h3>
            <p>Get smart analysis and recommendations powered by artificial intelligence.</p>
          </div>
        </div>
      </main>

      <footer className="home-footer">
        <p>Stock Tracker &mdash; Your personal investment companion</p>
      </footer>
    </div>
  );
}
