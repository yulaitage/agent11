import { BarChart, PieChart, transformTableDataToChart, type ChartData } from './Charts';

interface DataRow {
  [key: string]: any;
}

interface FlexibleReportProps {
  title: string;
  tableData: DataRow[];
  chartType?: 'bar' | 'pie' | 'both';
  labelField?: string;
  valueField?: string;
  onExportPdf?: () => void;
  onExportExcel?: () => void;
}

export function FlexibleReport({
  title,
  tableData,
  chartType = 'both',
  labelField,
  valueField,
  onExportPdf,
  onExportExcel,
}: FlexibleReportProps) {
  // Auto-detect label and value fields if not specified
  const actualLabelField = labelField || Object.keys(tableData[0] || {})[0] || 'label';
  const actualValueField = valueField || Object.keys(tableData[0] || {})[1] || 'value';

  // Transform to chart data
  const barChartData = transformTableDataToChart(tableData, actualLabelField, actualValueField, 'bar');
  const pieChartData = transformTableDataToChart(tableData, actualLabelField, actualValueField, 'pie');

  // Get table headers
  const headers = tableData.length > 0 ? Object.keys(tableData[0]) : [];

  return (
    <div className="space-y-6 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-800">{title}</h2>
        <div className="flex items-center gap-2">
          {onExportPdf && (
            <button
              onClick={onExportPdf}
              className="px-3 py-1.5 text-sm bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              PDF
            </button>
          )}
          {onExportExcel && (
            <button
              onClick={onExportExcel}
              className="px-3 py-1.5 text-sm bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-2m3 2v-2M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              Excel
            </button>
          )}
        </div>
      </div>

      {/* Charts */}
      {(chartType === 'bar' || chartType === 'both') && (
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <BarChart title="" data={barChartData} height={300} />
        </div>
      )}

      {(chartType === 'pie' || chartType === 'both') && (
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <PieChart title="" data={pieChartData} height={300} />
        </div>
      )}

      {/* Data Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                {headers.map((header, i) => (
                  <th
                    key={i}
                    className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {tableData.map((row, rowIndex) => (
                <tr key={rowIndex} className="hover:bg-slate-50 transition-colors">
                  {headers.map((header, colIndex) => (
                    <td key={colIndex} className="px-4 py-3 text-slate-700">
                      {row[header] !== null && row[header] !== undefined
                        ? String(row[header])
                        : '-'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 text-xs text-slate-500">
          Total: {tableData.length} records
        </div>
      </div>
    </div>
  );
}

// Query result display component
interface QueryResultProps {
  result: {
    answer?: string;
    data?: DataRow[];
    map_data?: any;
    reasoning_chain?: string[];
  };
  onRetry?: () => void;
}

export function QueryResult({ result, onRetry }: QueryResultProps) {
  const tableData = result.data || [];

  return (
    <div className="space-y-4">
      {/* Answer text */}
      {result.answer && (
        <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4">
          <p className="text-slate-700 leading-relaxed">{result.answer}</p>
        </div>
      )}

      {/* Reasoning chain */}
      {result.reasoning_chain && result.reasoning_chain.length > 0 && (
        <details className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <summary className="text-sm font-medium text-slate-600 cursor-pointer">
            Reasoning ({result.reasoning_chain.length} steps)
          </summary>
          <div className="mt-2 space-y-1">
            {result.reasoning_chain.map((step, i) => (
              <div key={i} className="text-xs text-slate-500 pl-4 border-l-2 border-slate-200">
                {step}
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Data display */}
      {tableData.length > 0 && (
        <FlexibleReport title="Query Results" tableData={tableData} chartType="both" />
      )}

      {/* Map data placeholder */}
      {result.map_data && (
        <div className="bg-slate-100 rounded-xl p-4 text-center text-slate-500">
          Map visualization coming soon
        </div>
      )}
    </div>
  );
}