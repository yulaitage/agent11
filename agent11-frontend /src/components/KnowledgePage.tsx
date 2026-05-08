import React, { useState, useEffect, useRef, DragEvent } from 'react';
import {
  Folder,
  FolderOpen,
  FileText,
  ChevronRight,
  ChevronDown,
  Search,
  Trash2,
  Edit3,
  X,
  Check,
  Upload,
  Clock,
} from 'lucide-react';
import { knowledgeApi, KnowledgeFile } from '../api/knowledge';

interface TreeNode extends KnowledgeFile {
  children?: TreeNode[];
}

export const KnowledgeSidebar = ({
  onSelectFile,
}: {
  onSelectFile: (id: string) => void;
}) => {
  const [expanded, setExpanded] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [treeData, setTreeData] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; node: TreeNode } | null>(null);
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [editingFile, setEditingFile] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [draggedNode, setDraggedNode] = useState<TreeNode | null>(null);
  const [dropTargetFolder, setDropTargetFolder] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadFiles();
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
        setContextMenu(null);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  const loadFiles = async () => {
    try {
      const result = await knowledgeApi.getFiles();
      if (result.success && result.data) {
        setTreeData(buildTree(result.data));
      }
    } catch (err) {
      console.error('Failed to load knowledge:', err);
    } finally {
      setLoading(false);
    }
  };

  const buildTree = (files: KnowledgeFile[]): TreeNode[] => {
    const root: TreeNode[] = [];
    const folderMap = new Map<string, TreeNode>();

    const sortedFiles = [...files].sort((a, b) => a.path.localeCompare(b.path));

    for (const file of sortedFiles) {
      if (file.isFolder) {
        const parts = file.path.split('/').filter(Boolean);
        const folderName = parts[parts.length - 1];
        const node: TreeNode = { ...file, filename: folderName, children: [] };
        folderMap.set(file.path, node);
      }
    }

    for (const file of sortedFiles) {
      const parts = file.path.split('/').filter(Boolean);
      const fileName = parts[parts.length - 1];
      const isFolder = file.isFolder;
      const node: TreeNode = { ...file, filename: fileName, children: isFolder ? [] : undefined };

      if (parts.length === 1) {
        root.push(node);
      } else {
        const parentPath = parts.slice(0, -1).join('/');
        const parent = folderMap.get(parentPath);
        if (parent) {
          parent.children = parent.children || [];
          parent.children.push(node);
        } else {
          root.push(node);
        }
      }
    }
    return root;
  };

  const toggle = async (id: string) => {
    const isExpanded = expanded.includes(id);
    if (isExpanded) {
      setExpanded(prev => prev.filter(x => x !== id));
    } else {
      setExpanded(prev => [...prev, id]);
      // Fetch folder contents if not already loaded
      const existing = treeData.find(n => n.path === id);
      if (existing && (!existing.children || existing.children.length === 0)) {
        try {
          const result = await knowledgeApi.getFiles(id);
          if (result.success && result.data) {
            // Filter out the folder itself and get only children
            const children = result.data.filter((f: KnowledgeFile) => f.path !== id);
            setTreeData(prev => {
              const updateNode = (nodes: TreeNode[]): TreeNode[] => {
                return nodes.map(node => {
                  if (node.path === id) {
                    return { ...node, children: children.map((f: KnowledgeFile) => ({
                      ...f,
                      filename: f.path.split('/').pop() || f.filename,
                      children: f.isFolder ? [] : undefined
                    })) };
                  }
                  if (node.children) {
                    return { ...node, children: updateNode(node.children) };
                  }
                  return node;
                });
              };
              return updateNode(prev);
            });
          }
        } catch (err) {
          console.error('Failed to load folder contents:', err);
        }
      }
    }
  };

  const handleContextMenu = (e: React.MouseEvent, node: TreeNode) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY, node });
  };

  const handleDelete = async (node: TreeNode) => {
    if (!confirm(`Delete "${node.filename}"?`)) return;
    try {
      if (node.isFolder) {
        await knowledgeApi.deleteFolder(node.path);
      } else {
        await knowledgeApi.deleteFile(node.path);
      }
      loadFiles();
    } catch (err) {
      console.error('Delete failed:', err);
    }
    setContextMenu(null);
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) {
      setIsCreatingFolder(false);
      return;
    }
    try {
      await knowledgeApi.createFolder({ name: newFolderName.trim() });
      setNewFolderName('');
      setIsCreatingFolder(false);
      loadFiles();
    } catch (err) {
      console.error('Create folder failed:', err);
    }
  };

  const handleSaveFile = async (filename: string) => {
    try {
      await knowledgeApi.updateFile(filename, editContent);
      setEditingFile(null);
      loadFiles();
    } catch (err) {
      console.error('Save file failed:', err);
    }
  };

  const handleFileEdit = async (node: TreeNode) => {
    try {
      const result = await knowledgeApi.getFile(node.path);
      if (result.success && result.data) {
        setEditingFile(node.filename);
        setEditContent(result.data.content || '');
      }
    } catch (err) {
      console.error('Load file for edit failed:', err);
    }
    setContextMenu(null);
  };

  const filterTree = (nodes: TreeNode[], query: string): TreeNode[] => {
    if (!query) return nodes;
    return nodes.reduce((acc: TreeNode[], node) => {
      if (node.isFolder) {
        const filteredChildren = filterTree(node.children || [], query);
        if (filteredChildren.length > 0) {
          acc.push({ ...node, children: filteredChildren });
        }
      } else if (node.filename.toLowerCase().includes(query.toLowerCase())) {
        acc.push(node);
      }
      return acc;
    }, []);
  };

  const filteredData = filterTree(treeData || [], searchQuery);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    setUploadProgress('Uploading...');

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        setUploadProgress(`Uploading ${file.name}...`);
        const result = await knowledgeApi.uploadFile(file);
        if (result.success) {
          setUploadProgress(`Uploaded ${file.name}`);
        } else {
          setUploadProgress(`Failed: ${file.name}`);
        }
      } catch (err) {
        console.error('Upload failed:', err);
        setUploadProgress(`Error: ${file.name}`);
      }
    }

    setTimeout(() => {
      setIsUploading(false);
      setUploadProgress('');
      loadFiles();
    }, 1000);

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleFileUploadWithFolder = async (e: React.ChangeEvent<HTMLInputElement>, folderPath: string) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    setUploadProgress('Uploading...');

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        setUploadProgress(`Uploading ${file.name} to ${folderPath || 'root'}...`);
        console.log('[upload] folderPath:', folderPath, 'file:', file.name);
        const result = await knowledgeApi.uploadFile(file, folderPath || undefined);
        if (result.success) {
          setUploadProgress(`Uploaded ${file.name}`);
        } else {
          setUploadProgress(`Failed: ${file.name}`);
        }
      } catch (err) {
        console.error('Upload failed:', err);
        setUploadProgress(`Error: ${file.name}`);
      }
    }

    setTimeout(() => {
      setIsUploading(false);
      setUploadProgress('');
      loadFiles();
    }, 1000);

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleCreateFile = async () => {
    const filename = prompt('Enter file name (e.g., myfile.md):');
    if (!filename) return;

    const finalName = filename.endsWith('.md') ? filename : filename + '.md';

    try {
      await knowledgeApi.updateFile(finalName, '# ' + finalName.replace('.md', '') + '\n\nStart writing here...');
      loadFiles();
    } catch (err) {
      console.error('Create file failed:', err);
    }
  };

  const handleDragStart = (e: DragEvent, node: TreeNode) => {
    if (node.isFolder) return;
    e.dataTransfer.setData('text/plain', node.path);
    setDraggedNode(node);
  };

  const handleDragOver = (e: DragEvent, node: TreeNode) => {
    if (!node.isFolder) return;
    e.preventDefault();
    setDropTargetFolder(node.path);
  };

  const handleDragLeave = () => {
    setDropTargetFolder(null);
  };

  const handleDrop = async (e: DragEvent, targetFolder: TreeNode) => {
    e.preventDefault();
    setDropTargetFolder(null);

    if (!draggedNode || targetFolder.isFolder !== true) return;

    const sourcePath = draggedNode.path;
    const targetFolderPath = targetFolder.path;

    if (sourcePath === targetFolderPath) return;

    // Extract filename from path
    const filename = sourcePath.split('/').pop() || sourcePath;
    const newPath = targetFolderPath ? `${targetFolderPath}/${filename}` : filename;

    try {
      // Read file content
      const contentResult = await knowledgeApi.getFile(sourcePath);
      if (!contentResult.success || !contentResult.data) {
        console.error('Failed to read file content');
        return;
      }

      // Create/update file at new location
      await knowledgeApi.updateFile(newPath, contentResult.data.content || '');

      // Delete original file
      await knowledgeApi.deleteFile(sourcePath);

      // Reload files
      loadFiles();
      // Auto-expand target folder to show moved file
      setExpanded(prev => [...prev, targetFolderPath]);
    } catch (err) {
      console.error('Move file failed:', err);
    }

    setDraggedNode(null);
  };

  const TreeItem = ({ node, depth = 0 }: { node: TreeNode; depth?: number }) => {
    const isExpanded = expanded.includes(node.path);
    const isFolder = node.isFolder;
    const isDropTarget = dropTargetFolder === node.path;
    const isDragging = draggedNode?.path === node.path;

    return (
      <div className="space-y-0.5">
        <div
          draggable={!isFolder}
          onDragStart={(e) => handleDragStart(e, node)}
          onDragOver={(e) => handleDragOver(e, node)}
          onDragLeave={handleDragLeave}
          onDrop={(e) => handleDrop(e, node)}
          onClick={() => isFolder ? toggle(node.path) : onSelectFile(node.path)}
          onContextMenu={(e) => handleContextMenu(e, node)}
          className={`flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-white hover:shadow-sm transition-all cursor-pointer group ${isDropTarget ? 'bg-indigo-50 ring-2 ring-indigo-300' : ''} ${isDragging ? 'opacity-50' : ''}`}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
        >
          {isFolder ? (
            <>
              {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
              {isExpanded ? <FolderOpen className="w-4 h-4 text-indigo-500" /> : <Folder className="w-4 h-4 text-slate-400" />}
            </>
          ) : (
            <>
              <div className="w-3.5" />
              <FileText className="w-4 h-4 text-slate-400 group-hover:text-indigo-500" />
            </>
          )}
          <span className={`text-xs flex-1 truncate ${isFolder ? 'font-medium text-slate-700' : 'text-slate-600'}`}>{node.filename}</span>
        </div>
        {isFolder && isExpanded && node.children && (
          <div className="border-l border-slate-200 ml-3.5">
            {node.children.map(child => (
              <TreeItem key={child.path} node={child} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    );
  };

  if (editingFile) {
    return (
      <div className="flex-1 flex flex-col h-full bg-white">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-slate-400" />
            <span className="text-sm font-medium">{editingFile}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setEditingFile(null)}
              className="p-1.5 hover:bg-slate-100 rounded-md transition-colors"
            >
              <X className="w-4 h-4 text-slate-400" />
            </button>
            <button
              onClick={() => handleSaveFile(editingFile)}
              className="p-1.5 hover:bg-slate-100 rounded-md transition-colors"
            >
              <Check className="w-4 h-4 text-emerald-500" />
            </button>
          </div>
        </div>
        <textarea
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
          className="flex-1 p-4 w-full h-full resize-none border-0 focus:outline-none focus:ring-0 font-mono text-sm"
          placeholder="Write your content here..."
        />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden" ref={contextMenuRef}>
      <div className="p-4 space-y-4">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-slate-100 border-none rounded-lg text-xs focus:ring-2 focus:ring-indigo-500/20 transition-all"
          />
        </div>

        <div className="flex items-center justify-between px-1">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Explorer</span>
          <div className="flex items-center gap-1 relative">
            <button
              onClick={() => setIsCreatingFolder(true)}
              className="p-1 hover:bg-white hover:shadow-sm rounded transition-all"
              title="New folder"
            >
              <Folder className="w-3.5 h-3.5 text-slate-400 hover:text-indigo-500" />
            </button>
            <button
              onClick={handleCreateFile}
              className="p-1 hover:bg-white hover:shadow-sm rounded transition-all"
              title="New file"
            >
              <FileText className="w-3.5 h-3.5 text-slate-400 hover:text-indigo-500" />
            </button>
            <div className="relative">
              <button
                onClick={() => setShowUploadMenu(!showUploadMenu)}
                className="p-1 hover:bg-white hover:shadow-sm rounded transition-all"
                title="Upload"
              >
                <Upload className="w-3.5 h-3.5 text-slate-400 hover:text-indigo-500" />
              </button>
              {showUploadMenu && (
                <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-slate-200 py-1 min-w-[160px] z-50">
                  <button
                    onClick={() => {
                      setShowUploadMenu(false);
                      fileInputRef.current?.click();
                    }}
                    className="w-full px-3 py-2 text-xs text-slate-600 hover:bg-slate-50 text-left flex items-center gap-2"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    Upload to Root
                  </button>
                  {treeData.filter(n => n.isFolder).map(folder => (
                    <button
                      key={folder.path}
                      onClick={() => {
                        const folderPath = folder.path;
                        setShowUploadMenu(false);
                        // Use a timeout to ensure the file input is triggered after state update
                        setTimeout(() => {
                          const input = fileInputRef.current;
                          if (input) {
                            input.dataset.folderPath = folderPath;
                            input.click();
                          }
                        }, 50);
                      }}
                      className="w-full px-3 py-2 text-xs text-slate-600 hover:bg-slate-50 text-left flex items-center gap-2"
                    >
                      <Folder className="w-3.5 h-3.5 text-indigo-400" />
                      {folder.filename}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".md,.txt,.pdf,.doc,.docx,.xls,.xlsx"
              onChange={(e) => {
                const targetFolder = (e.target as HTMLInputElement).dataset.folderPath || '';
                handleFileUploadWithFolder(e, targetFolder);
                setShowUploadMenu(false);
                // Clear the dataset after use
                delete (e.target as HTMLInputElement).dataset.folderPath;
              }}
              className="hidden"
            />
          </div>
        </div>

        {isUploading && (
          <div className="text-xs text-indigo-600 text-center py-2">{uploadProgress}</div>
        )}

        {isCreatingFolder && (
          <div className="flex items-center gap-2 px-2 py-1.5 bg-white rounded-md shadow-sm">
            <Folder className="w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Folder name"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreateFolder();
                if (e.key === 'Escape') { setIsCreatingFolder(false); setNewFolderName(''); }
              }}
              className="flex-1 text-xs bg-transparent outline-none"
              autoFocus
            />
            <button onClick={handleCreateFolder} className="p-1 hover:bg-slate-100 rounded">
              <Check className="w-3.5 h-3.5 text-emerald-500" />
            </button>
            <button onClick={() => { setIsCreatingFolder(false); setNewFolderName(''); }} className="p-1 hover:bg-slate-100 rounded">
              <X className="w-3.5 h-3.5 text-slate-400" />
            </button>
          </div>
        )}

        <div className="space-y-1 overflow-y-auto max-h-[calc(100vh-220px)]">
          {loading ? (
            <div className="text-xs text-slate-400 text-center py-4">Loading...</div>
          ) : filteredData.length === 0 ? (
            <div className="text-xs text-slate-400 text-center py-4">
              {isCreatingFolder ? 'Type folder name and press Enter' : 'No files found'}
            </div>
          ) : (
            filteredData.map(node => <TreeItem key={node.path} node={node} />)
          )}
        </div>
      </div>

      {contextMenu && (
        <div
          className="fixed z-50 bg-white rounded-lg shadow-lg border border-slate-200 py-1 min-w-[140px]"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          {!contextMenu.node.isFolder && (
            <button
              onClick={() => handleFileEdit(contextMenu.node)}
              className="w-full px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 text-left flex items-center gap-2"
            >
              <Edit3 className="w-3.5 h-3.5" />
              Edit
            </button>
          )}
          <button
            onClick={() => handleDelete(contextMenu.node)}
            className="w-full px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 text-left flex items-center gap-2"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Delete
          </button>
        </div>
      )}
    </div>
  );
};

export const KnowledgeHeaderExtras = () => null;

const KnowledgePage: React.FC<{ selectedFile?: string | null; onClearSelection?: () => void }> = ({ selectedFile, onClearSelection }) => {
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [fileData, setFileData] = useState<KnowledgeFile | null>(null);
  const [loading, setLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    if (selectedFile) {
      setSelectedFileId(selectedFile);
    }
  }, [selectedFile]);

  useEffect(() => {
    if (selectedFileId) {
      console.log('[KnowledgePage] selectedFileId changed, loading:', selectedFileId);
      loadFile(selectedFileId);
    }
  }, [selectedFileId]);

  const loadFile = async (filename: string) => {
    console.log('[KnowledgePage] loadFile called with:', filename);
    setLoading(true);
    try {
      const result = await knowledgeApi.getFile(filename);
      console.log('[KnowledgePage] getFile result:', result);
      if (result.success && result.data) {
        setFileData(result.data);
      }
    } catch (err) {
      console.error('Failed to load file:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectFile = (id: string) => {
    setSelectedFileId(id);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-white">
      <div className="flex-1 flex overflow-hidden">
        {isUploading && (
          <div className="w-96 p-4 border-r border-slate-200 bg-slate-50">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium">Upload Files</h3>
              <button onClick={() => setIsUploading(false)} className="p-1 hover:bg-slate-200 rounded">
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>
            <div className="text-xs text-slate-500">Upload component placeholder</div>
          </div>
        )}
        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : fileData ? (
          <div className="flex-1 flex flex-col overflow-y-auto bg-white">
            <div className="px-8 pt-8 pb-4 border-b border-slate-100">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2 text-slate-400">
                  <FileText className="w-4 h-4" />
                  <span className="text-sm font-medium">{fileData.filename}</span>
                </div>
              </div>
              <h1 className="text-3xl font-bold text-slate-800 mb-6">{fileData.filename.replace(/\.md$/, '')}</h1>
              <div className="flex flex-wrap gap-4 text-xs text-slate-500">
                <div className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Modified: {fileData.updatedAt ? new Date(fileData.updatedAt).toLocaleString() : 'Unknown'}</span>
                </div>
              </div>
            </div>
            <div className="p-8 max-w-4xl w-full mx-auto">
              <div className="prose prose-slate max-w-none">
                <pre className="whitespace-pre-wrap font-sans text-slate-700 leading-relaxed">
                  {fileData.content || 'No content'}
                </pre>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-400 bg-slate-50/30">
            <div className="text-center">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-20" />
              <p className="text-sm">Select a file from the sidebar to view its content</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgePage;