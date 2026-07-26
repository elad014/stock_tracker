import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";

import {
  AdminStock,
  AdminUser,
  assignStockToUser,
  createAdminStock,
  createAdminUser,
  deleteAdminStock,
  deleteAdminUser,
  fetchAdminStocks,
  fetchAdminUsers,
  removeStockFromUser,
  removeUserAdminRole,
  removeUserLock,
  setAdminUserPassword,
  updateAdminUser,
} from "../api/admin";

function formatCell(value: number | string | null): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "number") {
    return value.toFixed(2);
  }
  return String(value);
}

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail.map((item: { msg?: string }) => item.msg ?? "Invalid input").join(", ");
    }
  }
  return "Something went wrong";
}

export default function AdminPage(): JSX.Element {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [stocks, setStocks] = useState<AdminStock[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [pageError, setPageError] = useState<string>("");

  const [newUserName, setNewUserName] = useState<string>("");
  const [newUserEmail, setNewUserEmail] = useState<string>("");
  const [newUserPhone, setNewUserPhone] = useState<string>("");
  const [newUserPassword, setNewUserPassword] = useState<string>("");
  const [newUserAdmin, setNewUserAdmin] = useState<string>("");
  const [newUserLock, setNewUserLock] = useState<string>("");
  const [userFormError, setUserFormError] = useState<string>("");

  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editUserName, setEditUserName] = useState<string>("");
  const [editEmail, setEditEmail] = useState<string>("");
  const [editPhone, setEditPhone] = useState<string>("");
  const [editAdmin, setEditAdmin] = useState<string>("");
  const [editLock, setEditLock] = useState<string>("");
  const [editError, setEditError] = useState<string>("");

  const [passwordUserId, setPasswordUserId] = useState<string | null>(null);
  const [passwordUserLabel, setPasswordUserLabel] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [passwordError, setPasswordError] = useState<string>("");
  const [passwordSuccess, setPasswordSuccess] = useState<string>("");

  const [newStockName, setNewStockName] = useState<string>("");
  const [stockFormError, setStockFormError] = useState<string>("");

  const [assignStockByUser, setAssignStockByUser] = useState<Record<string, string>>({});
  const [assignErrorByUser, setAssignErrorByUser] = useState<Record<string, string>>({});

  async function loadAll(): Promise<void> {
    setLoading(true);
    setPageError("");
    try {
      const [usersData, stocksData] = await Promise.all([
        fetchAdminUsers(),
        fetchAdminStocks(),
      ]);
      setUsers(usersData);
      setStocks(stocksData);
    } catch (err: unknown) {
      setPageError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  async function handleCreateUser(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setUserFormError("");
    const adminValue: string = newUserAdmin.trim().toLowerCase();
    const lockValue: string = newUserLock.trim().toLowerCase();
    if (adminValue && adminValue !== "admin") {
      setUserFormError("Admin field must be empty or 'admin'");
      return;
    }
    if (lockValue && lockValue !== "lock") {
      setUserFormError("Lock field must be empty or code_lock");
      return;
    }
    try {
      await createAdminUser({
        user_name: newUserName.trim(),
        email: newUserEmail.trim(),
        phone_number: newUserPhone.trim(),
        password: newUserPassword,
        admin: adminValue || undefined,
        lock: lockValue || undefined,
      });
      setNewUserName("");
      setNewUserEmail("");
      setNewUserPhone("");
      setNewUserPassword("");
      setNewUserAdmin("");
      setNewUserLock("");
      await loadAll();
    } catch (err: unknown) {
      setUserFormError(errorMessage(err));
    }
  }

  function startEdit(user: AdminUser): void {
    setPasswordUserId(null);
    setEditingUserId(user.id);
    setEditUserName(user.user_name);
    setEditEmail(user.email);
    setEditPhone(user.phone_number);
    setEditAdmin("");
    setEditLock("");
    setEditError("");
  }

  function cancelEdit(): void {
    setEditingUserId(null);
    setEditError("");
  }

  async function handleSaveEdit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!editingUserId) {
      return;
    }
    setEditError("");
    const adminValue: string = editAdmin.trim().toLowerCase();
    const lockValue: string = editLock.trim().toLowerCase();
    if (adminValue && adminValue !== "admin") {
      setEditError("Admin field must be empty or admin_code");
      return;
    }
    if (lockValue && lockValue !== "lock") {
      setEditError("Lock field must be empty or code_lock");
      return;
    }
    try {
      const payload: {
        user_name: string;
        email: string;
        phone_number: string;
        admin?: string | null;
        lock?: string | null;
      } = {
        user_name: editUserName.trim(),
        email: editEmail.trim(),
        phone_number: editPhone.trim(),
      };
      if (adminValue) {
        payload.admin = adminValue;
      }
      if (lockValue) {
        payload.lock = lockValue;
      }
      await updateAdminUser(editingUserId, payload);
      setEditingUserId(null);
      await loadAll();
    } catch (err: unknown) {
      setEditError(errorMessage(err));
    }
  }

  function startSetPassword(user: AdminUser): void {
    setEditingUserId(null);
    setPasswordUserId(user.id);
    setPasswordUserLabel(user.user_name);
    setNewPassword("");
    setConfirmPassword("");
    setPasswordError("");
    setPasswordSuccess("");
  }

  function cancelSetPassword(): void {
    setPasswordUserId(null);
    setPasswordError("");
    setPasswordSuccess("");
  }

  async function handleSetPassword(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!passwordUserId) {
      return;
    }
    setPasswordError("");
    setPasswordSuccess("");

    if (newPassword.length < 8) {
      setPasswordError("Password must be at least 8 characters");
      return;
    }
    if (!/[A-Z]/.test(newPassword)) {
      setPasswordError("Password needs an uppercase letter");
      return;
    }
    if (!/[a-z]/.test(newPassword)) {
      setPasswordError("Password needs a lowercase letter");
      return;
    }
    if (!/\d/.test(newPassword)) {
      setPasswordError("Password needs a digit");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match");
      return;
    }

    try {
      const message = await setAdminUserPassword(passwordUserId, newPassword);
      setPasswordSuccess(message);
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      setPasswordError(errorMessage(err));
    }
  }

  async function handleDeleteUser(userId: string): Promise<void> {
    if (!window.confirm("Delete this user and their watchlist links?")) {
      return;
    }
    setPageError("");
    try {
      await deleteAdminUser(userId);
      if (editingUserId === userId) {
        setEditingUserId(null);
      }
      if (passwordUserId === userId) {
        setPasswordUserId(null);
      }
      await loadAll();
    } catch (err: unknown) {
      setPageError(errorMessage(err));
    }
  }

  async function handleRemoveAdmin(userId: string): Promise<void> {
    setPageError("");
    try {
      await removeUserAdminRole(userId);
      await loadAll();
    } catch (err: unknown) {
      setPageError(errorMessage(err));
    }
  }

  async function handleRemoveLock(userId: string): Promise<void> {
    setPageError("");
    try {
      await removeUserLock(userId);
      await loadAll();
    } catch (err: unknown) {
      setPageError(errorMessage(err));
    }
  }

  async function handleCreateStock(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setStockFormError("");
    try {
      await createAdminStock(newStockName.trim());
      setNewStockName("");
      await loadAll();
    } catch (err: unknown) {
      setStockFormError(errorMessage(err));
    }
  }

  async function handleDeleteStock(stockId: string): Promise<void> {
    if (!window.confirm("Delete this stock and remove it from all watchlists?")) {
      return;
    }
    setPageError("");
    try {
      await deleteAdminStock(stockId);
      await loadAll();
    } catch (err: unknown) {
      setPageError(errorMessage(err));
    }
  }

  async function handleAssignStock(userId: string): Promise<void> {
    const stockId = assignStockByUser[userId] ?? "";
    if (!stockId) {
      setAssignErrorByUser((prev) => ({ ...prev, [userId]: "Select a stock" }));
      return;
    }
    setAssignErrorByUser((prev) => ({ ...prev, [userId]: "" }));
    try {
      await assignStockToUser(userId, stockId);
      setAssignStockByUser((prev) => ({ ...prev, [userId]: "" }));
      await loadAll();
    } catch (err: unknown) {
      setAssignErrorByUser((prev) => ({ ...prev, [userId]: errorMessage(err) }));
    }
  }

  async function handleRemoveUserStock(userId: string, stockId: string): Promise<void> {
    setAssignErrorByUser((prev) => ({ ...prev, [userId]: "" }));
    try {
      await removeStockFromUser(userId, stockId);
      await loadAll();
    } catch (err: unknown) {
      setAssignErrorByUser((prev) => ({ ...prev, [userId]: errorMessage(err) }));
    }
  }

  function availableStocksForUser(user: AdminUser): AdminStock[] {
    const followedIds = new Set(user.followed_stocks.map((s: AdminStock) => s.id));
    return stocks.filter((stock: AdminStock) => !followedIds.has(stock.id));
  }

  return (
    <div className="admin-page">
      <header className="admin-header">
        <span className="admin-logo">Stock Tracker Admin</span>
        <Link to="/dashboard" className="btn-outline">
          Back to dashboard
        </Link>
      </header>

      <main className="admin-main">
        {pageError ? <p className="admin-error">{pageError}</p> : null}
        {loading ? <p className="admin-subtitle">Loading…</p> : null}

        <section className="admin-panel">
          <h1>Users</h1>
          <p className="admin-subtitle">Add, edit, or delete users and manage their stocks</p>

          <form className="admin-form" onSubmit={handleCreateUser}>
            <input
              type="text"
              placeholder="Username"
              value={newUserName}
              onChange={(e) => setNewUserName(e.target.value)}
              required
            />
            <input
              type="email"
              placeholder="Email"
              value={newUserEmail}
              onChange={(e) => setNewUserEmail(e.target.value)}
              required
            />
            <input
              type="text"
              placeholder="Phone"
              value={newUserPhone}
              onChange={(e) => setNewUserPhone(e.target.value)}
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={newUserPassword}
              onChange={(e) => setNewUserPassword(e.target.value)}
              required
            />
            <input
              type="text"
              placeholder="Role"
              value={newUserAdmin}
              onChange={(e) => setNewUserAdmin(e.target.value)}
              autoComplete="off"
            />
            <input
              type="text"
              placeholder="Status"
              value={newUserLock}
              onChange={(e) => setNewUserLock(e.target.value)}
              autoComplete="off"
            />
            <button type="submit" className="btn-primary">
              Add user
            </button>
          </form>
          {userFormError ? <p className="admin-error">{userFormError}</p> : null}

          <div className="table-wrap">
            <table className="stocks-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Followed stocks</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user: AdminUser) => (
                  <tr key={user.id}>
                    <td>{user.user_name}</td>
                    <td>{user.email}</td>
                    <td>{user.phone_number}</td>
                    <td>{user.admin === "admin" ? "admin" : "user"}</td>
                    <td>{user.lock === "lock" ? "locked" : "active"}</td>
                    <td>
                      <div className="admin-stock-tags">
                        {user.followed_stocks.length === 0 ? (
                          <span>—</span>
                        ) : (
                          user.followed_stocks.map((stock: AdminStock) => (
                            <span key={stock.id} className="admin-stock-tag">
                              {stock.name}
                              <button
                                type="button"
                                className="admin-inline-btn"
                                onClick={() => void handleRemoveUserStock(user.id, stock.id)}
                              >
                                Remove
                              </button>
                            </span>
                          ))
                        )}
                      </div>
                      <div className="admin-inline-row">
                        <select
                          value={assignStockByUser[user.id] ?? ""}
                          onChange={(e) =>
                            setAssignStockByUser((prev) => ({
                              ...prev,
                              [user.id]: e.target.value,
                            }))
                          }
                        >
                          <option value="">Add stock…</option>
                          {availableStocksForUser(user).map((stock: AdminStock) => (
                            <option key={stock.id} value={stock.id}>
                              {stock.name}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="btn-primary admin-btn-sm"
                          onClick={() => void handleAssignStock(user.id)}
                        >
                          Assign
                        </button>
                      </div>
                      {assignErrorByUser[user.id] ? (
                        <p className="admin-error">{assignErrorByUser[user.id]}</p>
                      ) : null}
                    </td>
                    <td>
                      <div className="admin-actions">
                        <button
                          type="button"
                          className="btn-outline admin-btn-sm"
                          onClick={() => startEdit(user)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="btn-outline admin-btn-sm"
                          onClick={() => startSetPassword(user)}
                        >
                          Set password
                        </button>
                        {user.admin === "admin" ? (
                          <button
                            type="button"
                            className="btn-outline admin-btn-sm"
                            onClick={() => void handleRemoveAdmin(user.id)}
                          >
                            Remove admin
                          </button>
                        ) : null}
                        {user.lock === "lock" ? (
                          <button
                            type="button"
                            className="btn-outline admin-btn-sm"
                            onClick={() => void handleRemoveLock(user.id)}
                          >
                            Remove lock
                          </button>
                        ) : null}
                        <button
                          type="button"
                          className="btn-outline admin-btn-sm"
                          onClick={() => void handleDeleteUser(user.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {editingUserId ? (
            <form className="admin-form admin-edit-form" onSubmit={handleSaveEdit}>
              <h2>Edit user</h2>
              <input
                type="text"
                placeholder="Username"
                value={editUserName}
                onChange={(e) => setEditUserName(e.target.value)}
                required
              />
              <input
                type="email"
                placeholder="Email"
                value={editEmail}
                onChange={(e) => setEditEmail(e.target.value)}
                required
              />
              <input
                type="text"
                placeholder="Phone"
                value={editPhone}
                onChange={(e) => setEditPhone(e.target.value)}
                required
              />
              <input
                type="text"
                placeholder="Role"
                value={editAdmin}
                onChange={(e) => setEditAdmin(e.target.value)}
                autoComplete="off"
              />
              <input
                type="text"
                placeholder="Status"
                value={editLock}
                onChange={(e) => setEditLock(e.target.value)}
                autoComplete="off"
              />
              <div className="admin-actions">
                <button type="submit" className="btn-primary">
                  Save
                </button>
                <button type="button" className="btn-outline" onClick={cancelEdit}>
                  Cancel
                </button>
              </div>
              {editError ? <p className="admin-error">{editError}</p> : null}
            </form>
          ) : null}

          {passwordUserId ? (
            <form className="admin-form admin-edit-form" onSubmit={handleSetPassword}>
              <h2>Set password for {passwordUserLabel}</h2>
              <p className="admin-subtitle">
                Current password is not required. Enter a new password only.
              </p>
              <input
                type="password"
                placeholder="New password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
              <input
                type="password"
                placeholder="Confirm new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
              <div className="admin-actions">
                <button type="submit" className="btn-primary">
                  Update password
                </button>
                <button type="button" className="btn-outline" onClick={cancelSetPassword}>
                  Cancel
                </button>
              </div>
              {passwordError ? <p className="admin-error">{passwordError}</p> : null}
              {passwordSuccess ? <p className="success-msg">{passwordSuccess}</p> : null}
            </form>
          ) : null}
        </section>

        <section className="admin-panel">
          <h1>Stocks</h1>
          <p className="admin-subtitle">Add or remove stocks in the catalog</p>

          <form className="admin-form" onSubmit={handleCreateStock}>
            <input
              type="text"
              placeholder="Ticker (e.g. AAPL)"
              value={newStockName}
              onChange={(e) => setNewStockName(e.target.value.toUpperCase())}
              required
            />
            <button type="submit" className="btn-primary">
              Add stock
            </button>
          </form>
          {stockFormError ? <p className="admin-error">{stockFormError}</p> : null}

          <div className="table-wrap">
            <table className="stocks-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Price</th>
                  <th>Trend</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {stocks.map((stock: AdminStock) => (
                  <tr key={stock.id}>
                    <td className="symbol-cell">{stock.name}</td>
                    <td>{formatCell(stock.price)}</td>
                    <td>{formatCell(stock.trend)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn-outline admin-btn-sm"
                        onClick={() => void handleDeleteStock(stock.id)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}
