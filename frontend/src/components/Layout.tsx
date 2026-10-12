import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import { Home, Activity } from 'lucide-react';

export const Layout: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col text-slate-100">
      <header className="glass sticky top-0 z-50 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2 text-white">
            <Activity className="h-6 w-6 text-primary-500" />
            <h1 className="text-xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-primary-500 to-primary-100">VyaparFlow AI</h1>
          </div>
          <nav className="flex gap-6">
            <Link to="/" className="flex items-center gap-1.5 text-slate-300 hover:text-white transition-all duration-300 hover:scale-105">
              <Home className="h-4 w-4" />
              <span className="hidden sm:inline font-medium text-sm">Dashboard</span>
            </Link>
            <Link to="/workflows" className="flex items-center gap-1.5 text-slate-300 hover:text-white transition-all duration-300 hover:scale-105">
              <Activity className="h-4 w-4" />
              <span className="hidden sm:inline font-medium text-sm">Workflows</span>
            </Link>
            <Link to="/eval" className="flex items-center gap-1.5 text-slate-300 hover:text-white transition-all duration-300 hover:scale-105">
              <Activity className="h-4 w-4" />
              <span className="hidden sm:inline font-medium text-sm">Evaluation</span>
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-in fade-in duration-500">
        <Outlet />
      </main>

      <footer className="glass py-4 text-center text-sm text-slate-400 mt-auto">
        <p>VyaparFlow AI - Local-First Worker Prototype</p>
      </footer>
    </div>
  );
};
