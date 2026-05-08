import React from 'react';
import { 
  History, 
  ExternalLink, 
  Settings, 
  LogOut, 
  Search, 
  Filter, 
  MoreHorizontal,
  Inbox
} from 'lucide-react';

export const APISidebar = () => {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex-1">
        <div className="px-2 py-2">
          <button className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-indigo-700 bg-indigo-50 rounded-lg transition-all">
            <History className="w-4 h-4" />
            API history
          </button>
          <button className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-slate-600 hover:bg-white hover:shadow-sm rounded-lg transition-all mt-1">
            <div className="flex items-center gap-3">
              <ExternalLink className="w-4 h-4 text-slate-400" />
              API reference
            </div>
            <ExternalLink className="w-3 h-3 text-slate-400" />
          </button>
        </div>
      </div>
    </div>
  );
};

export const APIHeaderExtras = () => (
  <div className="flex items-center gap-2 text-slate-300 text-sm cursor-pointer hover:text-white transition-colors">
    <span>GovChat V1</span>
    <Settings className="w-4 h-4" />
  </div>
);

const APIPage = () => {
  const columns = [
    { label: 'Timestamp', key: 'timestamp' },
    { label: 'API type', key: 'type', hasFilter: true },
    { label: 'Status', key: 'status', hasFilter: true },
    { label: 'Question / SQL', key: 'query' },
    { label: 'Thread ID', key: 'threadId', hasSearch: true },
    { label: 'Duration (ms)', key: 'duration' },
    { label: 'Actions', key: 'actions' },
  ];

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden">
      <div className="p-8">
        <div className="flex items-center gap-2 mb-2">
          <History className="w-5 h-5 text-slate-400" />
          <h1 className="text-xl font-semibold text-slate-800">API history</h1>
        </div>
        <p className="text-sm text-slate-500 mb-8">
          Here you can view the full history of API calls, including request inputs, responses, and execution details.
        </p>

        <div className="border border-slate-200 rounded-lg overflow-hidden shadow-sm">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                {columns.map((col) => (
                  <th key={col.key} className="px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    <div className="flex items-center gap-2">
                      {col.label}
                      {col.hasFilter && <Filter className="w-3 h-3 text-slate-400 cursor-pointer hover:text-slate-600" />}
                      {col.hasSearch && <Search className="w-3 h-3 text-slate-400 cursor-pointer hover:text-slate-600" />}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={columns.length} className="py-20">
                  <div className="flex flex-col items-center justify-center text-slate-400">
                    <div className="w-16 h-16 bg-slate-50 rounded-2xl flex items-center justify-center mb-4">
                      <Inbox className="w-8 h-8 opacity-20" />
                    </div>
                    <span className="text-sm font-medium">No Data</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <div className="h-2 bg-slate-100 border-t border-slate-200"></div>
        </div>
      </div>
    </div>
  );
};

export default APIPage;
