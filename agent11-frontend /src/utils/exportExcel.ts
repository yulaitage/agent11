import * as XLSX from 'xlsx'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

export function exportChatToExcel(chatTitle: string, messages: Message[]) {
  const data = messages.map((msg) => ({
    Role: msg.role === 'user' ? 'User' : msg.role === 'assistant' ? 'Agent' : 'System',
    Message: msg.content,
    Time: new Date(msg.timestamp).toLocaleString(),
  }))

  const worksheet = XLSX.utils.json_to_sheet(data)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Chat')

  // Set column widths
  worksheet['!cols'] = [
    { wch: 10 }, // Role
    { wch: 80 }, // Message
    { wch: 25 }, // Time
  ]

  XLSX.writeFile(
    workbook,
    `${chatTitle.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.xlsx`
  )
}

export function exportTableToExcel(
  title: string,
  headers: string[],
  data: string[][]
) {
  const dataWithHeaders = [headers, ...data]

  const worksheet = XLSX.utils.aoa_to_sheet(dataWithHeaders)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, title)

  // Set column widths based on content
  worksheet['!cols'] = headers.map(() => ({ wch: 20 }))

  XLSX.writeFile(workbook, `${title.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.xlsx`)
}
