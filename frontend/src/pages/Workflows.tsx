import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { workflowApi } from '../services/api';
import type { Workflow } from '../types';
import { CheckCircle, AlertTriangle, Clock } from 'lucide-react';

export const Workflows: React.FC = () => {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'All' | 'Needs Review' | 'Blocked' | 'Completed'>('All');

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const fetchWorkflows = async () => {
    try {
      const data = await workflowApi.listWorkflows();
      setWorkflows(data);
    } catch (error) {
      console.error("Failed to fetch workflows", error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (state: string) => {
    if (state === 'COMPLETED') return <CheckCircle className="text-emerald-500 w-5 h-5" />;
    if (['NEEDS_CLARIFICATION', 'HUMAN_REVIEW', 'ERROR_RECOVERY', 'FAILED'].includes(state))
      return <AlertTriangle className="text-amber-500 w-5 h-5" />;
    return <Clock className="text-blue-500 w-5 h-5" />;
  };

  const filteredWorkflows = workflows.filter(wf => {
    if (filter === 'All') return true;
    if (filter === 'Completed') return wf.state === 'COMPLETED';
    if (filter === 'Needs Review') return ['NEEDS_CLARIFICATION', 'HUMAN_REVIEW'].includes(wf.state);
    if (filter === 'Blocked') return ['FAILED', 'ERROR_RECOVERY'].includes(wf.state);
    return true;
  });

  return (
    <div className="max-w-6xl mx-auto space-y-6 mt-4 animate-in fade-in duration-700">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h2 className="text-3xl font-extrabold text-white tracking-tight drop-shadow-md">Workflows</h2>
          <p className="text-slate-300 text-lg font-light mt-1">Manage and review all business workflows.</p>
        </div>

        <div className="flex flex-wrap gap-2">
          {['All', 'Needs Review', 'Blocked', 'Completed'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f as any)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                filter === f
                  ? 'bg-primary-500 text-white shadow-lg shadow-primary-500/20'
                  : 'bg-white/5 text-slate-300 hover:bg-white/10'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="glass-card rounded-2xl overflow-hidden">
        {loading ? (
          <div className="flex justify-center p-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-400"></div>
          </div>
        ) : filteredWorkflows.length === 0 ? (
          <div className="text-center py-16 text-slate-400">
            No workflows found matching the filter.
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {filteredWorkflows.map((wf) => (
              <div key={wf.id} className="p-5 hover:bg-white/5 transition-colors flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 group">
                <div className="flex items-start gap-4">
                  <div className="mt-1">
                    {getStatusIcon(wf.state)}
                  </div>
                  <div>
                    <h4 className="text-white font-semibold">
                      {wf.extraction?.customer_name ? `${wf.extraction.customer_name} — ` : ''}
                      {wf.document?.type ? wf.document.type.replace(/_/g, ' ') : wf.original_filename}
                    </h4>
                    <p className="text-sm text-slate-400 mt-1 line-clamp-1">
                      {wf.draft_message || wf.recommended_action || 'No action generated yet'}
                    </p>
                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-500 font-medium">
                      <span>{new Date(wf.created_at).toLocaleString()}</span>
                      <span>•</span>
                      <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10">
                        {wf.state.replace(/_/g, ' ')}
                      </span>
                    </div>
                  </div>
                </div>

                <Link
                  to={`/workflow/${wf.id}`}
                  className="shrink-0 bg-white/10 hover:bg-primary-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 opacity-100 sm:opacity-0 group-hover:opacity-100"
                >
                  Review
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
