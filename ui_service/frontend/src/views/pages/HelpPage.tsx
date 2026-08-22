import { Link } from "react-router-dom";

import HomeNav from "../components/HomeNav";

export default function HelpPage(): JSX.Element {
  return (
    <div className="help-page">
      <HomeNav />

      <main className="help-content">
        <h1>Help</h1>
        <p className="help-intro">
          Stock Tracker is a watchlist, news, and document workspace with an
          AI assistant. Sign in to follow tickers, upload PDFs, and ask
          questions about your stocks and files.
        </p>

        <section className="help-section">
          <h2>Getting started</h2>
          <ol>
            <li>Create an account with Sign up on the home page.</li>
            <li>Sign in with your email and password.</li>
            <li>Add tickers to your watchlist on the dashboard.</li>
            <li>Open a stock for charts, market data, and news.</li>
            <li>Upload PDFs and use Chat to ask about your files or watchlist.</li>
          </ol>
        </section>

        <section className="help-section">
          <h2>Account</h2>
          <ul>
            <li>
              <strong>Register</strong> — username (at least 3 characters),
              email, phone, and password. The password needs at least 8
              characters, one uppercase letter, one lowercase letter, and one
              digit.
            </li>
            <li>
              <strong>Log in</strong> — sign in with your email and password.
              Locked accounts cannot sign in.
            </li>
            <li>
              <strong>Forgot password</strong> — request a reset email, then
              enter the token and a new password. The token expires in 15
              minutes.
            </li>
            <li>
              <strong>Settings</strong> — after you sign in, update your
              username, email, phone, or password. Changing your password
              requires the current one.
            </li>
          </ul>
        </section>

        <section className="help-section">
          <h2>Watchlist</h2>
          <p>
            The dashboard lists the stocks you follow with current price and
            daily change. Add a ticker such as AAPL or BRK.A, or remove one
            from the dropdown. Click a row to open that stock.
          </p>
          <p>
            Home-page charts are an illustrative snapshot. Signed-in quotes
            and history come from market data for the tickers on your
            watchlist.
          </p>
        </section>

        <section className="help-section">
          <h2>Stock details</h2>
          <ul>
            <li>Price, daily change, and percent change.</li>
            <li>
              History chart for 1D, 5D, 1M, 3M, 6M, 1Y, and 5Y.
            </li>
            <li>
              Market data: open, previous close, day high and low, volume,
              and 52-week high and low.
            </li>
            <li>
              An AI news summary for the stock when one is available.
            </li>
            <li>
              Latest articles with source and date. Use Summarize article to
              generate an AI summary for that story.
            </li>
          </ul>
          <p>
            You can only open stocks that are on your watchlist.
          </p>
        </section>

        <section className="help-section">
          <h2>Documents</h2>
          <p>
            Upload PDFs to the dashboard document tree. Create folders, move
            files into a folder, open a file to download it, or delete a file
            or empty folder.
          </p>
          <ul>
            <li>PDF files only, up to 20 MB each.</li>
            <li>Up to 10 files per account.</li>
            <li>
              Up to 20 document indexes per rolling 7-day window. Deleting a
              file does not reset that weekly count.
            </li>
            <li>Download links expire after 5 minutes.</li>
          </ul>
        </section>

        <section className="help-section">
          <h2>News</h2>
          <p>
            The dashboard News panel shows one headline summary per followed
            stock when a summary is ready. Open a stock for the full article
            list and per-article summaries.
          </p>
        </section>

        <section className="help-section">
          <h2>Chat</h2>
          <p>
            Open Chat on the dashboard to ask about your watchlist, news, or
            uploaded documents. Opening a PDF first focuses the question on
            that file; otherwise the assistant can search all of your
            documents.
          </p>
        </section>

        <section className="help-section">
          <h2>Admin</h2>
          <p>
            Admin accounts can open Admin from the dashboard to create and
            edit users, lock or unlock accounts, assign or remove watchlist
            stocks, and delete users or stocks. Deleting a user also removes
            that account&apos;s documents and indexed files.
          </p>
        </section>

        <section className="help-section">
          <h2>Contact</h2>
          <p>
            For questions, contact us at{" "}
            <a href="mailto:elad.glx@gmail.com">elad.glx@gmail.com</a>.
          </p>
        </section>

        <section className="help-section">
          <h2>Important note</h2>
          <p>
            Stock Tracker is not an investment advisory service. It helps you
            follow market data, news, and your own documents. AI answers can
            be incomplete or wrong. Do not treat them as financial advice.
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
