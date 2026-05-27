import { useState, useEffect } from 'react';
import { X, Archive, Palette, Settings as SettingsIcon, Database, Plus, Trash2, Edit, Check, Server, Brain, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { chatApi } from '../api/chat';
import { llmApi, type LLMConfig } from '../api/llm';

interface SettingsPopupProps {
  opened: boolean;
  onClose: () => void;
}

interface ArchivedChat {
  id: string;
  title: string;
  updatedAt: string;
}

interface DatabaseConfig {
  id: string;
  name: string;
  type: 'postgresql' | 'mysql' | 'mongodb';
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
}

const PRESET_PROVIDERS = {
  'ollama-local': { name: 'Ollama (Local)', provider: 'ollama' as const, base_url: 'http://localhost:11434/v1' },
  'lmstudio-local': { name: 'LM Studio (Local)', provider: 'lmstudio' as const, base_url: 'http://localhost:1234/v1' },
  'deepseek': { name: 'DeepSeek', provider: 'deepseek' as const, base_url: 'https://api.deepseek.com/v1' },
  'zhipu': { name: '智谱 GLM', provider: 'zhipu' as const, base_url: 'https://open.bigmodel.cn/api/paas/v4' },
  'minimax': { name: 'MiniMax', provider: 'minimax' as const, base_url: 'https://api.minimax.chat/v1' },
  'custom': { name: 'Custom', provider: 'ollama' as const, base_url: '' },
}

const SettingsPopup: React.FC<SettingsPopupProps> = ({ opened, onClose }) => {
  const { logout } = useAuth();
  const [showArchived, setShowArchived] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [archivedChats, setArchivedChats] = useState<ArchivedChat[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'general' | 'database' | 'llm'>('general');
  const [databases, setDatabases] = useState<DatabaseConfig[]>([
    { id: '1', name: 'PostgreSQL Agent11', type: 'postgresql', host: 'localhost', port: '5433', database: 'agent11db', username: 'agent11', password: '' }
  ]);
  const [editingDb, setEditingDb] = useState<DatabaseConfig | null>(null);
  const [isAddingDb, setIsAddingDb] = useState(false);
  const [newDb, setNewDb] = useState<DatabaseConfig>({ id: '', name: '', type: 'postgresql', host: '', port: '', database: '', username: '', password: '' });

  // LLM Settings
  const [llmConfig, setLlmConfig] = useState<LLMConfig>({
    provider: 'ollama',
    base_url: 'http://localhost:11434/v1',
    model: 'qwen3:latest',
    temperature: 0.7,
    timeout: 120,
    api_key: '',
  });
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [llmConnected, setLlmConnected] = useState(false);
  const [llmLoading, setLlmLoading] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState<string>('');

  // Load LLM config on mount
  useEffect(() => {
    if (opened) {
      loadLlmConfig();
    }
  }, [opened]);

  const loadLlmConfig = async () => {
    try {
      const [config, status, models] = await Promise.all([
        llmApi.getConfig(),
        llmApi.getConnectionStatus(),
        llmApi.getAvailableModels().catch(() => ({ models: [] })),
      ]);
      setLlmConfig(config);
      setLlmConnected(status.connected);
      setAvailableModels(models.models || []);
    } catch (e) {
      console.error('Failed to load LLM config', e);
    }
  };

  const handleSaveLlmConfig = async () => {
    setLlmLoading(true);
    try {
      await llmApi.updateConfig(llmConfig);
      const status = await llmApi.getConnectionStatus();
      setLlmConnected(status.connected);
      alert('LLM 配置已保存');
    } catch (e) {
      console.error('Failed to save LLM config', e);
      alert('保存失败');
    } finally {
      setLlmLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    try {
      const result = await llmApi.testConnection(llmConfig);
      alert(result.message);
    } catch (e: any) {
      alert(e?.response?.data?.detail || '连接失败');
    } finally {
      setTestingConnection(false);
    }
  };

  const handlePresetChange = (preset: string) => {
    setSelectedPreset(preset);
    if (preset === 'custom') {
      setLlmConfig({ ...llmConfig, base_url: '' });
    } else if (preset && PRESET_PROVIDERS[preset as keyof typeof PRESET_PROVIDERS]) {
      const p = PRESET_PROVIDERS[preset as keyof typeof PRESET_PROVIDERS];
      setLlmConfig({ ...llmConfig, provider: p.provider, base_url: p.base_url });
    }
  };

  if (!opened) return null;

  const handleShowArchived = async () => {
    setLoading(true);
    try {
      const response = await chatApi.getChats();
      const chats = response.chats || [];
      const archived = chats
        .filter((c: any) => c.archived)
        .map((c: any) => ({
          id: c.id,
          title: c.title || 'Untitled',
          updatedAt: c.updatedAt || c.createdAt,
        }));
      setArchivedChats(archived);
      setShowArchived(true);
    } catch (e) {
      console.error('Failed to load archived chats', e);
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setShowArchived(false);
  };

  const handleDeleteChat = async (chatId: string) => {
    if (!confirm('Delete this chat?')) return;
    try {
      await chatApi.deleteChat(chatId);
      setArchivedChats(prev => prev.filter(c => c.id !== chatId));
    } catch (e) {
      console.error('Failed to delete chat', e);
    }
  };

  const handleLogout = async () => {
    logout();
    onClose();
  };

  const handleAddDb = () => {
    setIsAddingDb(true);
    setNewDb({ id: Date.now().toString(), name: '', type: 'postgresql', host: 'localhost', port: '5432', database: '', username: '', password: '' });
  };

  const handleSaveNewDb = () => {
    if (newDb.name && newDb.host && newDb.database) {
      setDatabases(prev => [...prev, { ...newDb, id: Date.now().toString() }]);
      setIsAddingDb(false);
    }
  };

  const handleDeleteDb = (id: string) => {
    if (confirm('Delete this database connection?')) {
      setDatabases(prev => prev.filter(d => d.id !== id));
    }
  };

  const handleEditDb = (db: DatabaseConfig) => {
    setEditingDb({ ...db });
  };

  const handleSaveEditDb = () => {
    if (editingDb) {
      setDatabases(prev => prev.map(d => d.id === editingDb.id ? editingDb : d));
      setEditingDb(null);
    }
  };

  const dbTypeLabels = { postgresql: 'PostgreSQL', mysql: 'MySQL', mongodb: 'MongoDB' };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl w-[750px] max-h-[85vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-800">
            {showArchived ? 'Archived Chats' : 'Settings'}
          </h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left Menu */}
          {!showArchived && (
            <div className="w-48 border-r border-slate-100 p-4 bg-slate-50/50">
              <div className="space-y-1">
                <button
                  onClick={() => setActiveTab('general')}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition-colors ${
                    activeTab === 'general' ? 'bg-indigo-100 text-indigo-700 font-medium' : 'text-slate-600 hover:bg-white hover:shadow-sm'
                  }`}
                >
                  <SettingsIcon className="w-4 h-4" />
                  General
                </button>
                <button
                  onClick={() => setActiveTab('database')}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition-colors ${
                    activeTab === 'database' ? 'bg-indigo-100 text-indigo-700 font-medium' : 'text-slate-600 hover:bg-white hover:shadow-sm'
                  }`}
                >
                  <Database className="w-4 h-4" />
                  Database
                </button>
                <button
                  onClick={() => setActiveTab('llm')}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition-colors ${
                    activeTab === 'llm' ? 'bg-indigo-100 text-indigo-700 font-medium' : 'text-slate-600 hover:bg-white hover:shadow-sm'
                  }`}
                >
                  <Brain className="w-4 h-4" />
                  LLM Model
                </button>
              </div>
            </div>
          )}

          {/* Right Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {showArchived ? (
              <div className="space-y-3">
                {loading ? (
                  <div className="text-center py-8 text-slate-400">Loading...</div>
                ) : archivedChats.length === 0 ? (
                  <div className="text-center py-8 text-slate-400">No archived chats</div>
                ) : (
                  archivedChats.map((chat) => (
                    <div
                      key={chat.id}
                      className="flex items-center justify-between px-4 py-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-slate-800 truncate">{chat.title}</div>
                        <div className="text-xs text-slate-500">
                          {new Date(chat.updatedAt).toLocaleDateString()}
                        </div>
                      </div>
                      <button
                        onClick={() => handleDeleteChat(chat.id)}
                        className="ml-4 p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            ) : activeTab === 'general' ? (
              <div className="space-y-6">
                {/* Archived Chats */}
                <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 flex items-center justify-center bg-white rounded-lg shadow-sm">
                      <Archive className="w-5 h-5 text-slate-600" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-800">Archived Chats</div>
                      <div className="text-xs text-slate-500">View archived conversations</div>
                    </div>
                  </div>
                  <button
                    onClick={handleShowArchived}
                    className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
                  >
                    See Chats
                  </button>
                </div>

                {/* Dark / Light Mode */}
                <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 flex items-center justify-center bg-white rounded-lg shadow-sm">
                      <Palette className="w-5 h-5 text-slate-600" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-800">Dark / Light</div>
                      <div className="text-xs text-slate-500">Switch theme</div>
                    </div>
                  </div>
                  <button
                    onClick={() => setDarkMode(!darkMode)}
                    className={`relative w-12 h-6 rounded-full transition-colors ${darkMode ? 'bg-indigo-600' : 'bg-slate-300'}`}
                  >
                    <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${darkMode ? 'left-7' : 'left-1'}`} />
                  </button>
                </div>

                {/* Log Out */}
                <div className="pt-4 border-t border-slate-200">
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-3 px-4 py-3 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <span className="text-sm font-medium">Log Out</span>
                  </button>
                </div>
              </div>
            ) : activeTab === 'llm' ? (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-slate-800">Model Configuration</h3>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${llmConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                    <span className="text-xs text-slate-500">{llmConnected ? 'Connected' : 'Disconnected'}</span>
                  </div>
                </div>

                {/* Preset Provider */}
                <div>
                  <label className="block text-xs text-slate-500 mb-2">Quick Presets</label>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(PRESET_PROVIDERS).map(([key, preset]) => (
                      <button
                        key={key}
                        onClick={() => handlePresetChange(key)}
                        className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                          selectedPreset === key
                            ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                            : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                        }`}
                      >
                        {preset.name}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Provider */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Provider</label>
                  <select
                    value={llmConfig.provider}
                    onChange={e => setLlmConfig({ ...llmConfig, provider: e.target.value as 'ollama' | 'lmstudio' | 'deepseek' | 'zhipu' | 'minimax' })}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="ollama">Ollama (本地)</option>
                    <option value="lmstudio">LM Studio (本地)</option>
                    <option value="deepseek">DeepSeek (云服务)</option>
                    <option value="zhipu">智谱 GLM (云服务)</option>
                    <option value="minimax">MiniMax (云服务)</option>
                  </select>
                </div>

                {/* Base URL */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Base URL</label>
                  <input
                    type="text"
                    value={llmConfig.base_url}
                    onChange={e => setLlmConfig({ ...llmConfig, base_url: e.target.value })}
                    placeholder="http://localhost:11434"
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                {/* Model */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Model Name</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={llmConfig.model}
                      onChange={e => setLlmConfig({ ...llmConfig, model: e.target.value })}
                      placeholder="qwen3:latest"
                      list="available-models"
                      className="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <button
                      onClick={loadLlmConfig}
                      className="px-3 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50"
                      title="Refresh models"
                    >
                      <Loader2 className="w-4 h-4" />
                    </button>
                  </div>
                  <datalist id="available-models">
                    {availableModels.map(m => <option key={m} value={m} />)}
                  </datalist>
                  {availableModels.length > 0 && (
                    <p className="mt-1 text-xs text-slate-400">
                      Available: {availableModels.slice(0, 5).join(', ')}
                      {availableModels.length > 5 && ` +${availableModels.length - 5} more`}
                    </p>
                  )}
                </div>

                {/* Temperature */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Temperature: {llmConfig.temperature}</label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={llmConfig.temperature}
                    onChange={e => setLlmConfig({ ...llmConfig, temperature: parseFloat(e.target.value) })}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-slate-400 mt-1">
                    <span>Precise</span>
                    <span>Creative</span>
                  </div>
                </div>

                {/* Timeout */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Timeout (seconds)</label>
                  <input
                    type="number"
                    value={llmConfig.timeout}
                    onChange={e => setLlmConfig({ ...llmConfig, timeout: parseInt(e.target.value) || 120 })}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                {/* API Key */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">API Key (for cloud providers)</label>
                  <input
                    type="password"
                    value={llmConfig.api_key || ''}
                    onChange={e => setLlmConfig({ ...llmConfig, api_key: e.target.value })}
                    placeholder="sk-..."
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                {/* Actions */}
                <div className="flex gap-3 pt-4">
                  <button
                    onClick={handleTestConnection}
                    disabled={testingConnection}
                    className="flex items-center gap-2 px-4 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
                  >
                    {testingConnection && <Loader2 className="w-4 h-4 animate-spin" />}
                    Test Connection
                  </button>
                  <button
                    onClick={handleSaveLlmConfig}
                    disabled={llmLoading}
                    className="flex items-center gap-2 px-4 py-2 text-sm text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
                  >
                    {llmLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                    Save Configuration
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-slate-800">Database Connections</h3>
                  <button
                    onClick={handleAddDb}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                    Add Database
                  </button>
                </div>

                {/* Add New Database Form */}
                {isAddingDb && (
                  <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Connection Name</label>
                        <input
                          type="text"
                          value={newDb.name}
                          onChange={e => setNewDb({ ...newDb, name: e.target.value })}
                          placeholder="My Database"
                          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Database Type</label>
                        <select
                          value={newDb.type}
                          onChange={e => setNewDb({ ...newDb, type: e.target.value as any })}
                          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        >
                          <option value="postgresql">PostgreSQL</option>
                          <option value="mysql">MySQL</option>
                          <option value="mongodb">MongoDB</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Host</label>
                        <input
                          type="text"
                          value={newDb.host}
                          onChange={e => setNewDb({ ...newDb, host: e.target.value })}
                          placeholder="localhost"
                          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Port</label>
                        <input
                          type="text"
                          value={newDb.port}
                          onChange={e => setNewDb({ ...newDb, port: e.target.value })}
                          placeholder={newDb.type === 'postgresql' ? '5432' : newDb.type === 'mysql' ? '3306' : '27017'}
                          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Database Name</label>
                        <input
                          type="text"
                          value={newDb.database}
                          onChange={e => setNewDb({ ...newDb, database: e.target.value })}
                          placeholder="mydb"
                          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Username</label>
                        <input
                          type="text"
                          value={newDb.username}
                          onChange={e => setNewDb({ ...newDb, username: e.target.value })}
                          placeholder="root"
                          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="block text-xs text-slate-500 mb-1">Password</label>
                        <input
                          type="password"
                          value={newDb.password}
                          onChange={e => setNewDb({ ...newDb, password: e.target.value })}
                          placeholder="••••••••"
                          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                    </div>
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setIsAddingDb(false)}
                        className="px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleSaveNewDb}
                        className="px-3 py-1.5 text-sm text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                )}

                {/* Database List */}
                <div className="space-y-3">
                  {databases.map((db) => (
                    <div key={db.id} className="p-4 bg-slate-50 rounded-lg">
                      {editingDb?.id === db.id ? (
                        <div className="space-y-3">
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label className="block text-xs text-slate-500 mb-1">Connection Name</label>
                              <input
                                type="text"
                                value={editingDb.name}
                                onChange={e => setEditingDb({ ...editingDb, name: e.target.value })}
                                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-slate-500 mb-1">Database Type</label>
                              <select
                                value={editingDb.type}
                                onChange={e => setEditingDb({ ...editingDb, type: e.target.value as any })}
                                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              >
                                <option value="postgresql">PostgreSQL</option>
                                <option value="mysql">MySQL</option>
                                <option value="mongodb">MongoDB</option>
                              </select>
                            </div>
                            <div>
                              <label className="block text-xs text-slate-500 mb-1">Host</label>
                              <input
                                type="text"
                                value={editingDb.host}
                                onChange={e => setEditingDb({ ...editingDb, host: e.target.value })}
                                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-slate-500 mb-1">Port</label>
                              <input
                                type="text"
                                value={editingDb.port}
                                onChange={e => setEditingDb({ ...editingDb, port: e.target.value })}
                                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-slate-500 mb-1">Database Name</label>
                              <input
                                type="text"
                                value={editingDb.database}
                                onChange={e => setEditingDb({ ...editingDb, database: e.target.value })}
                                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-slate-500 mb-1">Username</label>
                              <input
                                type="text"
                                value={editingDb.username}
                                onChange={e => setEditingDb({ ...editingDb, username: e.target.value })}
                                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              />
                            </div>
                            <div className="col-span-2">
                              <label className="block text-xs text-slate-500 mb-1">Password</label>
                              <input
                                type="password"
                                value={editingDb.password}
                                onChange={e => setEditingDb({ ...editingDb, password: e.target.value })}
                                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              />
                            </div>
                          </div>
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() => setEditingDb(null)}
                              className="px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={handleSaveEditDb}
                              className="px-3 py-1.5 text-sm text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors flex items-center gap-1"
                            >
                              <Check className="w-4 h-4" />
                              Save
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 flex items-center justify-center bg-white rounded-lg shadow-sm">
                              <Server className="w-5 h-5 text-slate-600" />
                            </div>
                            <div>
                              <div className="text-sm font-medium text-slate-800">{db.name}</div>
                              <div className="text-xs text-slate-500">
                                {dbTypeLabels[db.type]} · {db.host}:{db.port}/{db.database}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handleEditDb(db)}
                              className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDeleteDb(db.id)}
                              className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer - Back button for archived */}
        {showArchived && (
          <div className="px-6 py-3 border-t border-slate-200 bg-slate-50/50">
            <button
              onClick={handleBack}
              className="px-4 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-white transition-colors"
            >
              Back to Settings
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SettingsPopup;