import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Plus,
  RefreshCw,
  Maximize,
  RotateCcw,
  CheckCircle2,
  Database,
  Table as TableIcon,
  AlertCircle,
  ChevronDown,
  X,
  Eye,
  Loader2,
  Trash2,
} from 'lucide-react';
import { modelsApi, type DatabaseInfo, type TableDataResponse } from '../api/models';
import ExcelImport from './ExcelImport';
import { useDb } from '../context/DbContext';

interface NewViewDialogProps {
  tables: { name: string; columns: string[] }[];
  onClose: () => void;
  onCreated: () => void;
}

const NewViewDialog: React.FC<NewViewDialogProps> = ({ tables, onClose, onCreated }) => {
  const [name, setName] = useState('');
  const [sourceTable, setSourceTable] = useState('');
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [filterColumn, setFilterColumn] = useState('');
  const [filterValue, setFilterValue] = useState('');
  const [saving, setSaving] = useState(false);

  const sourceColumns = tables.find(t => t.name === sourceTable)?.columns || [];

  const handleColumnToggle = (col: string) => {
    setSelectedColumns(prev =>
      prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]
    );
  };

  const handleCreate = async () => {
    if (!name || !sourceTable || selectedColumns.length === 0) return;
    setSaving(true);
    try {
      // Escape single quotes to prevent SQL injection
      const escapedFilterValue = filterValue.replace(/'/g, "''");
      let definition = `SELECT ${selectedColumns.join(', ')} FROM "${sourceTable}"`;
      if (filterColumn && filterValue) {
        definition += ` WHERE "${filterColumn}" = '${escapedFilterValue}'`;
      }
      await modelsApi.createView(name, definition);
      onCreated();
    } catch (e) {
      console.error('Failed to create view', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-[500px] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
          <h3 className="text-sm font-semibold text-slate-800">Create View</h3>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded transition-colors">
            <X className="w-4 h-4 text-slate-500" />
          </button>
        </div>
        <div className="p-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">View Name</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. high_value_customers"
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Source Table</label>
            <select
              value={sourceTable}
              onChange={e => { setSourceTable(e.target.value); setSelectedColumns([]); setFilterColumn(''); }}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">Select a table...</option>
              {tables.map(t => (
                <option key={t.name} value={t.name}>{t.name}</option>
              ))}
            </select>
          </div>
          {sourceColumns.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Columns</label>
              <div className="flex flex-wrap gap-2">
                {sourceColumns.map(col => (
                  <button
                    key={col}
                    onClick={() => handleColumnToggle(col)}
                    className={`px-2 py-1 text-xs rounded border transition-colors ${selectedColumns.includes(col) ? 'bg-indigo-100 border-indigo-300 text-indigo-700' : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'}`}
                  >
                    {col}
                  </button>
                ))}
              </div>
            </div>
          )}
          {selectedColumns.length > 0 && (
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="block text-xs font-medium text-slate-600 mb-1">Filter Column (optional)</label>
                <select
                  value={filterColumn}
                  onChange={e => setFilterColumn(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">No filter</option>
                  {sourceColumns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
              </div>
              {filterColumn && (
                <div className="flex-1">
                  <label className="block text-xs font-medium text-slate-600 mb-1">Filter Value</label>
                  <input
                    type="text"
                    value={filterValue}
                    onChange={e => setFilterValue(e.target.value)}
                    placeholder="e.g. A区"
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              )}
            </div>
          )}
          <div className="pt-2 text-xs text-slate-500">
            <div className="font-medium mb-1">Generated SQL:</div>
            <code className="block bg-slate-50 p-2 rounded text-[11px] overflow-x-auto">
              {name && sourceTable && selectedColumns.length > 0
                ? `CREATE VIEW ${name} AS SELECT ${selectedColumns.join(', ')} FROM ${sourceTable}${filterColumn && filterValue ? ` WHERE ${filterColumn} = '${filterValue}'` : ''}`
                : 'SELECT ... FROM ...'}
            </code>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-4 py-3 border-t border-slate-200 bg-slate-50/50">
          <button onClick={onClose} className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">Cancel</button>
          <button
            onClick={handleCreate}
            disabled={!name || !sourceTable || selectedColumns.length === 0 || saving}
            className="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Creating...' : 'Create View'}
          </button>
        </div>
      </div>
    </div>
  );
};

interface ViewItem {
  name: string;
  definition: string;
}

interface ModelCardProps {
  name: string;
  columns: string[];
  x: number;
  y: number;
  onPreview: (table: string) => void;
}

const ModelCard: React.FC<ModelCardProps> = ({ name, columns, x, y, onPreview }) => {
  return (
    <div
      className="absolute bg-white border border-slate-200 rounded-lg shadow-sm w-56 overflow-hidden select-none"
      style={{ left: x, top: y }}
    >
      <div className="bg-[#4c3e91] px-3 py-1.5 flex items-center gap-2">
        <TableIcon className="w-3.5 h-3.5 text-white/80" />
        <span className="text-[11px] font-medium text-white truncate">{name}</span>
        <button onClick={() => onPreview(name)} className="ml-auto p-0.5 rounded hover:bg-white/20 transition-colors">
          <Eye className="w-3 h-3 text-white/60" />
        </button>
      </div>
      <div className="p-2 space-y-3">
        <div>
          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1 px-1">Columns</div>
          <div className="space-y-0.5">
            {columns.slice(0, 8).map((col, i) => (
              <div key={i} className="flex items-center gap-2 px-1 py-0.5 hover:bg-slate-50 rounded transition-colors group">
                <div className="w-3 h-3 flex items-center justify-center text-[8px] font-bold text-slate-400 border border-slate-200 rounded shrink-0 group-hover:border-indigo-200 group-hover:text-indigo-400">
                  {col.toLowerCase().includes('id') ? 'PK' : 'T'}
                </div>
                <span className="text-[10px] text-slate-600 truncate">{col}</span>
              </div>
            ))}
            {columns.length > 8 && (
              <div className="text-[9px] text-slate-400 pl-6">+{columns.length - 8} more</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// --- Sidebar ---

interface ModelingSidebarProps {
  onConnect: () => void;
}

export const ModelingSidebar: React.FC<ModelingSidebarProps> = ({ onConnect }) => {
  const { isConnected, setIsConnected } = useDb();
  const [databases, setDatabases] = useState<DatabaseInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedDb, setExpandedDb] = useState<string | null>(null);
  const [views, setViews] = useState<ViewItem[]>([]);
  const [showNewViewDialog, setShowNewViewDialog] = useState(false);
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchSchema = useCallback(async () => {
    if (!isConnected) return;
    setLoading(true);
    try {
      const resp = await modelsApi.getSchema();
      setDatabases(resp.databases || []);
      if (resp.databases?.length) setExpandedDb(resp.databases[0].id);
    } catch (e) {
      console.error('Failed to load schema', e);
    } finally {
      setLoading(false);
    }
  }, [isConnected]);

  const fetchViews = useCallback(async () => {
    if (!isConnected) return;
    try {
      const resp = await modelsApi.getViews();
      setViews(resp.views || []);
    } catch (e) {
      console.error('Failed to load views', e);
    }
  }, [isConnected]);

  useEffect(() => {
    if (isConnected) {
      fetchSchema();
      fetchViews();
    }
  }, [isConnected, fetchSchema, fetchViews]);

  // Auto-refresh schema every 30 seconds when connected
  useEffect(() => {
    if (isConnected) {
      refreshIntervalRef.current = setInterval(() => {
        fetchSchema();
      }, 30000);
    }
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [isConnected, fetchSchema]);

  const handleConnect = () => {
    setIsConnected(true);
    onConnect();
  };

  const tableCount = databases.reduce((acc, db) => acc + db.tables.length, 0);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="p-4 space-y-4 overflow-y-auto flex-1">
        <div>
          <div className="flex items-center justify-between mb-3 px-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700">Models</span>
              {isConnected && (
                <span className="text-[10px] text-slate-400 font-medium bg-slate-100 px-1.5 py-0.5 rounded-full">
                  ({tableCount})
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <RefreshCw
                className={`w-3.5 h-3.5 cursor-pointer hover:text-indigo-500 transition-colors ${!isConnected ? 'opacity-50 cursor-not-allowed' : ''} ${loading ? 'animate-spin' : ''}`}
                onClick={fetchSchema}
              />
              <button
                onClick={handleConnect}
                className="flex items-center gap-1 px-2 py-1 bg-indigo-600 border border-indigo-500 rounded-md text-[10px] font-medium text-white hover:bg-indigo-700 transition-colors shadow-sm"
              >
                <Plus className="w-3 h-3" />
                {isConnected ? 'Refresh' : 'Connect DB'}
              </button>
            </div>
          </div>

          <div className="max-h-64 overflow-y-auto space-y-0.5 pr-1">
            {isConnected ? (
              loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
                </div>
              ) : (
                databases.map((db) => (
                  <div key={db.id} className="space-y-0.5">
                    <div
                      onClick={() => setExpandedDb(expandedDb === db.id ? null : db.id)}
                      className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-indigo-50/50 border border-indigo-100/50 transition-all cursor-pointer group"
                    >
                      <ChevronDown
                        className={`w-3 h-3 text-indigo-500 transition-transform ${expandedDb === db.id ? '' : '-rotate-90'}`}
                      />
                      <Database className="w-3.5 h-3.5 text-indigo-500" />
                      <span className="text-xs font-medium text-slate-700 truncate">{db.name}</span>
                    </div>
                    {expandedDb === db.id && (
                      <div className="pl-4 space-y-0.5 mt-1">
                        {db.tables
                          .filter(tbl =>
                            !tbl.name.startsWith('memory_') &&
                            !tbl.name.startsWith('metrics_') &&
                            !['skill_definitions', 'skill_health', 'alembic_version', 'chats', 'users', 'api_call_logs', 'api_logs'].includes(tbl.name)
                          )
                          .map((tbl) => (
                          <div
                            key={tbl.name}
                            className="flex items-center justify-between gap-2 px-2 py-1 rounded-md hover:bg-white hover:shadow-sm transition-all cursor-pointer group"
                          >
                            <div className="flex items-center gap-2 overflow-hidden">
                              <TableIcon className="w-3 h-3 text-slate-400 group-hover:text-indigo-500 shrink-0" />
                              <span className="text-[11px] text-slate-600 truncate">{tbl.name}</span>
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              <span className="text-[9px] text-slate-400 font-medium">{tbl.row_count}</span>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  console.log('Delete rows clicked for:', tbl.name);
                                  if (confirm(`Delete all rows in "${tbl.name}"?`)) {
                                    console.log('Confirmed, calling API...');
                                    modelsApi.deleteTableRows(tbl.name).then(() => fetchSchema());
                                  }
                                }}
                                className="p-1.5 rounded hover:bg-blue-100 transition-all"
                                title="Delete rows"
                              >
                                <Trash2 className="w-3.5 h-3.5 text-blue-500" />
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  console.log('Delete table clicked for:', tbl.name);
                                  if (confirm(`Delete table "${tbl.name}" completely? This cannot be undone.`)) {
                                    console.log('Confirmed, calling API...');
                                    modelsApi.deleteTable(tbl.name).then(() => fetchSchema());
                                  }
                                }}
                                className="p-1.5 rounded hover:bg-red-100 transition-all"
                                title="Delete table"
                              >
                                <X className="w-3.5 h-3.5 text-red-500" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )
            ) : (
              <div className="flex flex-col items-center justify-center py-8 px-4 text-center space-y-2 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50">
                <Database className="w-8 h-8 text-slate-300" />
                <p className="text-[10px] text-slate-400 font-medium">No database connected</p>
                <button onClick={onConnect} className="text-[10px] text-indigo-600 font-semibold hover:underline">
                  Connect now
                </button>
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-3 px-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700">Views</span>
              <span className="text-[10px] text-slate-400 font-medium bg-slate-100 px-1.5 py-0.5 rounded-full">({views.length})</span>
            </div>
            <button
              onClick={() => setShowNewViewDialog(true)}
              className={`flex items-center gap-1 px-2 py-1 bg-white border border-slate-200 rounded-md text-[10px] font-medium text-slate-600 hover:bg-slate-50 transition-colors shadow-sm ${!isConnected ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Plus className="w-3 h-3" />
              New
            </button>
          </div>
          <div className="max-h-40 overflow-y-auto space-y-0.5 pr-1">
            {views.length === 0 ? (
              <div className="text-xs text-slate-400 px-2 italic">No views</div>
            ) : (
              views.map((view) => (
                <div
                  key={view.name}
                  className="flex items-center justify-between gap-2 px-2 py-1 rounded-md hover:bg-white hover:shadow-sm transition-all cursor-pointer group"
                >
                  <div className="flex items-center gap-2 overflow-hidden">
                    <Eye className="w-3 h-3 text-slate-400 group-hover:text-indigo-500 shrink-0" />
                    <span className="text-[11px] text-slate-600 truncate">{view.name}</span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`Delete view "${view.name}"?`)) {
                        modelsApi.deleteView(view.name).then(fetchViews);
                      }
                    }}
                    className="p-1.5 rounded hover:bg-red-100 transition-all"
                    title="Delete view"
                  >
                    <X className="w-3 h-3 text-red-500" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-3 px-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700">Import</span>
            </div>
          </div>
          <ExcelImport onComplete={fetchSchema} />
        </div>
        {showNewViewDialog && (
          <NewViewDialog
            tables={databases[0]?.tables.map(t => ({ name: t.name, columns: t.columns })) || []}
            onClose={() => setShowNewViewDialog(false)}
            onCreated={() => { setShowNewViewDialog(false); fetchViews(); }}
          />
        )}
      </div>
    </div>
  );
};

export const ModelingHeaderExtras: React.FC<{ isConnected: boolean }> = ({ isConnected }) => (
  <div className="flex items-center gap-4">
    {isConnected ? (
      <div className="flex items-center gap-1.5 text-green-500">
        <CheckCircle2 className="w-4 h-4" />
        <span className="text-xs font-medium">Synced</span>
      </div>
    ) : (
      <div className="flex items-center gap-1.5 text-slate-400">
        <AlertCircle className="w-4 h-4" />
        <span className="text-xs font-medium">Disconnected</span>
      </div>
    )}
    <button
      disabled={!isConnected}
      className={`px-3 py-1 bg-white/10 text-white text-xs font-medium rounded border border-white/20 transition-colors ${isConnected ? 'hover:bg-white/20' : 'opacity-50 cursor-not-allowed'}`}
    >
      Deploy
    </button>
  </div>
);

// --- Data Preview Panel ---

const DataPreviewPanel: React.FC<{
  table: string;
  onClose: () => void;
}> = ({ table, onClose }) => {
  const [data, setData] = useState<TableDataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const LIMIT = 50;
  const dataRef = useRef<TableDataResponse | null>(null);

  const fetchData = useCallback(async (offset: number, append: boolean = false) => {
    if (append) {
      setIsLoadingMore(true);
    } else {
      setLoading(true);
    }
    try {
      const result = await modelsApi.getTableData(table, LIMIT, offset);
      if (append && dataRef.current) {
        const newData = {
          ...result,
          rows: [...dataRef.current.rows, ...result.rows],
        };
        dataRef.current = newData;
        setData(newData);
      } else {
        dataRef.current = result;
        setData(result);
      }
      setHasMore(result.rows.length >= LIMIT && (append ? (dataRef.current?.total ?? 0) > (offset + LIMIT) : true));
    } catch (e) {
      console.error('Failed to load data', e);
    } finally {
      setLoading(false);
      setIsLoadingMore(false);
    }
  }, [table]);

  useEffect(() => {
    dataRef.current = null;
    setOffset(0);
    setData(null);
    fetchData(0, false);
  }, [table, fetchData]);

  const handleLoadMore = () => {
    if (!data) return;
    const newOffset = offset + LIMIT;
    setOffset(newOffset);
    fetchData(newOffset, true);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-[90vw] max-w-6xl max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
          <h3 className="text-sm font-semibold text-slate-800">
            <span className="text-indigo-600">Table</span> {table}
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded transition-colors">
            <X className="w-4 h-4 text-slate-500" />
          </button>
        </div>
        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
            </div>
          ) : data ? (
            <>
              <div className="text-[11px] text-slate-500 mb-3 flex items-center justify-between">
                <div>
                  Total rows: <span className="font-semibold text-slate-700">{data.total}</span>
                  {' | '}Showing {data.rows.length}
                </div>
                {hasMore && !loading && (
                  <button
                    onClick={handleLoadMore}
                    disabled={isLoadingMore}
                    className="px-3 py-1 text-[10px] font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors disabled:opacity-50"
                  >
                    {isLoadingMore ? 'Loading...' : `Load More (+${Math.min(LIMIT, data.total - data.rows.length)})`}
                  </button>
                )}
              </div>
              <table className="w-full text-xs border border-slate-200 rounded-lg overflow-hidden">
                <thead className="bg-slate-50">
                  <tr>
                    {data.columns.map((col) => (
                      <th key={col} className="px-2 py-1.5 text-left font-semibold text-slate-600 border-b border-slate-200 whitespace-nowrap">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row, i) => (
                    <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50/40'}>
                      {data.columns.map((col) => (
                        <td key={col} className="px-2 py-1 text-slate-700 border-b border-slate-100 max-w-[200px] truncate">
                          {row[col] ?? <span className="text-slate-300 italic">NULL</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {data.rows.length === 0 && (
                    <tr>
                      <td colSpan={data.columns.length} className="px-2 py-8 text-center text-slate-400">
                        No data
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </>
          ) : (
            <div className="py-8 text-center text-slate-400">Failed to load data</div>
          )}
        </div>
      </div>
    </div>
  );
};

// --- Main Page ---

const ModelingPage: React.FC = () => {
  const { isConnected } = useDb();
  const [databases, setDatabases] = useState<DatabaseInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewTable, setPreviewTable] = useState<string | null>(null);
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchSchema = useCallback(async () => {
    if (!isConnected) return;
    setLoading(true);
    try {
      const resp = await modelsApi.getSchema();
      setDatabases(resp.databases || []);
    } catch (e) {
      console.error('Failed to load schema', e);
    } finally {
      setLoading(false);
    }
  }, [isConnected]);

  useEffect(() => {
    fetchSchema();
  }, [fetchSchema]);

  // Auto-refresh schema every 30 seconds when connected
  useEffect(() => {
    if (isConnected) {
      refreshIntervalRef.current = setInterval(fetchSchema, 30000);
    }
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [isConnected, fetchSchema]);

  // Build model cards for the ERD canvas
  const CARD_WIDTH = 240;
  const CARD_HEIGHT = 220;
  const CARD_GAP_X = 40;
  const CARD_GAP_Y = 40;
  const COLUMNS = 4;
  const PADDING = 80;

  const modelCards = isConnected && !loading
    ? (databases[0]?.tables ?? [])
        .filter(tbl =>
            !tbl.name.startsWith('memory_') &&
            !tbl.name.startsWith('metrics_') &&
            !['skill_definitions', 'skill_health', 'alembic_version', 'chats', 'users'].includes(tbl.name)
          )
        .map((tbl, i) => {
        const col = i % COLUMNS;
        const row = Math.floor(i / COLUMNS);
        return {
          name: tbl.name,
          columns: tbl.columns,
          row_count: tbl.row_count,
          x: PADDING + col * (CARD_WIDTH + CARD_GAP_X),
          y: PADDING + row * (CARD_HEIGHT + CARD_GAP_Y),
        };
      })
    : [];

  return (
    <div className="flex-1 relative bg-[#f8f9fb] overflow-hidden">
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.03]"
        style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }}
      />

      <div className="absolute inset-0 overflow-auto p-20">
        {isConnected ? (
          loading ? (
            <div className="h-full flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-slate-400 animate-spin" />
            </div>
          ) : (
            (() => {
              const cols = 4;
              const cardW = 240;
              const cardH = 220;
              const gapX = 40;
              const gapY = 40;
              const pad = 80;
              const totalCols = cols;
              const totalRows = Math.ceil(modelCards.length / totalCols);
              const containerW = pad * 2 + totalCols * cardW + (totalCols - 1) * gapX;
              const containerH = pad * 2 + totalRows * cardH + (totalRows - 1) * gapY;
              return (
                <div className="relative" style={{ width: containerW, height: containerH }}>
                  {modelCards.map((card, i) => (
                    <ModelCard key={i} name={card.name} columns={card.columns} x={card.x} y={card.y} onPreview={setPreviewTable} />
                  ))}
                </div>
              );
            })()
          )
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-6 max-w-md mx-auto">
            <div className="w-20 h-20 bg-white rounded-3xl shadow-xl flex items-center justify-center border border-slate-100">
              <Database className="w-10 h-10 text-slate-200" />
            </div>
            <div className="space-y-2">
              <h2 className="text-xl font-bold text-slate-800">No Data Connected</h2>
              <p className="text-sm text-slate-500 leading-relaxed">
                Click <strong className="text-indigo-600">Connect DB</strong> in the sidebar to load your database schema.
              </p>
            </div>
          </div>
        )}
      </div>

      {isConnected && !loading && (
        <div className="absolute bottom-6 left-6 flex flex-col gap-2">
          <div className="flex flex-col bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
            <button className="p-2 hover:bg-slate-50 transition-colors border-bottom border-slate-100">
              <Plus className="w-4 h-4 text-slate-500" />
            </button>
            <button className="p-2 hover:bg-slate-50 transition-colors border-bottom border-slate-100">
              <div className="w-4 h-px bg-slate-400 mx-auto"></div>
            </button>
            <button className="p-2 hover:bg-slate-50 transition-colors border-bottom border-slate-100">
              <Maximize className="w-4 h-4 text-slate-500" />
            </button>
            <button className="p-2 hover:bg-slate-50 transition-colors">
              <RotateCcw className="w-4 h-4 text-slate-500" />
            </button>
          </div>
        </div>
      )}

      {isConnected && !loading && (
        <div className="absolute bottom-6 right-6 w-48 h-32 bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden p-2">
          <div className="w-full h-full bg-slate-50 rounded border border-slate-100 flex flex-wrap gap-1 p-2 opacity-50">
            {modelCards.slice(0, 12).map((_, i) => (
              <div key={i} className="w-4 h-6 bg-slate-300 rounded-sm"></div>
            ))}
          </div>
        </div>
      )}

      {previewTable && <DataPreviewPanel table={previewTable} onClose={() => setPreviewTable(null)} />}
    </div>
  );
};

export default ModelingPage;
