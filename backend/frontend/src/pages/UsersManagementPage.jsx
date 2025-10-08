import React, { useEffect, useMemo, useState } from "react";

/**
 * Admin Users Management Page
 * - Lists users grouped by role (via /api/accounts/user-roles/)
 * - Create user (username, password, role, optional profile fields)
 * - Change role for an existing user
 * - Reset password for an existing user
 * - Deactivate (soft-remove) user by setting is_active = false
 *
 * Requirements this page relies on the backend to provide these endpoints:
 *   POST   /api/accounts/register/                                 (Admin only)
 *   GET    /api/accounts/user-roles/                               (Admin only)
 *   POST   /api/accounts/user-roles/:user_id/                      (Admin only; body: { role_name })
 *   POST   /api/accounts/users/reset-password/                     (Admin only; body: { user_id, new_password })
 *   PUT    /api/accounts/users/update/:user_id/                    (Admin/Coordinator or self)
 *   GET    /api/accounts/roles/                                    (Admin only)  [for role dropdown]
 *
 * Auth: assumes an access token is stored in localStorage under key `accessToken`.
 * Styling: TailwindCSS
 */

const API_BASE = "/api/accounts"; // change if you mounted under a different prefix

function useAuthHeaders() {
    const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
    return useMemo(
        () => ({
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        }),
        [token]
    );
}

function Section({ title, children, actions }) {
    return (
        <div className="bg-white rounded-2xl shadow p-5 border border-gray-100">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">{title}</h2>
                {actions}
            </div>
            {children}
        </div>
    );
}

export default function UsersManagementPage() {
    const headers = useAuthHeaders();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [roles, setRoles] = useState([]); // [{id, role_name}]
    const [rows, setRows] = useState([]); // from /user-roles/ [{id, user, role, user_username, user_name, role_name, ...}]

    // Create user form state
    const [newUser, setNewUser] = useState({
        username: "",
        password: "",
        role_name: "Tutor",
        email: "",
        first_name: "",
        last_name: "",
    });

    // Load roles + users
    async function loadAll() {
        setLoading(true);
        setError("");
        try {
            const [rolesRes, usersRes] = await Promise.all([
                fetch(`${API_BASE}/roles/`, { headers }),
                fetch(`${API_BASE}/user-roles/`, { headers }),
            ]);
            if (!rolesRes.ok) throw new Error("Failed to load roles");
            if (!usersRes.ok) throw new Error("Failed to load users");
            const rolesData = await rolesRes.json();
            const usersData = await usersRes.json();
            setRoles(rolesData);
            setRows(usersData);
        } catch (e) {
            setError(e.message || "Failed to load data");
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        loadAll();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const grouped = useMemo(() => {
        const m = new Map();
        for (const r of rows) {
            const key = r.role_name || "(No Role)";
            if (!m.has(key)) m.set(key, []);
            m.get(key).push(r);
        }
        return Array.from(m.entries()).sort((a, b) => a[0].localeCompare(b[0]));
    }, [rows]);

    async function handleCreateUser(e) {
        e.preventDefault();
        setError("");
        try {
            const res = await fetch(`${API_BASE}/register/`, {
                method: "POST",
                headers,
                body: JSON.stringify(newUser),
            });
            if (!res.ok) {
                const j = await res.json().catch(() => ({}));
                throw new Error(j?.error || "Failed to create user");
            }
            setNewUser({ username: "", password: "", role_name: "Tutor", email: "", first_name: "", last_name: "" });
            await loadAll();
        } catch (e) {
            setError(e.message || "Create failed");
        }
    }

    async function handleChangeRole(userId, roleName) {
        try {
            const res = await fetch(`${API_BASE}/user-roles/${userId}/`, {
                method: "POST",
                headers,
                body: JSON.stringify({ role_name: roleName }),
            });
            if (!res.ok) throw new Error("Failed to update role");
            await loadAll();
        } catch (e) {
            setError(e.message || "Role update failed");
        }
    }

    async function handleResetPassword(userId) {
        const pwd = prompt("Enter a new password for this user:");
        if (!pwd) return;
        try {
            const res = await fetch(`${API_BASE}/users/reset-password/`, {
                method: "POST",
                headers,
                body: JSON.stringify({ user_id: userId, new_password: pwd }),
            });
            if (!res.ok) throw new Error("Failed to reset password");
            alert("Password updated");
        } catch (e) {
            setError(e.message || "Password reset failed");
        }
    }

    async function handleDeactivate(userId) {
        if (!confirm("Deactivate this user? They will not be able to sign in.")) return;
        try {
            const res = await fetch(`${API_BASE}/users/update/${userId}/`, {
                method: "PUT",
                headers,
                body: JSON.stringify({ is_active: false }),
            });
            if (!res.ok) throw new Error("Failed to deactivate user");
            await loadAll();
        } catch (e) {
            setError(e.message || "Deactivate failed");
        }
    }

    return (
        <div className="max-w-7xl mx-auto p-6 space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold">Users Management</h1>
                <button
                    onClick={loadAll}
                    className="px-4 py-2 rounded-xl border border-gray-200 hover:bg-gray-50"
                >
                    Refresh
                </button>
            </div>

            {error && (
                <div className="rounded-xl bg-red-50 border border-red-200 text-red-700 p-3">{error}</div>
            )}

            <Section title="Create New User">
                <form onSubmit={handleCreateUser} className="grid md:grid-cols-3 gap-4">
                    <div>
                        <label className="block text-sm mb-1">Username</label>
                        <input
                            className="w-full rounded-xl border p-2"
                            value={newUser.username}
                            onChange={(e) => setNewUser((s) => ({ ...s, username: e.target.value }))}
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-sm mb-1">Password</label>
                        <input
                            type="password"
                            className="w-full rounded-xl border p-2"
                            value={newUser.password}
                            onChange={(e) => setNewUser((s) => ({ ...s, password: e.target.value }))}
                            required
                            minLength={8}
                        />
                    </div>
                    <div>
                        <label className="block text-sm mb-1">Role</label>
                        <select
                            className="w-full rounded-xl border p-2"
                            value={newUser.role_name}
                            onChange={(e) => setNewUser((s) => ({ ...s, role_name: e.target.value }))}
                        >
                            {roles?.map((r) => (
                                <option key={r.id} value={r.role_name}>{r.role_name}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm mb-1">First name</label>
                        <input className="w-full rounded-xl border p-2" value={newUser.first_name} onChange={(e) => setNewUser((s) => ({ ...s, first_name: e.target.value }))} />
                    </div>
                    <div>
                        <label className="block text-sm mb-1">Last name</label>
                        <input className="w-full rounded-xl border p-2" value={newUser.last_name} onChange={(e) => setNewUser((s) => ({ ...s, last_name: e.target.value }))} />
                    </div>
                    <div>
                        <label className="block text-sm mb-1">Email (optional)</label>
                        <input className="w-full rounded-xl border p-2" type="email" value={newUser.email} onChange={(e) => setNewUser((s) => ({ ...s, email: e.target.value }))} />
                    </div>
                    <div className="md:col-span-3">
                        <button className="px-4 py-2 rounded-xl bg-black text-white hover:opacity-90">Create User</button>
                    </div>
                </form>
            </Section>

            <Section title="Users by Role">
                {loading ? (
                    <div className="text-gray-500">Loading…</div>
                ) : (
                    <div className="space-y-6">
                        {grouped.map(([roleName, items]) => (
                            <div key={roleName} className="border rounded-2xl p-4">
                                <div className="flex items-center justify-between mb-3">
                                    <h3 className="font-semibold">{roleName} ({items.length})</h3>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="min-w-full text-sm">
                                        <thead>
                                            <tr className="text-left text-gray-500">
                                                <th className="py-2 pr-4">Username</th>
                                                <th className="py-2 pr-4">Name</th>
                                                <th className="py-2 pr-4">Role</th>
                                                <th className="py-2 pr-4">Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {items.map((r) => (
                                                <tr key={r.id} className="border-t">
                                                    <td className="py-2 pr-4 font-mono">{r.user_username}</td>
                                                    <td className="py-2 pr-4">{r.user_name || "—"}</td>
                                                    <td className="py-2 pr-4">
                                                        <select
                                                            className="rounded-lg border p-1"
                                                            value={r.role_name}
                                                            onChange={(e) => handleChangeRole(r.user, e.target.value)}
                                                        >
                                                            {roles?.map((opt) => (
                                                                <option key={opt.id} value={opt.role_name}>{opt.role_name}</option>
                                                            ))}
                                                        </select>
                                                    </td>
                                                    <td className="py-2 pr-4 space-x-2">
                                                        <button className="px-3 py-1 rounded-lg border hover:bg-gray-50" onClick={() => handleResetPassword(r.user)}>Reset password</button>
                                                        <button className="px-3 py-1 rounded-lg border hover:bg-red-50" onClick={() => handleDeactivate(r.user)}>Deactivate</button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ))}
                        {grouped.length === 0 && (
                            <div className="text-gray-500">No users found.</div>
                        )}
                    </div>
                )}
            </Section>
        </div>
    );
}
