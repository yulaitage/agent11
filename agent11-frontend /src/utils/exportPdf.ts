import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

export function exportChatToPdf(chatTitle: string, messages: Message[]) {
  const doc = new jsPDF()

  // Title
  doc.setFontSize(20)
  doc.text(chatTitle, 14, 22)

  // Date
  doc.setFontSize(10)
  doc.setTextColor(128)
  doc.text(`Exported on ${new Date().toLocaleString()}`, 14, 30)

  // Messages
  const tableData = messages.map((msg) => [
    msg.role === 'user' ? 'User' : msg.role === 'assistant' ? 'Agent' : 'System',
    msg.content.substring(0, 100) + (msg.content.length > 100 ? '...' : ''),
    new Date(msg.timestamp).toLocaleString(),
  ])

  autoTable(doc, {
    head: [['Role', 'Message', 'Time']],
    body: tableData,
    startY: 40,
    styles: {
      fontSize: 8,
      cellPadding: 4,
    },
    headStyles: {
      fillColor: [75, 85, 99],
    },
    alternateRowStyles: {
      fillColor: [245, 245, 245],
    },
  })

  // Save
  doc.save(`${chatTitle.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.pdf`)
}

export function exportTableToPdf(
  title: string,
  headers: string[],
  data: string[][]
) {
  const doc = new jsPDF()

  doc.setFontSize(16)
  doc.text(title, 14, 22)

  autoTable(doc, {
    head: [headers],
    body: data,
    startY: 30,
    styles: {
      fontSize: 10,
      cellPadding: 5,
    },
    headStyles: {
      fillColor: [75, 85, 99],
    },
    alternateRowStyles: {
      fillColor: [245, 245, 245],
    },
  })

  doc.save(`${title.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.pdf`)
}
