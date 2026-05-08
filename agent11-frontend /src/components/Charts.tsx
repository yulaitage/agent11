import { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';
import { Bar, Pie } from 'react-chartjs-2';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

export interface ChartData {
  labels: string[];
  datasets: {
    label: string;
    data: number[];
    backgroundColor?: string[];
    borderColor?: string[];
    borderWidth?: number;
  }[];
}

interface BarChartProps {
  title: string;
  data: ChartData;
  horizontal?: boolean;
  height?: number;
}

export function BarChart({ title, data, horizontal = false, height = 300 }: BarChartProps) {
  const options = useMemo(() => ({
    indexAxis: horizontal ? 'y' as const : 'x' as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: !!title,
        text: title,
        font: { size: 14, weight: 'bold' as const },
      },
    },
    scales: horizontal ? {
      x: { grid: { display: true } },
      y: { grid: { display: false } },
    } : {
      x: { grid: { display: false } },
      y: { grid: { display: true } },
    },
  }), [horizontal, title]);

  return (
    <div style={{ height }}>
      <Bar data={data} options={options} />
    </div>
  );
}

interface PieChartProps {
  title: string;
  data: ChartData;
  height?: number;
}

export function PieChart({ title, data, height = 300 }: PieChartProps) {
  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right' as const,
      },
      title: {
        display: !!title,
        text: title,
        font: { size: 14, weight: 'bold' as const },
      },
    },
  }), [title]);

  // Ensure we have colors for pie chart
  const chartData = {
    ...data,
    datasets: data.datasets.map(ds => ({
      ...ds,
      backgroundColor: ds.backgroundColor || [
        '#4c3e91', '#6366f1', '#8b5cf6', '#a78bfa',
        '#c4b5fd', '#7c3aed', '#3b82f6', '#06b6d4',
      ],
    })),
  };

  return (
    <div style={{ height }}>
      <Pie data={chartData} options={options} />
    </div>
  );
}

export function transformTableDataToChart(
  tableData: Record<string, any>[],
  labelField: string,
  valueField: string,
  chartType: 'bar' | 'pie' = 'bar'
): ChartData {
  if (!tableData || tableData.length === 0) {
    return { labels: [], datasets: [{ label: '', data: [] }] };
  }

  const labels = tableData.map(row => String(row[labelField] || ''));
  const values = tableData.map(row => Number(row[valueField] || 0));

  return {
    labels,
    datasets: [{
      label: valueField,
      data: values,
    }],
  };
}