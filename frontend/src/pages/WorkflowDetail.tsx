import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { workflowApi } from '../services/api';
import type { Workflow, AuditLog } from '../types';
import { CheckCircle, AlertTriangle, ArrowRight, XCircle, ChevronRight, ChevronDown, Code } from 'lucide-react';

export const WorkflowDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [clarification, setClarification] = useState<Record<string, string>>({});
  const [editedAction, setEditedAction] = useState('');
  const [editedMessage, setEditedMessage] = useState('');
  const [showOcr, setShowOcr] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingError, setProcessingError] = useState('');

  const clarificationLabel = (field: string) => ({
    customer_name: 'Customer name',
    person: 'Customer name',
    product: 'Product',
    quantity: 'Quantity',
    delivery_date: 'Delivery date',
    date: 'Date',
    amount: 'Amount',
  }[field] || field.replace(/_/g, ' '));

  const fetchWorkflow = async () => {
    if (!id) return;
    try {
      const data = await workflowApi.getWorkflow(Number(id));
      setWorkflow(data);
      if (data.recommended_action) setEditedAction(data.recommended_action);
      if (data.draft_message) setEditedMessage(data.draft_message);

      const logData = await workflowApi.getAuditLog(Number(id));
      setLogs(logData);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchWorkflow();
    const refresh = () => { void fetchWorkflow(); };
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, [id]);

  useEffect(() => {
    const activeStates = ['RECEIVED', 'PROCESSING', 'CLASSIFIED', 'EXTRACTED', 'VALIDATING', 'NEEDS_CLARIFICATION'];
    if (!isProcessing && !activeStates.includes(workflow?.state || '')) return;
    const timer = window.setInterval(() => { void fetchWorkflow(); }, 2000);
    return () => window.clearInterval(timer);
  }, [id, isProcessing, workflow?.state]);

  const handleProcess = async () => {
    if (!workflow) return;
    setIsProcessing(true);
    setProcessingError('');
    try {
      await workflowApi.processWorkflow(workflow.id);
      await fetchWorkflow();
    } catch (error) {
      console.error(error);
      setProcessingError('The processing request failed or timed out. The latest workflow status is shown below; retry if processing has stopped.');
    } finally {
      await fetchWorkflow();
      setIsProcessing(false);
    }
  };

  const handleClarifySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workflow) return;
    try {
      await workflowApi.clarify(workflow.id, clarification);
      setClarification({});
      fetchWorkflow();
    } catch (error) {
      console.error(error);
    }
  };

  const handleApprove = async () => {
    if (!workflow) return;
    try {
      await workflowApi.approve(workflow.id, editedAction, editedMessage);
      fetchWorkflow();
    } catch (error) {
      console.error(error);
    }
  };

  const handleReject = async () => {
    if (!workflow) return;
    try {
      await workflowApi.reject(workflow.id);
      fetchWorkflow();
    } catch (error) {
      console.error(error);
    }
  };

  if (!workflow) return (
    <div className="flex justify-center p-12">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-400"></div>
    </div>
  );

  const getTimelineSteps = () => {
    const isClarification = workflow.state === 'NEEDS_CLARIFICATION';

    return [
      { id: 'RECEIVED', label: 'Received', done: true },
      { id: 'PROCESSING', label: 'Processing', done: true },
      { id: 'EXTRACTED', label: 'Extracted', done: ['EXTRACTED', 'VALIDATING', 'NEEDS_CLARIFICATION', 'READY_FOR_ACTION', 'HUMAN_REVIEW', 'APPROVED', 'COMPLETED'].includes(workflow.state) },
      { id: 'VALIDATING', label: 'Validating', done: ['VALIDATING', 'NEEDS_CLARIFICATION', 'READY_FOR_ACTION', 'HUMAN_REVIEW', 'APPROVED', 'COMPLETED'].includes(workflow.state) },
      {
        id: 'DECISION',
        label: isClarification ? 'Needs Clarification' : ['READY_FOR_ACTION', 'HUMAN_REVIEW', 'APPROVED', 'COMPLETED'].includes(workflow.state) ? 'Ready for Action' : 'Pending',
        done: ['NEEDS_CLARIFICATION', 'READY_FOR_ACTION', 'HUMAN_REVIEW', 'APPROVED', 'COMPLETED'].includes(workflow.state),
        current: ['NEEDS_CLARIFICATION', 'READY_FOR_ACTION'].includes(workflow.state),
        isWarning: isClarification
      },
      { id: 'HUMAN_REVIEW', label: 'Human Review', done: ['APPROVED', 'COMPLETED'].includes(workflow.state), current: workflow.state === 'HUMAN_REVIEW' },
      { id: 'COMPLETED', label: 'Completed', done: workflow.state === 'COMPLETED', current: workflow.state === 'COMPLETED' }
    ];
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 animate-in fade-in duration-700 mt-4">

      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
          Workflow #{workflow.id}
          <span className="text-sm font-bold text-primary-200 bg-primary-900/50 border border-primary-500/30 px-3 py-1 rounded-full tracking-wider">
            {workflow.state.replace(/_/g, ' ')}
          </span>
        </h2>
        {['RECEIVED', 'FAILED', 'ERROR_RECOVERY'].includes(workflow.state) && (
          <button
            onClick={handleProcess}
            disabled={isProcessing}
            className={`ml-auto px-4 py-2 ${isProcessing ? 'bg-primary-800 text-primary-300' : 'bg-primary-600 text-white hover:bg-primary-500'} rounded-lg transition-colors flex items-center gap-2 shadow-lg shadow-primary-500/20`}
          >
            {isProcessing ? 'Processing...' : 'Start Processing'} <ArrowRight className="w-4 h-4" />
          </button>
        )}
      </div>

      {(processingError || workflow.error_message) && (
        <div role="alert" className="rounded-xl border border-rose-500/40 bg-rose-900/20 p-4 text-rose-200">
          {workflow.error_message || processingError}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left Column: Image and Audit */}
        <div className="lg:col-span-1 space-y-6">
          <div className="glass-card rounded-2xl p-5 border border-white/5">
            <h3 className="font-semibold text-slate-100 mb-4 flex items-center gap-2">Original Document</h3>
            <div className="aspect-[3/4] bg-black/20 rounded-xl flex items-center justify-center overflow-hidden border border-white/5 relative group">
              <img
                src={`http://localhost:8000/uploads/${workflow.id}_${workflow.original_filename}`}
                alt="Document"
                className="w-full h-full object-contain"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                  (e.target as HTMLImageElement).parentElement!.innerHTML = `
                    <div class="text-slate-500 text-sm p-4 text-center">
                      Failed to load image.<br/>(Check backend uploads folder)
                    </div>
                  `;
                }}
              />
            </div>
          </div>

          <div className="glass-card rounded-2xl p-5 border border-white/5">
            <h3 className="font-semibold text-slate-100 mb-4">Workflow Timeline</h3>
            <div className="mb-8">
              <div className="flex flex-col gap-1 relative">
                {getTimelineSteps().map((step, idx) => (
                  <div key={step.id} className="flex items-start gap-3">
                    <div className="flex flex-col items-center">
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center border-2 z-10 ${
                        step.done
                          ? step.isWarning ? 'bg-amber-500 border-amber-500 text-black' : 'bg-primary-500 border-primary-500 text-white'
                          : step.current ? 'bg-primary-900/50 border-primary-400' : 'bg-transparent border-slate-600'
                      }`}>
                        {step.done ? (step.isWarning ? '!' : '✓') : step.current ? '●' : ''}
                      </div>
                      {idx < getTimelineSteps().length - 1 && (
                        <div className={`w-0.5 h-6 ${step.done ? 'bg-primary-500/50' : 'bg-slate-700/50'}`}></div>
                      )}
                    </div>
                    <div className={`text-sm mt-0.5 font-medium ${
                      step.done || step.current ? 'text-slate-200' : 'text-slate-500'
                    }`}>
                      {step.label}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <h3 className="font-semibold text-slate-100 mb-4 pt-4 border-t border-white/10">Audit Trail</h3>
            <div className="space-y-4 text-sm max-h-60 overflow-y-auto pr-2 custom-scrollbar">
              {logs.map((log) => (
                <div key={log.id} className="relative pl-4 border-l-2 border-slate-700">
                  <div className="absolute -left-[5px] top-1.5 w-2 h-2 rounded-full bg-slate-500"></div>
                  <p className="text-xs text-slate-400">{new Date(log.created_at).toLocaleTimeString()}</p>
                  <p className="text-slate-200 mt-0.5">{log.message}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Workflow State */}
        <div className="lg:col-span-2 space-y-6">

          {/* Extracted Data */}
          {workflow.extraction && (
            <div className="glass-card rounded-2xl p-6 border border-white/5">
              <div className="flex flex-col mb-6 gap-2">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-lg text-white">Extracted Information</h3>
                  {workflow.document?.type && (
                    <span className="text-sm font-bold text-emerald-400 bg-emerald-900/40 px-3 py-1 rounded border border-emerald-500/30">
                      Type: {workflow.document.type.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>
                {workflow.document?.reason && (
                  <p className="text-sm text-slate-400 italic bg-black/20 p-2 rounded border border-white/5">
                    {workflow.document.reason}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
                {Object.entries(workflow.extraction).map(([key, value]) => {
                  if (key === 'confidence_scores' || key === 'document_type') return null;

                  const isMissing = workflow.missing_info?.includes(key);

                  if (Array.isArray(value)) {
                     if (value.length === 0 && !isMissing) return null; // Don't show empty arrays if not required

                     return (
                       <div key={key} className="md:col-span-2 bg-white/5 rounded-xl p-4 border border-white/5">
                         <div className="flex justify-between items-start mb-2">
                           <p className="text-xs text-slate-400 uppercase tracking-widest font-semibold">{key}</p>
                         </div>
                         <ul className="space-y-2">
                           {value.map((item, i) => (
                             <li key={i} className="font-medium text-slate-200 flex items-center gap-2">
                               <ChevronRight className="w-4 h-4 text-primary-400" />
                               {typeof item === 'string' ? item : `${item.quantity || ''} ${item.unit || ''} ${item.name || item.price || ''}`}
                             </li>
                           ))}
                           {value.length === 0 && isMissing && (
                             <li className="font-medium text-amber-400/70 italic">Missing</li>
                           )}
                         </ul>
                       </div>
                     );
                  }

                  if (value === null && !isMissing) return null; // Hide irrelevant null fields

                  return (
                    <div key={key} className={`bg-white/5 rounded-xl p-4 border ${isMissing ? 'border-amber-500/50 bg-amber-500/5' : 'border-white/5'}`}>
                      <div className="flex justify-between items-start mb-1">
                        <p className="text-xs text-slate-400 uppercase tracking-widest font-semibold">{key.replace(/_/g, ' ')}</p>
                        {isMissing && (
                          <span className="text-xs font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">
                            Missing
                          </span>
                        )}
                      </div>
                      <p className={`text-lg font-medium ${isMissing ? 'text-amber-400/70 italic' : 'text-slate-100'}`}>
                        {isMissing ? 'Unknown' : value !== null ? String(value) : 'Unknown'}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* RAW OCR DEBUG PANEL */}
          {workflow.ocr?.raw_text && (
            <div className="glass-card rounded-2xl overflow-hidden border border-white/5">
              <button
                onClick={() => setShowOcr(!showOcr)}
                className="w-full p-4 flex items-center justify-between text-slate-300 hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center gap-2 font-medium">
                  <Code className="w-4 h-4 text-slate-400" />
                  View extracted raw text (OCR)
                </div>
                <ChevronDown className={`w-5 h-5 transition-transform ${showOcr ? 'rotate-180' : ''}`} />
              </button>
              {showOcr && (
                <div className="p-4 bg-black/40 border-t border-white/5">
                  <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono custom-scrollbar">
                    {workflow.ocr.raw_text}
                  </pre>
                </div>
              )}
            </div>
          )}

          {workflow.normalized_text && (
            <div className="glass-card rounded-2xl p-5 border border-white/5">
              <h3 className="font-semibold text-slate-100 mb-2">Normalized / Interpreted Text</h3>
              <p className="text-sm text-slate-300 whitespace-pre-wrap font-mono">
                {workflow.normalized_text}
              </p>
            </div>
          )}

          {/* EXTRACTION DEBUG PANEL */}
          <div className="glass-card rounded-2xl overflow-hidden border border-white/5">
            <details className="group">
              <summary className="w-full p-4 flex items-center justify-between text-slate-300 hover:bg-white/5 transition-colors cursor-pointer list-none">
                <div className="flex items-center gap-2 font-medium text-amber-400">
                  <Code className="w-4 h-4 text-amber-500" />
                  Extraction Debug
                </div>
                <ChevronDown className="w-5 h-5 transition-transform group-open:rotate-180 text-amber-400" />
              </summary>
              <div className="p-4 bg-black/40 border-t border-white/5 text-sm text-slate-300 space-y-2 font-mono">
                <div className="grid grid-cols-[150px_1fr] gap-2">
                  <div className="text-slate-500">Workflow ID:</div>
                  <div>{workflow.id}</div>

                  <div className="text-slate-500">Original filename:</div>
                  <div className="break-all">{workflow.original_filename}</div>

                  <div className="text-slate-500">Image hash:</div>
                  <div className="break-all text-xs">{workflow.file_hash || 'N/A'}</div>

                  <div className="text-slate-500">Input integrity:</div>
                  <div className={workflow.file_hash ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                    {workflow.file_hash ? 'VERIFIED' : 'FAILED'}
                  </div>

                  <div className="text-slate-500">File size:</div>
                  <div>{workflow.file_size ? `${workflow.file_size} bytes` : 'N/A'}</div>

                  <div className="text-slate-500">Dimensions:</div>
                  <div>{workflow.image_width && workflow.image_height ? `${workflow.image_width}x${workflow.image_height}` : 'N/A'}</div>

                  <div className="text-slate-500">OCR Provider:</div>
                  <div>{workflow.ocr_provider || 'Unknown'}</div>

                  <div className="text-slate-500">Vision Provider:</div>
                  <div>{['CloudVision', 'GeminiVision'].includes(workflow.ocr_provider || '') ? 'Gemini Vision' : 'N/A'}</div>

                  <div className="text-slate-500">Raw OCR:</div>
                  <div className="break-all whitespace-pre-wrap">{workflow.ocr?.raw_text || 'N/A'}</div>

                  <div className="text-slate-500">Classification:</div>
                  <div>{workflow.document?.type || 'Unknown'}</div>

                  <div className="text-slate-500">Extraction Source:</div>
                  <div>{workflow.ocr_provider === 'MockOCR' ? 'MockAI' : 'GeminiAI'}</div>

                  <div className="text-slate-500">Created timestamp:</div>
                  <div>{new Date(workflow.created_at).toISOString()}</div>

                  <div className="text-slate-500">Processing timestamp:</div>
                  <div>{new Date(workflow.updated_at).toISOString()}</div>

                  {workflow.provenance && (
                    <>
                      <div className="text-slate-500 mt-2 col-span-2 border-t border-white/10 pt-2 font-semibold">Provenance Map:</div>
                      <div className="col-span-2 bg-black/40 p-2 rounded border border-white/5 whitespace-pre-wrap">
                        {JSON.stringify(workflow.provenance, null, 2)}
                      </div>
                    </>
                  )}
                  {workflow.field_confidence && (
                    <>
                      <div className="text-slate-500 mt-2 col-span-2 border-t border-white/10 pt-2 font-semibold">Field Confidence / Evidence:</div>
                      <div className="col-span-2 bg-black/40 p-2 rounded border border-white/5 whitespace-pre-wrap">
                        {JSON.stringify(workflow.field_confidence, null, 2)}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </details>
          </div>

          {/* Clarification Needed */}
          {workflow.state === 'NEEDS_CLARIFICATION' && workflow.error_message && !workflow.missing_info && (
            <div className="bg-amber-900/20 border border-amber-500/30 rounded-2xl p-6 shadow-lg shadow-amber-900/10">
              <div className="flex items-center gap-3 text-amber-400 mb-3">
                <div className="p-2 bg-amber-500/20 rounded-lg">
                  <AlertTriangle className="w-6 h-6" />
                </div>
                <h3 className="font-bold text-xl text-amber-100">Worker needs better image text</h3>
              </div>
              <p className="text-amber-200/80 mb-5 text-sm">{workflow.error_message}</p>
              <button
                onClick={handleProcess}
                disabled={isProcessing}
                className="px-6 py-3 bg-amber-500 text-black font-semibold rounded-xl hover:bg-amber-400 transition-colors disabled:opacity-50"
              >
                {isProcessing ? 'Retrying…' : 'Retry Processing'}
              </button>
            </div>
          )}

          {workflow.state === 'NEEDS_CLARIFICATION' && workflow.missing_info?.includes('document_type') && (
            <div role="alert" className="rounded-xl border border-amber-500/40 p-5 text-amber-100">
              <p>The document could not be interpreted. Retry processing to read the image again.</p>
              <button onClick={handleProcess} disabled={isProcessing} className="mt-4 rounded-lg bg-amber-500 px-4 py-2 text-black disabled:opacity-50">
                {isProcessing ? 'Processing...' : 'Retry Processing'}
              </button>
            </div>
          )}

          {workflow.state === 'NEEDS_CLARIFICATION' && workflow.missing_info && !workflow.missing_info.includes('document_type') && (
            <div className="bg-amber-900/20 border border-amber-500/30 rounded-2xl p-6 shadow-lg shadow-amber-900/10 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/10 blur-3xl rounded-full translate-x-1/2 -translate-y-1/2"></div>

              <div className="relative z-10">
                <div className="flex items-center gap-3 text-amber-400 mb-2">
                  <div className="p-2 bg-amber-500/20 rounded-lg">
                    <AlertTriangle className="w-6 h-6" />
                  </div>
                  <h3 className="font-bold text-xl text-amber-100">Worker paused — information required</h3>
                </div>
                <p className="text-amber-200/80 mb-6 text-sm">
                  I couldn't confidently determine these fields for this {workflow.document?.type?.replace(/_/g, ' ')}.
                </p>
                <p className="text-amber-100 mb-4 font-medium">
                  Please provide: {workflow.missing_info.map(clarificationLabel).join(', ')}.
                  {workflow.missing_info.includes('amount') && ' Amount must be entered as a number.'}
                </p>

                <form onSubmit={handleClarifySubmit} className="space-y-4 mb-6">
                  {workflow.missing_info.map(field => (
                    <div key={field}>
                      <label className="block text-sm font-semibold text-amber-100 mb-1.5">{clarificationLabel(field)}</label>
                      <div className="flex items-center bg-black/40 border border-amber-500/30 rounded-xl focus-within:border-amber-400 focus-within:ring-1 focus-within:ring-amber-400">
                        {field === 'amount' && <span className="pl-4 text-amber-200 text-lg">₹</span>}
                        <input
                          type={field === 'amount' ? 'number' : 'text'}
                          inputMode={field === 'amount' ? 'decimal' : undefined}
                          min={field === 'amount' ? '0.01' : undefined}
                          step={field === 'amount' ? '0.01' : undefined}
                          required
                          className="w-full bg-transparent rounded-xl px-4 py-3 text-white focus:outline-none"
                          value={clarification[field] || ''}
                          onChange={e => setClarification(prev => ({...prev, [field]: e.target.value}))}
                          placeholder={field === 'amount' ? 'amount' : `Enter ${field.replace(/_/g, ' ')}`}
                        />
                      </div>
                    </div>
                  ))}
                  <div className="pt-2">
                    <button type="submit" className="px-6 py-3 bg-amber-500 text-black font-semibold rounded-xl hover:bg-amber-400 transition-colors shadow-lg shadow-amber-500/20">
                      Submit & Continue
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Human Review */}
          {workflow.state === 'HUMAN_REVIEW' && (
            <div className="bg-primary-900/20 border border-primary-500/30 rounded-2xl p-6 shadow-lg shadow-primary-900/10">
              <div className="flex items-center gap-3 text-primary-400 mb-6">
                <div className="p-2 bg-primary-500/20 rounded-lg">
                  <CheckCircle className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-xl text-white">Review Generated Action</h3>
                  <p className="text-primary-200/80 text-sm mt-1">Please approve or edit the recommended actions before proceeding.</p>
                </div>
              </div>

              <div className="space-y-5 mb-8">
                <div>
                  <label className="block text-sm font-semibold text-primary-100 mb-2">Recommended Action</label>
                  <input
                    type="text"
                    value={editedAction}
                    onChange={e => setEditedAction(e.target.value)}
                    className="w-full bg-black/40 border border-primary-500/30 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-primary-100 mb-2">Draft Message / Details</label>
                  <textarea
                    value={editedMessage}
                    onChange={e => setEditedMessage(e.target.value)}
                    rows={4}
                    className="w-full bg-black/40 border border-primary-500/30 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 transition-colors custom-scrollbar"
                  />
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <button
                  onClick={handleApprove}
                  className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-emerald-500 text-black font-semibold rounded-xl hover:bg-emerald-400 transition-colors shadow-lg shadow-emerald-500/20"
                >
                  <CheckCircle className="w-5 h-5" /> Approve Action
                </button>
                <button
                  onClick={handleReject}
                  className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-6 py-3 bg-transparent border border-rose-500/50 text-rose-400 font-semibold rounded-xl hover:bg-rose-500/10 transition-colors"
                >
                  <XCircle className="w-5 h-5" /> Reject
                </button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};
