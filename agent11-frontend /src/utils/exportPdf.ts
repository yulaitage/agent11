/** PDF 导出工具 - 使用浏览器打印生成 PDF，完美支持中文 */

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

/** 导出聊天记录为 PDF（通过浏览器打印） */
export async function exportChatToPdf(chatTitle: string, messages: Message[]) {
  const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>${esc(chatTitle)}</title>
<style>
  body { font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif; padding: 20px; color: #333; }
  h1 { font-size: 22px; margin: 0 0 5px; }
  .meta { font-size: 11px; color: #999; margin-bottom: 20px; }
  hr { border: none; border-top: 1px solid #ddd; margin-bottom: 20px; }
  .msg { margin-bottom: 16px; }
  .role { font-size: 11px; font-weight: 600; margin-bottom: 4px; }
  .role.user { color: #4f46e5; }
  .role.assistant { color: #059669; }
  .role.system { color: #888; }
  .time { font-weight: 400; color: #aaa; margin-left: 8px; }
  .content { font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
  @media print { body { padding: 0; } }
</style></head>
<body>
  <h1>${esc(chatTitle)}</h1>
  <div class="meta">导出时间: ${new Date().toLocaleString()}</div>
  <hr>
  ${messages.map(msg => `
    <div class="msg">
      <div class="role ${msg.role}">${msg.role === 'user' ? 'User' : msg.role === 'assistant' ? 'Agent' : 'System'}<span class="time">${new Date(msg.timestamp).toLocaleString()}</span></div>
      <div class="content">${esc(msg.content)}</div>
    </div>
  `).join('')}
  <script>window.onload=function(){window.print();}<\/script>
</body></html>`

  printHtml(html)
}

/** 导出表格为 PDF（通过浏览器打印） */
export async function exportTableToPdf(title: string, headers: string[], data: string[][]) {
  const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>${esc(title)}</title>
<style>
  body { font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif; padding: 20px; color: #333; }
  h2 { font-size: 18px; margin: 0 0 10px; }
  .meta { font-size: 11px; color: #999; margin-bottom: 20px; }
  table { border-collapse: collapse; width: 100%; font-size: 12px; }
  th { border: 1px solid #ccc; padding: 6px 8px; background: #f5f5f5; text-align: left; font-weight: 600; color: #555; }
  td { border: 1px solid #eee; padding: 5px 8px; color: #333; }
  tr:nth-child(even) td { background: #fafafa; }
  @media print { body { padding: 0; } }
</style></head>
<body>
  <h2>${esc(title)}</h2>
  <div class="meta">导出时间: ${new Date().toLocaleString()}</div>
  <table>
    <thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead>
    <tbody>${data.map(row => `<tr>${row.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody>
  </table>
  <script>window.onload=function(){window.print();}<\/script>
</body></html>`

  printHtml(html, title)
}

/** 在 iframe 中打印 HTML，用户可选择「另存为 PDF」 */
function printHtml(html: string) {
  const win = window.open('', '_blank')
  if (!win) return // 被浏览器拦截
  win.document.open()
  win.document.write(html)
  win.document.close()
}

function esc(s: unknown): string {
  const text = s == null ? '' : String(s)
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}
