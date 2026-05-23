import React, { useEffect, useState } from 'react'
import AppLayout from '../../components/layout/AppLayout'
import { userAPI } from '../../services/api'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export default function AdminUsers() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const load = () => {
    userAPI.getAll(0, 200)
      .then(r => setUsers(r.data || []))
      .catch(() => toast.error('Failed to load users'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleToggleActive = async (user) => {
    try {
      await userAPI.update(user.id, { is_active: !user.is_active })
      setUsers(us => us.map(u => u.id === user.id ? { ...u, is_active: !u.is_active } : u))
      toast.success(`User ${!user.is_active ? 'activated' : 'deactivated'}`)
    } catch {
      toast.error('Failed to update user')
    }
  }

  const handleDelete = async (user) => {
    if (!window.confirm(`Delete user "${user.full_name}"? This cannot be undone.`)) return
    try {
      await userAPI.delete(user.id)
      setUsers(us => us.filter(u => u.id !== user.id))
      toast.success('User deleted')
    } catch {
      toast.error('Failed to delete user')
    }
  }

  const filtered = users.filter(u =>
    !search || u.full_name?.toLowerCase().includes(search.toLowerCase()) || u.email?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <AppLayout>
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Users</h1>
            <p className="text-slate-400 text-sm mt-0.5">{users.length} registered account{users.length !== 1 ? 's' : ''}</p>
          </div>
          <input
            type="text"
            className="input-field max-w-xs"
            placeholder="Search by name or email…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="glass-card p-16 text-center">
            <div className="text-5xl mb-4">◉</div>
            <h3 className="text-lg font-semibold text-white mb-2">
              {search ? 'No results found' : 'No users yet'}
            </h3>
            <p className="text-slate-400">{search ? 'Try a different search term.' : 'Users will appear here after they register.'}</p>
          </div>
        ) : (
          <div className="glass-card overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-800">
                  {['Name', 'Email', 'Role', 'Status', 'Joined', 'Actions'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filtered.map(user => (
                  <tr key={user.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-brand-600/30 rounded-full flex items-center justify-center text-brand-400 text-sm font-bold flex-shrink-0">
                          {user.full_name?.[0]?.toUpperCase() || '?'}
                        </div>
                        <span className="font-medium text-white text-sm">{user.full_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-slate-400 text-sm">{user.email}</td>
                    <td className="px-4 py-4">
                      <span className={user.role === 'admin' ? 'badge-blue' : 'badge-gray'}>
                        {user.role}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <span className={user.is_active ? 'badge-green' : 'badge-red'}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-slate-500 text-xs">
                      {user.created_at ? new Date(user.created_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => handleToggleActive(user)}
                          className={clsx(
                            'text-sm font-medium transition-colors',
                            user.is_active ? 'text-amber-500 hover:text-amber-400' : 'text-emerald-500 hover:text-emerald-400'
                          )}
                        >
                          {user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                        <button
                          onClick={() => handleDelete(user)}
                          className="text-red-500 hover:text-red-400 text-sm font-medium transition-colors"
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
        )}
      </div>
    </AppLayout>
  )
}
