import React, { useState, useRef } from 'react'
import { Upload, X, FileText, FileSpreadsheet, File, Check, AlertCircle } from 'lucide-react'
import { knowledgeApi } from '../api/knowledge'

interface KnowledgeUploadProps {
  currentPath?: string
  onUploadComplete?: () => void
  onClose?: () => void
}

interface UploadFile {
  file: File
  status: 'pending' | 'uploading' | 'success' | 'error'
  error?: string
}

const ACCEPTED_TYPES = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain',
]

const ACCEPTED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt']

export const KnowledgeUpload: React.FC<KnowledgeUploadProps> = ({
  currentPath = '',
  onUploadComplete,
  onClose,
}) => {
  const [isDragging, setIsDragging] = useState(false)
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const getFileIcon = (file: File) => {
    if (file.type.includes('spreadsheet') || file.name.match(/\.(xls|xlsx)$/i)) {
      return <FileSpreadsheet className="w-8 h-8 text-emerald-500" />
    }
    if (file.type.includes('pdf')) {
      return <File className="w-8 h-8 text-red-500" />
    }
    return <FileText className="w-8 h-8 text-blue-500" />
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    addFiles(files)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files)
      addFiles(files)
    }
  }

  const addFiles = (files: File[]) => {
    const validFiles = files.filter((file) => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase()
      return ACCEPTED_EXTENSIONS.includes(ext) || ACCEPTED_TYPES.includes(file.type)
    })

    const newFiles: UploadFile[] = validFiles.map((file) => ({
      file,
      status: 'pending',
    }))

    setUploadFiles((prev) => [...prev, ...newFiles])
  }

  const removeFile = (index: number) => {
    setUploadFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const uploadFiles_ = async () => {
    setIsUploading(true)

    for (let i = 0; i < uploadFiles.length; i++) {
      if (uploadFiles[i].status !== 'pending') continue

      setUploadFiles((prev) =>
        prev.map((f, idx) => (idx === i ? { ...f, status: 'uploading' } : f))
      )

      try {
        const result = await knowledgeApi.uploadFile(uploadFiles[i].file, currentPath)
        if (result.success) {
          setUploadFiles((prev) =>
            prev.map((f, idx) => (idx === i ? { ...f, status: 'success' } : f))
          )
        } else {
          setUploadFiles((prev) =>
            prev.map((f, idx) =>
              idx === i ? { ...f, status: 'error', error: result.error } : f
            )
          )
        }
      } catch (err) {
        setUploadFiles((prev) =>
          prev.map((f, idx) =>
            idx === i ? { ...f, status: 'error', error: 'Upload failed' } : f
          )
        )
      }
    }

    setIsUploading(false)
    onUploadComplete?.()
  }

  const handleUpload = () => {
    if (uploadFiles.some((f) => f.status === 'pending')) {
      uploadFiles_()
    }
  }

  const pendingCount = uploadFiles.filter((f) => f.status === 'pending').length
  const hasFiles = uploadFiles.length > 0

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-lg overflow-hidden">
      <div className="p-4 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-slate-800">Upload Files</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Supports PDF, Word, Excel, TXT
          </p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-slate-100 rounded-md transition-colors"
          >
            <X className="w-4 h-4 text-slate-400" />
          </button>
        )}
      </div>

      <div className="p-4 space-y-4">
        {!hasFiles ? (
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`
              border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
              ${isDragging
                ? 'border-indigo-500 bg-indigo-50'
                : 'border-slate-200 hover:border-indigo-300 hover:bg-slate-50'
              }
            `}
          >
            <Upload className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-slate-600 mb-1">
              Drag and drop files here, or click to browse
            </p>
            <p className="text-xs text-slate-400">
              PDF, DOC, DOCX, XLS, XLSX, TXT
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={ACCEPTED_EXTENSIONS.join(',')}
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs text-slate-500">
                {uploadFiles.length} file{uploadFiles.length > 1 ? 's' : ''} selected
              </span>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-xs text-indigo-600 hover:text-indigo-700"
              >
                Add more
              </button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={ACCEPTED_EXTENSIONS.join(',')}
                onChange={handleFileSelect}
                className="hidden"
              />
            </div>

            <div className="max-h-48 overflow-y-auto space-y-2">
              {uploadFiles.map((uf, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg"
                >
                  {getFileIcon(uf.file)}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-700 truncate">{uf.file.name}</p>
                    <p className="text-xs text-slate-400">
                      {(uf.file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  {uf.status === 'uploading' && (
                    <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                  )}
                  {uf.status === 'success' && (
                    <Check className="w-5 h-5 text-emerald-500" />
                  )}
                  {uf.status === 'error' && (
                    <div className="flex items-center gap-1">
                      <AlertCircle className="w-4 h-4 text-red-500" />
                      <span className="text-xs text-red-500">{uf.error}</span>
                    </div>
                  )}
                  {uf.status === 'pending' && (
                    <button
                      onClick={() => removeFile(idx)}
                      className="p-1 hover:bg-slate-200 rounded transition-colors"
                    >
                      <X className="w-4 h-4 text-slate-400" />
                    </button>
                  )}
                </div>
              ))}
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={() => setUploadFiles([])}
                className="flex-1 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Clear
              </button>
              <button
                onClick={handleUpload}
                disabled={isUploading || pendingCount === 0}
                className="flex-1 px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isUploading ? 'Uploading...' : `Upload ${pendingCount} file${pendingCount > 1 ? 's' : ''}`}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default KnowledgeUpload