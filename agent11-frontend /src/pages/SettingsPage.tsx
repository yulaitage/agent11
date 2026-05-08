import { useState } from 'react';
import { Archive, LogOut, ChevronRight, Palette } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import SettingsSidebar from '../components/SettingsSidebar';

interface ArchivedChat {
  id: string;
  title: string;
  updatedAt: string;
}

const GeneralSettings: React.FC = () => {
  const [darkMode, setDarkMode] = useState(false);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-slate-800 mb-4">Preferences</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 flex items-center justify-center bg-white rounded-lg shadow-sm">
                <Palette className="w-5 h-5 text-slate-600" />
              </div>
              <div>
                <div className="text-sm font-medium text-slate-800">Dark Mode</div>
                <div className="text-xs text-slate-500">Switch between light and dark theme</div>
              </div>
            </div>
            <button
              onClick={() => setDarkMode(!darkMode)}
              className={`relative w-12 h-6 rounded-full transition-colors ${darkMode ? 'bg-indigo-600' : 'bg-slate-300'}`}
            >
              <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${darkMode ? 'left-7' : 'left-1'}`} />
            </button>
          </div>

          <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 flex items-center justify-center bg-white rounded-lg shadow-sm">
                <Archive className="w-5 h-5 text-slate-600" />
              </div>
              <div>
                <div className="text-sm font-medium text-slate-800">Archived Chats</div>
                <div className="text-xs text-slate-500">View and manage archived conversations</div>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-slate-400" />
          </div>
        </div>
      </div>
    </div>
  );
};

const AccountSettings: React.FC<{ onLogout: () => void }> = ({ onLogout }) => {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-slate-800 mb-4">Account Information</h3>
        <div className="bg-slate-50 rounded-lg p-4 space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-slate-500">Email</span>
            <span className="text-slate-800">user@example.com</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500">Role</span>
            <span className="text-slate-800">Admin</span>
          </div>
        </div>
      </div>
      <div>
        <button
          onClick={onLogout}
          className="flex items-center gap-3 px-4 py-3 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
        >
          <LogOut className="w-5 h-5" />
          <span className="text-sm font-medium">Log Out</span>
        </button>
      </div>
    </div>
  );
};

const SettingsPage: React.FC = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState('general');

  const handleLogout = async () => {
    logout();
    navigate('/login');
  };

  const renderContent = () => {
    switch (activeSection) {
      case 'account':
        return <AccountSettings onLogout={handleLogout} />;
      default:
        return <GeneralSettings />;
    }
  };

  return (
    <div className="flex flex-1 bg-white">
      <SettingsSidebar activeSection={activeSection} onSectionChange={setActiveSection} />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl">
          <h2 className="text-lg font-semibold text-slate-800 mb-6 capitalize">{activeSection}</h2>
          {renderContent()}
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;