import { useState, useRef } from 'react';
import { Upload, X, FileSpreadsheet, AlertCircle, Loader2 } from 'lucide-react';
import * as XLSX from 'xlsx';

interface ExcelImportProps {
  onImportSuccess?: (data: any[], fileName: string, sheetName: string) => void;
  onComplete?: () => void;
  onError?: (error: string) => void;
}

interface SheetPreview {
  name: string;
  headers: string[];
  rowCount: number;
  data: Record<string, any>[];
}

export default function ExcelImport({ onImportSuccess, onComplete, onError }: ExcelImportProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<SheetPreview[] | null>(null);
  const [selectedSheet, setSelectedSheet] = useState(0);
  const [fileName, setFileName] = useState('');
  const [rawData, setRawData] = useState<any[][]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFile = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['xlsx', 'xls'].includes(ext || '')) {
      setError('Unsupported file type. Please upload .xlsx or .xls files.');
      return;
    }

    setError('');
    setIsUploading(true);
    setFileName(file.name);

    try {
      const arrayBuffer = await file.arrayBuffer();
      const workbook = XLSX.read(arrayBuffer, { type: 'array' });

      const sheets: SheetPreview[] = workbook.SheetNames.map(name => {
        const sheet = workbook.Sheets[name];
        const data = XLSX.utils.sheet_to_json(sheet, { header: 1 }) as any[][];
        const headers = (data[0] || []).map(h => String(h || ''));
        const rows = data.slice(1).filter(row => row.some(cell => cell !== undefined && cell !== null && cell !== ''));

        // Convert to objects with headers
        const objData = rows.map(row => {
          const obj: Record<string, any> = {};
          headers.forEach((h, i) => {
            obj[h] = row[i];
          });
          return obj;
        });

        return {
          name,
          headers,
          rowCount: rows.length,
          data: objData,
        };
      });

      // Store raw data for import (per sheet)
      setRawData(
        workbook.SheetNames.map(name => {
          const sheet = workbook.Sheets[name];
          return XLSX.utils.sheet_to_json(sheet, { header: 1 }) as any[][];
        })
      );

      setPreview(sheets);
      setSelectedSheet(0);
    } catch (err) {
      setError('Failed to parse Excel file. Please check the file format.');
      setPreview(null);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      await processFile(files[0]);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      await processFile(files[0]);
    }
  };

  const handleImport = async () => {
    if (!preview || preview.length === 0) return;

    const selectedData = preview[selectedSheet];
    if (!selectedData) return;

    try {
      // Convert raw data to proper format with headers
      const headers = selectedData.headers;
      const sheetRawData = rawData[selectedSheet] || [];
      const fullData = sheetRawData.slice(1).map(row => {
        const obj: Record<string, any> = {};
        headers.forEach((h, i) => {
          obj[h] = row[i];
        });
        return obj;
      });

      const response = await fetch('/api/import/excel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fileName,
          sheetName: selectedData.name,
          headers,
          data: fullData,
        }),
      });

      console.log('Import response:', response.status, response.statusText);

      if (response.ok) {
        onImportSuccess?.(fullData, fileName, selectedData.name);
        onComplete?.();
        setIsOpen(false);
        setPreview(null);
        setFileName('');
        setRawData([]);
      } else {
        let errMsg = `Import failed (${response.status})`;
        try {
          const errData = await response.json();
          errMsg = errData.detail || errData.error || errMsg;
          console.error('Import error response:', errData);
        } catch {
          const text = await response.text().catch(() => '');
          console.error('Import error text:', text.substring(0, 500));
        }
        setError(errMsg);
      }
    } catch (err) {
      console.error('Import error:', err);
      setError('Failed to import data. Please try again.');
    }
  };

  const handleClose = () => {
    setIsOpen(false);
    setPreview(null);
    setError('');
    setFileName('');
    setRawData([]);
  };

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition"
        title="Import Excel"
      >
        <FileSpreadsheet size={18} />
        Import Excel
      </button>

      {isOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl p-6 w-full max-w-3xl border border-slate-700">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Import Excel to Database</h3>
              <button
                onClick={handleClose}
                className="p-1 hover:bg-slate-700 rounded-lg transition"
              >
                <X size={20} className="text-slate-400" />
              </button>
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400 text-sm flex items-center gap-2">
                <AlertCircle size={16} />
                {error}
              </div>
            )}

            {!preview ? (
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-12 text-center transition ${
                  dragActive
                    ? 'border-indigo-500 bg-indigo-500/10'
                    : 'border-slate-600 hover:border-slate-500'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={handleFileSelect}
                  className="hidden"
                />

                {isUploading ? (
                  <div className="flex flex-col items-center">
                    <Loader2 size={48} className="animate-spin text-indigo-400 mb-4" />
                    <p className="text-slate-400">Processing...</p>
                  </div>
                ) : (
                  <>
                    <FileSpreadsheet size={48} className="mx-auto text-slate-500 mb-4" />
                    <p className="text-white mb-2">Drag and drop your Excel file here</p>
                    <p className="text-sm text-slate-400 mb-4">or</p>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition"
                    >
                      Browse Files
                    </button>
                    <p className="text-xs text-slate-500 mt-4">Supports .xlsx, .xls</p>
                  </>
                )}
              </div>
            ) : (
              <div>
                {/* File info */}
                <div className="flex items-center gap-3 mb-4 p-3 bg-slate-700/50 rounded-lg">
                  <FileSpreadsheet size={24} className="text-indigo-400" />
                  <div>
                    <p className="text-white font-medium">{fileName}</p>
                    <p className="text-sm text-slate-400">{preview.length} sheet(s)</p>
                  </div>
                </div>

                {/* Sheet selector */}
                {preview.length > 1 && (
                  <div className="flex gap-2 mb-4 flex-wrap">
                    {preview.map((sheet, i) => (
                      <button
                        key={sheet.name}
                        onClick={() => setSelectedSheet(i)}
                        className={`px-3 py-1.5 text-sm rounded-lg transition ${
                          selectedSheet === i
                            ? 'bg-indigo-600 text-white'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                        }`}
                      >
                        {sheet.name} ({sheet.rowCount} rows)
                      </button>
                    ))}
                  </div>
                )}

                {/* Preview table */}
                <div className="overflow-x-auto border border-slate-600 rounded-lg max-h-64 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-700 sticky top-0">
                      <tr>
                        {preview[selectedSheet].headers.map((header, i) => (
                          <th key={i} className="px-4 py-2 text-left text-slate-300 font-medium whitespace-nowrap">
                            {header || `Column ${i + 1}`}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview[selectedSheet].data.slice(0, 10).map((row, i) => (
                        <tr key={i} className="border-t border-slate-700 hover:bg-slate-700/30">
                          {preview[selectedSheet].headers.map((header, j) => (
                            <td key={j} className="px-4 py-2 text-slate-300 whitespace-nowrap">
                              {String(row[header] ?? '')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  Showing {Math.min(10, preview[selectedSheet].rowCount)} of {preview[selectedSheet].rowCount} rows
                </p>

                {/* Action buttons */}
                <div className="flex justify-end gap-3 mt-6">
                  <button
                    onClick={handleClose}
                    className="px-4 py-2 text-slate-300 hover:bg-slate-700 rounded-lg transition"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleImport}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition flex items-center gap-2"
                  >
                    <Upload size={16} />
                    Import to Database
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}