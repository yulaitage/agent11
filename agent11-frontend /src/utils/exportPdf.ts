import jsPDF from 'jspdf'
import html2canvas from 'html2canvas'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

/** 将聊天记录渲染为 HTML 后截图生成 PDF（解决中文乱码） */
export async function exportChatToPdf(chatTitle: string, messages: Message[]) {
  const container = document.createElement('div')
  container.style.position = 'fixed'
  container.style.left = '-9999px'
  container.style.top = '0'
  container.style.background = '#fff'
  container.style.fontFamily = 'sans-serif'
  container.style.fontSize = '14px'
  container.innerHTML = `
    <div style="padding: 20px; max-width: 800px;">
      <h1 style="font-size: 22px; color: #333; margin: 0 0 5px;">${escapeHtml(chatTitle)}</h1>
      <p style="font-size: 11px; color: #999; margin: 0 0 20px;">导出时间: ${new Date().toLocaleString()}</p>
      <hr style="border: none; border-top: 1px solid #ddd; margin-bottom: 20px;">
      ${messages.map(msg => `
        <div style="margin-bottom: 16px;">
          <div style="font-size: 11px; color: ${msg.role === 'user' ? '#4f46e5' : msg.role === 'assistant' ? '#059669' : '#888'}; font-weight: 600; margin-bottom: 4px;">
            ${msg.role === 'user' ? 'User' : msg.role === 'assistant' ? 'Agent' : 'System'}
            <span style="font-weight: 400; color: #aaa; margin-left: 8px;">${new Date(msg.timestamp).toLocaleString()}</span>
          </div>
          <div style="font-size: 13px; color: #333; line-height: 1.6; white-space: pre-wrap;">${escapeHtml(msg.content)}</div>
        </div>
      `).join('')}
    </div>
  `
  document.body.appendChild(container)

  try {
    const canvas = await html2canvas(container, {
      scale: 2,
      useCORS: true,
      logging: false,
    })

    const imgData = canvas.toDataURL('image/png')
    const imgWidth = 190
    const imgHeight = (canvas.height * imgWidth) / canvas.width

    const doc = new jsPDF('p', 'mm', 'a4')
    let heightLeft = imgHeight
    let position = 10

    doc.addImage(imgData, 'PNG', 10, position, imgWidth, imgHeight)
    heightLeft -= doc.internal.pageSize.getHeight() - 20

    while (heightLeft > 0) {
      position = heightLeft - imgHeight + 10
      doc.addPage()
      doc.addImage(imgData, 'PNG', 10, position, imgWidth, imgHeight)
      heightLeft -= doc.internal.pageSize.getHeight() - 20
    }

    doc.save(`${chatTitle.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.pdf`)
  } finally {
    document.body.removeChild(container)
  }
}

/** 将表格渲染为 HTML 后再截图生成 PDF，解决中文乱码问题 */
export async function exportTableToPdf(
  title: string,
  headers: string[],
  data: string[][]
) {
  // 构建 HTML 表格
  const container = document.createElement('div')
  container.style.position = 'fixed'
  container.style.left = '-9999px'
  container.style.top = '0'
  container.style.background = '#fff'
  container.style.fontFamily = 'sans-serif'
  container.style.fontSize = '14px'
  container.innerHTML = `
    <div style="padding: 20px;">
      <h2 style="margin: 0 0 10px; font-size: 18px; color: #333;">${escapeHtml(title)}</h2>
      <p style="margin: 0 0 20px; font-size: 11px; color: #999;">导出时间: ${new Date().toLocaleString()}</p>
      <table style="border-collapse: collapse; width: 100%;">
        <thead>
          <tr>${headers.map(h => `<th style="border: 1px solid #ccc; padding: 6px 8px; background: #f5f5f5; text-align: left; font-weight: 600; color: #555;">${escapeHtml(h)}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${data.map(row => `<tr>${row.map(c => `<td style="border: 1px solid #eee; padding: 5px 8px; color: #333;">${escapeHtml(c)}</td>`).join('')}</tr>`).join('')}
        </tbody>
      </table>
    </div>
  `
  document.body.appendChild(container)

  try {
    const canvas = await html2canvas(container, {
      scale: 2, // 高清输出
      useCORS: true,
      logging: false,
    })

    const imgData = canvas.toDataURL('image/png')
    const imgWidth = 190 // mm (A4 width minus margins)
    const imgHeight = (canvas.height * imgWidth) / canvas.width

    const doc = new jsPDF('p', 'mm', 'a4')
    let heightLeft = imgHeight
    let position = 10

    // 第一页
    doc.addImage(imgData, 'PNG', 10, position, imgWidth, imgHeight)
    heightLeft -= doc.internal.pageSize.getHeight() - 20

    // 多页处理
    while (heightLeft > 0) {
      position = heightLeft - imgHeight + 10
      doc.addPage()
      doc.addImage(imgData, 'PNG', 10, position, imgWidth, imgHeight)
      heightLeft -= doc.internal.pageSize.getHeight() - 20
    }

    doc.save(`${title.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.pdf`)
  } finally {
    document.body.removeChild(container)
  }
}

/** 简单的 HTML 转义 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
