import React from 'react';
import { 
  Users, 
  ExternalLink, 
  Settings, 
  CheckCircle2,
  MoreHorizontal
} from 'lucide-react';

export const UsersSidebar = () => {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex-1">
        <div className="px-2 py-2">
          <button className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-indigo-700 bg-indigo-50 rounded-lg transition-all">
            <ExternalLink className="w-4 h-4" />
            User Management
          </button>
        </div>
      </div>
    </div>
  );
};

export const UsersHeaderExtras = () => (
  <div className="flex items-center gap-2 text-slate-300 text-sm cursor-pointer hover:text-white transition-colors">
    <span>GovChat V1</span>
    <Settings className="w-4 h-4" />
  </div>
);

const UsersPage = () => {
  const users = [
    { 
      name: 'GovChat Admin', 
      email: 'admin@spesland.com', 
      status: 'APPROVED' 
    }
  ];

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden">
      <div className="p-8">
        <div className="flex items-center gap-2 mb-2">
          <ExternalLink className="w-5 h-5 text-slate-400" />
          <h1 className="text-xl font-semibold text-slate-800">User Management</h1>
        </div>
        <p className="text-sm text-slate-500 mb-8">
          You can view all registered users here and choose to allow or block them from logging in.
        </p>

        <div className="border border-slate-200 rounded-lg overflow-hidden shadow-sm">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-6 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Name</th>
                <th className="px-6 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Email</th>
                <th className="px-6 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.map((user, idx) => (
                <tr key={idx} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4 text-sm text-slate-700 font-medium">{user.name}</td>
                  <td className="px-6 py-4 text-sm text-slate-500">{user.email}</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-green-200 bg-green-50 text-[10px] font-bold text-green-600">
                      <CheckCircle2 className="w-3 h-3" />
                      {user.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-sm text-slate-400 hover:text-red-500 transition-colors">
                      Reject
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default UsersPage;
