import { Link } from "react-router-dom";

export default function HomeNav(): JSX.Element {
  return (
    <nav className="home-nav">
      <Link to="/" className="home-logo">
        Stock Tracker
      </Link>
      <div className="home-nav-actions">
        <Link to="/help" className="btn-outline">
          Help
        </Link>
        <Link to="/login" className="btn-outline">
          Log in
        </Link>
        <Link to="/register" className="btn-solid">
          Sign up
        </Link>
      </div>
    </nav>
  );
}
