import { marked } from 'marked'

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

/**
 * 将 markdown 文本渲染为 HTML。
 * 用于聊天消息、知识库词条内容、Q&A 回答等场景。
 */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  return marked.parse(text) as string
}
