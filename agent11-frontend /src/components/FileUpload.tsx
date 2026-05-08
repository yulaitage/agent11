import { useState, useRef, type ChangeEvent, type DragEvent } from 'react'
import { Upload, X, FileText } from 'lucide-react'
import { knowledgeApi } from '../api/knowledge'

interface FileUploadProps {
  onUploadSuccess?: (filename: string) => void
  className?: string
}

export default function FileUpload({ onUploadSuccess, className = '' }: FileUploadProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDrag = (e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = async (e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    const files = e.dataTransfer.files
    if (files && files[0]) {
      await handleFile(files[0])
    }
  }

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files[0]) {
      await handleFile(files[0])
    }
  }

  const handleFile = async (file: File) => {
    const allowedTypes = [
      'text/plain',
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ]

    if (!allowedTypes.includes(file.type)) {
      setError('Unsupported file type. Please upload .txt, .pdf, or .doc files.')
      return
    }

    setError('')
    setIsUploading(true)

    try {
      const response = await knowledgeApi.uploadFile(file)
      if (response.success && response.data) {
        onUploadSuccess?.(response.data.filename)
        setIsOpen(false)
      } else {
        setError(response.error || 'Upload failed')
      }
    } catch (err) {
      setError('Upload failed. Please try again.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className={`p-2 hover:bg-slate-700 rounded-lg transition ${className}`}
        title="Upload file"
      >
        <Upload size={20} className="text-slate-400" />
      </button>

      {isOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md border border-slate-700">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Upload to Knowledge Base</h3>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 hover:bg-slate-700 rounded-lg transition"
              >
                <X size={20} className="text-slate-400" />
              </button>
            </div>

            <p className="text-sm text-slate-400 mb-4">
              Upload a file to add it to the knowledge base. It will be processed by the agent
              and stored as a markdown file.
            </p>

            {error && (
              <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400 text-sm">
                {error}
              </div>
            )}

            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-xl p-8 text-center transition ${
                dragActive
                  ? 'border-indigo-500 bg-indigo-500/10'
                  : 'border-slate-600 hover:border-slate-500'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.pdf,.doc,.docx"
                onChange={handleFileSelect}
                className="hidden"
              />

              {isUploading ? (
                <div className="flex flex-col items-center">
                  <div className="w-10 h-10 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mb-4" />
                  <p className="text-slate-400">Uploading...</p>
                </div>
              ) : (
                <>
                  <FileText size={48} className="mx-auto text-slate-500 mb-4" />
                  <p className="text-white mb-2">Drag and drop your file here</p>
                  <p className="text-sm text-slate-400 mb-4">or</p>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition"
                  >
                    Browse Files
                  </button>
                  <p className="text-xs text-slate-500 mt-4">Supports .txt, .pdf, .doc, .docx</p>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
