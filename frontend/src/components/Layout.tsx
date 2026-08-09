import { NavLink, Outlet } from 'react-router-dom'
import { cn } from '../lib/utils'

const navItems = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/execucoes', label: 'Execuções', icon: '🎬' },
  { to: '/revisao', label: 'Revisão Manual', icon: '✏️' },
  { to: '/ideias-manuais', label: 'Ideias Manuais', icon: '💡' },
  { to: '/gameplay', label: 'Gameplay', icon: '🎮' },
  { to: '/nichos', label: 'Nichos', icon: '📁' },
]

export default function Layout() {
  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-card">
        <div className="p-6 border-b border-border">
          <h1 className="text-xl font-bold">Faceless Pipeline</h1>
          <p className="text-sm text-muted-foreground mt-1">Gestão de Vídeos</p>
        </div>
        <nav className="p-4">
          <ul className="space-y-2">
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 px-4 py-2 rounded-md text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                    )
                  }
                >
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="container mx-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
