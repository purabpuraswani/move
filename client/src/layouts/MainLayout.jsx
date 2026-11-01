import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import {
  LayoutDashboard, Activity, Clipboard, Stethoscope, Apple, Brain,
  Moon, Dumbbell, TrendingUp, User, ChevronRight, LogOut, Menu,
  Heart, PlayCircle
} from 'lucide-react';

const navItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/plan', icon: Clipboard, label: 'My Plan' },
  { path: '/assessment', icon: Activity, label: 'Assessment' },
  { label: 'SPECIALISTS', isHeader: true },
  { path: '/specialists/physiotherapy', icon: Stethoscope, label: 'Physiotherapy' },
  { path: '/specialists/nutrition', icon: Apple, label: 'Nutrition' },
  { path: '/specialists/behaviour', icon: Brain, label: 'Behaviour' },
  { path: '/specialists/recovery', icon: Moon, label: 'Wellness & Recovery' },
  { path: '/specialists/activity', icon: Dumbbell, label: 'Exercise & Activity' },
  { path: '/progress', icon: TrendingUp, label: 'Progress' },
];

function SidebarContent({ onLinkClick }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="p-6 border-b border-emerald-900/30">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-emerald-500 rounded-lg flex items-center justify-center">
            <Heart size={18} className="text-white" />
          </div>
          <div>
            <div className="text-white font-bold text-sm">MoveWell AI</div>
            <div className="text-emerald-400 text-xs">AI-Guided Protocol</div>
          </div>
        </div>
      </div>

      {/* Run Assessment CTA */}
      <div className="p-4">
        <Link
          to="/assessment"
          onClick={onLinkClick}
          className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-3 py-2.5 text-emerald-400 text-sm hover:bg-emerald-500/20 transition-colors w-full"
        >
          <PlayCircle size={16} />
          <span>Start Assessment</span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 pb-4 overflow-y-auto">
        {navItems.map((item, i) => {
          if (item.isHeader) {
            return (
              <div key={i} className="text-xs text-emerald-700 font-semibold uppercase tracking-wider px-3 py-2 mt-4">
                {item.label}
              </div>
            );
          }
          const isActive = location.pathname === item.path;
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              to={item.path}
              onClick={onLinkClick}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 text-sm transition-colors ${
                isActive
                  ? 'bg-emerald-500/15 text-emerald-400 border-l-2 border-emerald-500'
                  : 'text-emerald-100/60 hover:text-emerald-100 hover:bg-white/5'
              }`}
            >
              <Icon size={16} />
              <span>{item.label}</span>
              {isActive && <ChevronRight size={12} className="ml-auto" />}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="p-4 border-t border-emerald-900/30">
        <Link
          to="/profile"
          onClick={onLinkClick}
          className="flex items-center gap-3 mb-3 hover:bg-white/5 rounded-lg p-2 transition-colors"
        >
          <div className="w-8 h-8 bg-emerald-500/20 rounded-full flex items-center justify-center">
            <User size={14} className="text-emerald-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-white truncate">{user?.name}</div>
            <div className="text-xs text-emerald-600 truncate">{user?.email}</div>
          </div>
        </Link>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-xs text-red-400/70 hover:text-red-400 transition-colors px-2"
        >
          <LogOut size={12} />
          <span>Sign Out</span>
        </button>
      </div>
    </div>
  );
}

export default function MainLayout({ children }) {
  const { user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen bg-[#0a0f0a] overflow-hidden">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex w-64 flex-shrink-0 bg-[#0d1a0d] border-r border-emerald-900/30 flex-col">
        <SidebarContent onLinkClick={undefined} />
      </div>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="w-64 bg-[#0d1a0d] border-r border-emerald-900/30 flex flex-col">
            <SidebarContent onLinkClick={() => setSidebarOpen(false)} />
          </div>
          <div className="flex-1 bg-black/50" onClick={() => setSidebarOpen(false)} />
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <div className="h-14 bg-[#0d1a0d] border-b border-emerald-900/30 flex items-center px-4 md:px-6 gap-4 flex-shrink-0">
          <button
            className="md:hidden text-emerald-400 hover:text-emerald-300 transition-colors"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={20} />
          </button>
          <div className="flex-1" />
          <div className="text-xs text-emerald-600 hidden sm:block">
            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
          </div>
          <Link to="/profile" className="w-8 h-8 bg-emerald-500/20 rounded-full flex items-center justify-center text-emerald-400 text-xs font-bold hover:bg-emerald-500/30 transition-colors">
            {user?.name?.[0]?.toUpperCase() ?? 'U'}
          </Link>
        </div>

        {/* Page Content */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
}
