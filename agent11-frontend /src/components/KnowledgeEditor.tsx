import React, { useState, useEffect, useRef } from 'react'
import { Save, Edit3, X, Check, FileText, Clock, Tag } from 'lucide-react'
import { knowledgeApi, KnowledgeFile } from '../api/knowledge'

interface KnowledgeEditorProps {
  file: KnowledgeFile | null
  onSave?: (filename: string, content: string) => void
}

export const KnowledgeEditor: React.FC<KnowledgeEditorProps> = ({ file, onSave }) => {
  const [isEditing, setIsEditing] = useState(false)
  const [content, setContent] = useState('')
  const [originalContent, setOriginalContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (file && !file.isFolder) {
      loadFileContent(file.filename)
    }
  }, [file])

  const loadFileContent = async (filename: string) => {
    try {
      setError(null)
      const result = await knowledgeApi.getFile(filename)
      if (result.success && result.data) {
        setContent(result.data.content || '')
        setOriginalContent(result.data.content || '')
      } else {
        setError(result.error || 'Failed to load file')
      }
    } catch (err) {
      setError('Failed to load file')
    }
    setIsEditing(false)
  }

  const handleSave = async () => {
    if (!file) return

    setIsSaving(true)
    try {
      const result = await knowledgeApi.updateFile(file.filename, content)
      if (result.success) {
        setOriginalContent(content)
        setIsEditing(false)
        onSave?.(file.filename, content)
      } else {
        setError(result.error || 'Failed to save')
      }
    } catch (err) {
      setError('Failed to save file')
    }
    setIsSaving(false)
  }

  const handleCancel = () => {
    setContent(originalContent)
    setIsEditing(false)
    setError(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 's' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleSave()
    }
    if (e.key === 'Escape') {
      handleCancel()
    }
  }

  const hasChanges = content !== originalContent

  if (!file) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50/30">
        <div className="text-center">
          <FileText className="w-12 h-12 mx-auto mb-4 opacity-20" />
          <p className="text-sm text-slate-400">Select a file from the sidebar</p>
        </div>
      </div>
    )
  }

  if (file.isFolder) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50/30">
        <div className="text-center">
          <p className="text-sm text-slate-400">Select a file to view its content</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-white">
      {/* File Header */}
      <div className="px-8 pt-8 pb-4 border-b border-slate-100">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-slate-400">
            <FileText className="w-4 h-4" />
            <span className="text-sm font-medium">{file.filename}</span>
          </div>
          <div className="flex items-center gap-2">
            {error && (
              <span className="text-xs text-red-500 mr-2">{error}</span>
            )}
            {hasChanges && (
              <span className="text-xs text-amber-500 mr-2">Unsaved changes</span>
            )}
            {isEditing ? (
              <>
                <button
                  onClick={handleCancel}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
                >
                  <X className="w-4 h-4" />
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={isSaving || !hasChanges}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <Check className="w-4 h-4" />
                  {isSaving ? 'Saving...' : 'Save'}
                </button>
              </>
            ) : (
              <button
                onClick={() => setIsEditing(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
              >
                <Edit3 className="w-4 h-4" />
                Edit
              </button>
            )}
          </div>
        </div>

        <h1 className="text-3xl font-bold text-slate-800 mb-6">
          {file.filename.replace(/\.md$/, '')}
        </h1>

        <div className="flex flex-wrap gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            <span>Modified: {new Date(file.updatedAt).toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* File Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-4xl w-full mx-auto">
          {isEditing ? (
            <textarea
              ref={textareaRef}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full min-h-[400px] p-4 border border-slate-200 rounded-lg font-mono text-sm text-slate-700 leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              placeholder="Write your content here..."
            />
          ) : (
            <div className="prose prose-slate max-w-none">
              <pre className="whitespace-pre-wrap font-sans text-slate-700 leading-relaxed">
                {content || 'No content'}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default KnowledgeEditor