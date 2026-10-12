import React, { useState } from 'react';
import { api } from '../services/api';
import { CheckCircle, XCircle, Play } from 'lucide-react';

export const Evaluation: React.FC = () => {
  const [results, setResults] = useState<any[]>([]);
  const [running, setRunning] = useState(false);

  const runEvaluation = async () => {
    setRunning(true);
    try {
      const res = await api.post('/evaluation/run');
      setResults(res.data.results);
    } catch (error) {
      console.error(error);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Evaluation Harness</h2>
          <p className="text-gray-500">Run synthetic test cases against the workflow engine.</p>
        </div>
        <button
          onClick={runEvaluation}
          disabled={running}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors flex items-center gap-2 disabled:opacity-50"
        >
          <Play className="w-4 h-4" /> {running ? 'Running...' : 'Run All Tests'}
        </button>
      </div>

      {results.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Test Case</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Input</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Result</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200 text-sm">
              {results.map((r, i) => (
                <tr key={i}>
                  <td className="px-6 py-4 font-medium text-gray-900">{r.case}</td>
                  <td className="px-6 py-4 text-gray-500">{r.input}</td>
                  <td className="px-6 py-4">
                    {r.passed ?
                      <span className="flex items-center gap-1 text-green-600 font-medium"><CheckCircle className="w-4 h-4"/> Pass</span> :
                      <span className="flex items-center gap-1 text-red-600 font-medium"><XCircle className="w-4 h-4"/> Fail</span>
                    }
                  </td>
                  <td className="px-6 py-4 text-gray-500">
                    State: {r.actual_state}<br/>
                    {r.notes && r.notes.length > 0 && (
                      <span className="text-red-500 text-xs">{r.notes.join(', ')}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
