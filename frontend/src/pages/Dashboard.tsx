import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { workflowApi } from '../services/api';
import type { DashboardStats } from '../types';
import { Camera, Upload, CheckCircle, AlertTriangle, Clock, FileText, Server, Database, ShieldAlert, Cpu } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const data = await workflowApi.getDashboardStats();
      setStats(data);
    } catch (error) {
      console.error("Failed to fetch dashboard stats", error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      try {
        const workflow = await workflowApi.uploadImage(file);
        navigate(`/workflow/${workflow.id}`);
      } catch (error) {
        console.error("Upload failed", error);
        alert("Failed to upload image.");
      }
    }
  };

  const handleDemoUpload = async (filename: string) => {
    try {
      const response = await fetch(`http://localhost:8000/uploads/${filename}`);
      if (!response.ok) throw new Error("File not found");
      const blob = await response.blob();
      const file = new File([blob], filename, { type: 'image/jpeg' });
      const workflow = await workflowApi.uploadImage(file);
      navigate(`/workflow/${workflow.id}`);
    } catch (error) {
      console.error("Demo upload failed", error);
      alert("Failed to start demo workflow. Ensure images are generated.");
    }
  };

  const getStatusIcon = (state: string) => {
    if (state === 'COMPLETED') return <CheckCircle className="text-emerald-500 w-5 h-5" />;
    if (['NEEDS_CLARIFICATION', 'HUMAN_REVIEW', 'ERROR_RECOVERY', 'FAILED'].includes(state))
      return <AlertTriangle className="text-amber-500 w-5 h-5" />;
    return <Clock className="text-blue-500 w-5 h-5" />;
  };

  const needsAttention = stats?.recent_workflows.filter(wf =>
    ['NEEDS_CLARIFICATION', 'HUMAN_REVIEW', 'ERROR_RECOVERY'].includes(wf.state)
  ) || [];

  return (
    <div className="max-w-6xl mx-auto space-y-8 mt-4 animate-in fade-in duration-700">
      <div className="mb-8">
        <h2 className="text-3xl font-extrabold text-white tracking-tight drop-shadow-md">Good morning</h2>
        <p className="text-slate-300 text-lg font-light mt-1">Here's what's happening with your business workflows.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Processed', value: stats?.processed || 0, icon: <FileText className="w-6 h-6 text-blue-400" />, color: 'from-blue-500/20 to-blue-600/10' },
          { label: 'Completed', value: stats?.completed || 0, icon: <CheckCircle className="w-6 h-6 text-emerald-400" />, color: 'from-emerald-500/20 to-emerald-600/10' },
          { label: 'Needs Review', value: stats?.needs_review || 0, icon: <AlertTriangle className="w-6 h-6 text-amber-400" />, color: 'from-amber-500/20 to-amber-600/10' },
          { label: 'Blocked', value: stats?.blocked || 0, icon: <ShieldAlert className="w-6 h-6 text-rose-400" />, color: 'from-rose-500/20 to-rose-600/10' }
        ].map((stat, i) => (
          <div key={i} className={`glass-card p-6 rounded-2xl bg-gradient-to-br ${stat.color} border border-white/5`}>
            <div className="flex justify-between items-start">
              <div>
                <p className="text-slate-400 text-sm font-medium">{stat.label}</p>
                <p className="text-3xl font-bold text-white mt-2">{loading ? '-' : stat.value}</p>
              </div>
              <div className="p-3 glass rounded-xl bg-black/20">
                {stat.icon}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-8">
        {/* Left Column */}
        <div className="lg:col-span-2 space-y-8">

          <div className="glass-card p-8 rounded-2xl relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-r from-primary-600/10 to-primary-400/5 opacity-50 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div className="relative z-10 flex flex-col sm:flex-row items-center justify-between gap-6">
              <div>
                <h3 className="text-xl font-bold text-white">Start a new workflow</h3>
                <p className="text-slate-400 mt-2 max-w-sm text-sm leading-relaxed">
                  Upload a bill, order note, payment screenshot, or handwritten business note.
                </p>
              </div>
              <label className="cursor-pointer shrink-0 inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-500 text-white px-6 py-3 rounded-xl font-medium transition-all duration-300 shadow-lg shadow-primary-500/20 hover:scale-105">
                <Upload className="w-5 h-5" />
                Scan / Upload Document
                <input type="file" className="hidden" accept="image/*" onChange={handleUpload} />
              </label>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => handleDemoUpload('clear-order.jpg')}
              className="glass-button px-4 py-2 rounded-full text-xs font-semibold text-primary-100 flex items-center gap-2">
              Sample: Clear Order
            </button>
            <button
              onClick={() => handleDemoUpload('blurry-order.jpg')}
              className="glass-button px-4 py-2 rounded-full text-xs font-semibold text-primary-100 flex items-center gap-2">
              Sample: Blurry Order
            </button>
            <button
              onClick={() => handleDemoUpload('incomplete-order.jpg')}
              className="glass-button px-4 py-2 rounded-full text-xs font-semibold text-primary-100 flex items-center gap-2">
              Sample: Missing Amount
            </button>
            <button
              onClick={() => handleDemoUpload('sensitive-pii.jpg')}
              className="glass-button px-4 py-2 rounded-full text-xs font-semibold text-primary-100 flex items-center gap-2">
              Sample: Sensitive PII
            </button>
          </div>

          {needsAttention.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                Needs your attention
              </h3>
              <div className="space-y-3">
                {needsAttention.map((wf) => (
                  <div key={wf.id} className="glass-card p-5 rounded-xl border border-amber-500/20 flex flex-col sm:flex-row justify-between sm:items-center gap-4">
                    <div>
                      <p className="font-semibold text-white text-base">
                        {wf.extraction?.customer_name || 'Unknown'} — {wf.document?.type?.replace(/_/g, ' ') || 'Document'}
                      </p>
                      <div className="flex items-center gap-3 mt-1.5 text-sm text-slate-400">
                        {(wf.extraction?.quantity || wf.extraction?.product) && (
                          <span>{wf.extraction.quantity} {wf.extraction.product}</span>
                        )}
                        {wf.extraction?.amount && (
                          <span>· ₹{wf.extraction.amount}</span>
                        )}
                      </div>
                      <p className="text-sm text-amber-400/80 mt-2 font-medium">
                        {wf.state === 'NEEDS_CLARIFICATION' && wf.missing_info ? `Missing ${wf.missing_info.join(', ')}` : 'Human review required'}
                      </p>
                    </div>
                    <div className="flex flex-row sm:flex-col items-center sm:items-end justify-between gap-3 shrink-0">
                       <span className="text-xs font-bold text-amber-300 bg-amber-900/40 border border-amber-500/30 px-3 py-1 rounded-full tracking-wider">
                        {wf.state.replace(/_/g, ' ')}
                      </span>
                      <Link
                        to={`/workflow/${wf.id}`}
                        className="bg-white/10 hover:bg-white/20 text-white px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
                      >
                        Review
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Clock className="w-5 h-5 text-slate-400" />
              Recent Workflows
            </h3>
            {loading ? (
              <div className="flex justify-center p-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-400"></div>
              </div>
            ) : (stats?.recent_workflows.length || 0) === 0 ? (
              <div className="text-center py-12 text-slate-400 glass rounded-2xl">
                No recent workflows. Start by uploading a document.
              </div>
            ) : (
              <div className="space-y-3">
                {stats?.recent_workflows.slice(0, 10).map((wf) => (
                  <Link
                    key={wf.id}
                    to={`/workflow/${wf.id}`}
                    className="flex items-center justify-between p-4 glass rounded-xl hover:bg-white/10 transition-all duration-300 group"
                  >
                    <div className="flex items-center gap-4">
                      {getStatusIcon(wf.state)}
                      <div>
                        <p className="font-medium text-slate-200">
                           {wf.extraction?.customer_name ? `${wf.extraction.customer_name} — ` : ''}
                           {wf.document?.type ? wf.document.type.replace(/_/g, ' ') : wf.original_filename}
                        </p>
                        <p className="text-xs text-slate-400 mt-0.5">{new Date(wf.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                    <div className="text-xs font-medium text-slate-300">
                      {wf.state === 'COMPLETED' ? 'Completed' :
                       wf.state === 'HUMAN_REVIEW' ? 'Human Review' :
                       wf.state === 'NEEDS_CLARIFICATION' ? 'Needs Clarification' :
                       wf.state.replace(/_/g, ' ')}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* Right Column */}
        <div className="space-y-6">
          <div className="glass-card p-6 rounded-2xl">
            <h3 className="text-lg font-semibold text-white mb-6">Worker Health</h3>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Cpu className="w-5 h-5 text-slate-400" />
                  <span className="text-sm font-medium text-slate-300">AI Worker</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span className="text-xs font-semibold text-emerald-400">Operational</span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Camera className="w-5 h-5 text-slate-400" />
                  <span className="text-sm font-medium text-slate-300">OCR Service</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span className="text-xs font-semibold text-emerald-400">Operational</span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Database className="w-5 h-5 text-slate-400" />
                  <span className="text-sm font-medium text-slate-300">Database</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  <span className="text-xs font-semibold text-emerald-400">Operational</span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Server className="w-5 h-5 text-slate-400" />
                  <span className="text-sm font-medium text-slate-300">Demo Mode</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-blue-400 bg-blue-500/20 px-2 py-0.5 rounded">Active</span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};
