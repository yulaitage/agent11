/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect, useRef, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import {
  MessageSquare,
  Settings,
  LogOut,
  Send,
  Mic,
  ChevronDown,
  Sparkles,
  Download,
  Trash2
} from 'lucide-react';
import { motion } from 'motion/react';
import { useAuth } from './context/AuthContext';
import { chatApi, type ChatListItem, SkillType, Message } from './api/chat';
import { exportChatToPdf, exportTableToPdf } from './utils/exportPdf';
import { exportTableToExcel } from './utils/exportExcel';
import FileUpload from './components/FileUpload';
import DeviceMap from './components/DeviceMap';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ModelingPage, { ModelingSidebar, ModelingHeaderExtras } from './components/ModelingPage';
import KnowledgePage, { KnowledgeSidebar, KnowledgeHeaderExtras } from './components/KnowledgePage';
import APIPage, { APISidebar, APIHeaderExtras } from './components/APIPage';
import UsersPage, { UsersSidebar, UsersHeaderExtras } from './components/UsersPage';
import SettingsPopup from './components/SettingsPopup';
import { Logo } from './components/Logo';

function HomeContent({ showSettingsPopup, setShowSettingsPopup }: {
  showSettingsPopup: boolean
  setShowSettingsPopup: (v: boolean) => void
}) {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('Home');
  const [inputText, setInputText] = useState('');
  const [hasStarted, setHasStarted] = useState(false);
  const [isDbConnected, setIsDbConnected] = useState(false);
  const [chats, setChats] = useState<ChatListItem[]>([]);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [activeSkill, setActiveSkill] = useState<SkillType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isVoiceProcessing, setIsVoiceProcessing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editChatTitle, setEditChatTitle] = useState('');
  const editInputRef = useRef<HTMLInputElement>(null);
  const [selectedKnowledgeFile, setSelectedKnowledgeFile] = useState<string | null>(null);
  const [apiRefOpen, setApiRefOpen] = useState(false);

  const navItems = ['Home', 'Modeling', 'Knowledge', 'API', 'Users'];

  useEffect(() => {
    if (isAuthenticated) {
      loadChats();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    requestAnimationFrame(() => {
      const el = messagesEndRef.current;
      if (el) {
        el.scrollTop = el.scrollHeight;
      }
    });
  }, [messages]);

  const loadChats = async () => {
    try {
      const response = await chatApi.getChats();
      if (response.chats) {
        setChats(response.chats);
      }
    } catch (err) {
      console.error('Failed to load chats:', err);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleSkillClick = async (skill: SkillType) => {
    setActiveSkill(skill);
    setHasStarted(true);

    // Create a new chat with the skill
    try {
      const response = await chatApi.createChat(skill.replace('_', ' '));
      if (response.id) {
        setCurrentChatId(response.id);
        setMessages([]);
        await loadChats();
      }
    } catch (err) {
      console.error('Failed to create chat:', err);
      setError('创建对话失败，请重试');
    }
  };

  // ─── Voice Recording ───────────────────────────────
  const startRecording = async () => {
    console.log('[Voice] Start requested')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      console.log('[Voice] Mic stream obtained')
      // Detect supported mime type (webm not supported on Safari/iOS)
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : MediaRecorder.isTypeSupported('audio/mp4')
            ? 'audio/mp4'
            : ''
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      console.log('[Voice] Recorder created, mime:', mimeType || 'default')
      audioChunksRef.current = []
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        console.log('[Voice] Data available:', e.data.size, 'bytes')
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }

      recorder.onstop = async () => {
        console.log('[Voice] Recording stopped, chunks:', audioChunksRef.current.length)
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(audioChunksRef.current, { type: mimeType || 'audio/webm' })
        console.log('[Voice] Blob size:', blob.size, 'bytes')
        if (blob.size < 100) { setError('录音太短，请重试'); setIsVoiceProcessing(false); return }
        setIsVoiceProcessing(true)
        try {
          const ext = mimeType?.includes('mp4') ? 'mp4' : 'webm'
          const formData = new FormData()
          formData.append('file', blob, `recording.${ext}`)
          console.log('[Voice] Sending to STT...')
          const res = await fetch('/api/voice/stt', { method: 'POST', body: formData })
          if (!res.ok) throw new Error('STT failed: ' + res.status)
          const data = await res.json()
          console.log('[Voice] STT result:', data)
          if (data.text) {
            setHasStarted(true)
            await sendTextMessage(data.text)
          } else {
            setError('未能识别到语音，请重试')
          }
        } catch (err) {
          console.error('[Voice] Recognition failed:', err)
          setError('语音识别失败，请重试')
        } finally {
          setIsVoiceProcessing(false)
        }
      }
      recorder.start(250)  // Collect data every 250ms for complete recording
      console.log('[Voice] Recording started')
      setIsRecording(true)
    } catch (err) {
      console.error('[Voice] Mic access denied:', err)
      setError('无法访问麦克风，请在浏览器设置中允许麦克风权限')
    }
  }

  const stopRecording = () => {
    console.log('[Voice] Stop requested, state:', mediaRecorderRef.current?.state)
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
    }
  }

  // Ref for voice auto-send (initialized after handleSend)
  const handleSendRef = useRef<() => void>(() => {})

  // Keep latest inputText in a ref so async callbacks can read it
  const inputTextRef = useRef(inputText)
  useEffect(() => { inputTextRef.current = inputText }, [inputText])

  // Send text directly (used by voice callback to avoid stale closures)
  const sendTextMessage = async (text: string) => {
    if (!text.trim()) return
    setInputText(text)
    // Small delay so React state updates before handleSend reads inputText
    await new Promise(r => setTimeout(r, 50))
    await handleSend()
  }

  // ─── TTS: speak assistant messages ──────────────────
  const speakLastMessage = (text: string, lang: string) => {
    if (!window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang  // 'zh-HK' for Cantonese, 'en-US' for English
    utterance.rate = 1.0
    utterance.pitch = 1.0
    // Pick a voice matching language
    const voices = window.speechSynthesis.getVoices()
    const match = voices.find(v => v.lang.startsWith(lang.split('-')[0]))
    if (match) utterance.voice = match
    window.speechSynthesis.speak(utterance)
  }

  const handleSend = async () => {
    setError(null);
    if (!inputText.trim()) return;

    let chatId = currentChatId;

    // Create chat if not exists
    if (!chatId) {
      try {
        const response = await chatApi.createChat('新对话');
        // Backend returns {id, title} directly (no success field)
        if (response.id) {
          chatId = response.id;
          setCurrentChatId(chatId);
          setHasStarted(true);
          await loadChats();
        } else {
          console.error('Failed to create chat:', response);
          return;
        }
      } catch (err) {
        console.error('Failed to create chat:', err);
        return;
      }
    }

    const userMessage: Message = {
      role: 'user',
      content: inputText,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsLoading(true);

    // Create placeholder for assistant message (streaming)
    const assistantMessage: Message = {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      let hasError = false;

      await chatApi.sendMessageStream(
        chatId,
        {
          message: inputText,
          skill: activeSkill ?? null,
        },
        // onChunk - streaming content
        (chunk: string) => {
          setMessages(prev => {
            const lastIdx = prev.length - 1;
            if (lastIdx >= 0 && prev[lastIdx].role === 'assistant') {
              return [
                ...prev.slice(0, lastIdx),
                { ...prev[lastIdx], content: prev[lastIdx].content + chunk }
              ];
            }
            return prev;
          });
        },
        // onDone - message complete
        (message: Message) => {
          setMessages(prev => {
            const lastIdx = prev.length - 1;
            if (lastIdx >= 0 && prev[lastIdx].role === 'assistant') {
              return [
                ...prev.slice(0, lastIdx),
                message
              ];
            }
            return prev;
          });
          setIsLoading(false);
          // TTS: speak the assistant response
          if (message.content) {
            const isEn = !/[一-鿿]/.test(message.content.slice(0, 20))
            speakLastMessage(message.content, isEn ? 'en-US' : 'zh-HK')
          }
        },
        // onError
        (error: string) => {
          setError(error);
          setIsLoading(false);
          hasError = true;
        }
      );

      if (hasError) {
        // Remove the placeholder message on error (last assistant message)
        setMessages(prev => {
          const lastIdx = prev.length - 1;
          if (lastIdx >= 0 && prev[lastIdx].role === 'assistant') {
            return prev.slice(0, lastIdx);
          }
          return prev;
        });
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      setError('发送消息失败，请重试');
      // Remove the placeholder message on error
      setMessages(prev => {
        const lastIdx = prev.length - 1;
        if (lastIdx >= 0 && prev[lastIdx].role === 'assistant') {
          return prev.slice(0, lastIdx);
        }
        return prev;
      });
      setIsLoading(false);
    }
  };
  // Keep handleSendRef updated across renders to avoid stale closures
  useEffect(() => { handleSendRef.current = handleSend; }, [handleSend]);

  const handleExportPdf = async () => {
    if (messages.length > 0) {
      const chatTitle = chats.find(c => c.id === currentChatId)?.title || 'Chat';
      try {
        await exportChatToPdf(chatTitle, messages);
      } catch (e) {
        console.error('PDF export failed', e);
      }
    }
  };

  const skills: { name: string; skill: SkillType; color: string; description: string }[] = [
    { name: 'Query', skill: 'query', color: 'bg-blue-50 text-blue-600 border-blue-100', description: 'Query infrastructure data' },
    { name: 'Troubleshooting', skill: 'troubleshoot', color: 'bg-red-50 text-red-600 border-red-100', description: 'Diagnose failures' },
    { name: 'Maintenance Reports', skill: 'maintenance_report', color: 'bg-green-50 text-green-600 border-green-100', description: 'Generate reports' },
    { name: 'Prediction', skill: 'prediction', color: 'bg-purple-50 text-purple-600 border-purple-100', description: 'Predict failures and energy' },
    { name: 'Flexible Report', skill: 'flexible_report', color: 'bg-amber-50 text-amber-600 border-amber-100', description: 'Custom data reports' }
  ];

  return (
    <div className="flex h-screen w-full bg-white overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-[#f3f4f9] border-r border-slate-200 flex flex-col">
        <div className="p-6 flex items-center gap-2">
          <div className="w-8 h-8 flex items-center justify-center overflow-hidden">
            <Logo className="w-full h-full" />
          </div>
          <span className="font-bold text-xl tracking-tight text-slate-800">Agent 11</span>
        </div>

        {activeTab === 'Home' ? (
          <div className="px-4 flex-1 flex flex-col overflow-hidden">
            <button
              onClick={() => {
                setCurrentChatId(null);
                setMessages([]);
                setHasStarted(false);
              }}
              className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-indigo-600 bg-white border border-indigo-100 rounded-lg shadow-sm mb-6"
            >
              <MessageSquare className="w-4 h-4" />
              Chat
            </button>

            {(hasStarted || chats.length > 0) && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-4 flex flex-col overflow-hidden"
              >
                <div className="flex items-center justify-between px-2">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Recent Chats</span>
                </div>

                <div className="space-y-1 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-transparent hover:scrollbar-thumb-slate-400">
                  {chats.map((chat) => (
                    <div
                      key={chat.id}
                      className={`group flex items-center justify-between px-3 py-2 rounded-lg hover:bg-white hover:shadow-sm transition-all cursor-pointer ${
                        currentChatId === chat.id ? 'bg-white shadow-sm' : ''
                      } ${isLoadingChat && currentChatId === chat.id ? 'opacity-50' : ''}`}
                    >
                      <div
                        className="flex items-center gap-3 overflow-hidden flex-1"
                        onClick={() => {
                          if (isLoadingChat) return;
                          setCurrentChatId(chat.id);
                          setHasStarted(true);
                          setMessages([]);
                          setIsLoadingChat(true);
                          chatApi.getChat(chat.id).then(response => {
                            if (response.messages) {
                              setMessages(response.messages);
                            }
                          }).catch(err => {
                            console.error('Failed to load chat:', err);
                            setError('加载对话失败');
                          }).finally(() => {
                            setIsLoadingChat(false);
                          });
                        }}
                      >
                        {isLoadingChat && currentChatId === chat.id ? (
                          <div className="w-4 h-4 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin shrink-0" />
                        ) : (
                          <MessageSquare className="w-4 h-4 text-slate-400 shrink-0" />
                        )}
                        {editingChatId === chat.id ? (
                          <input
                            ref={editInputRef}
                            type="text"
                            value={editChatTitle}
                            onChange={e => setEditChatTitle(e.target.value)}
                            onBlur={() => {
                              if (editChatTitle.trim() && editChatTitle !== chat.title) {
                                chatApi.updateChatTitle(chat.id, editChatTitle.trim()).then(() => loadChats());
                              }
                              setEditingChatId(null);
                            }}
                            onKeyDown={e => {
                              if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
                              if (e.key === 'Escape') setEditingChatId(null);
                            }}
                            className="w-full text-sm text-slate-700 bg-white border border-indigo-300 rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                            autoFocus
                          />
                        ) : (
                          <span
                            className="text-sm text-slate-600 truncate flex-1"
                            onDoubleClick={() => {
                              setEditingChatId(chat.id);
                              setEditChatTitle(chat.title);
                              setTimeout(() => editInputRef.current?.select(), 50);
                            }}
                            title="双击修改名称"
                          >
                            {chat.title}
                          </span>
                        )}
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm('确定要删除这个对话吗？')) {
                            chatApi.deleteChat(chat.id).then(() => {
                              if (currentChatId === chat.id) {
                                setCurrentChatId(null);
                                setMessages([]);
                                setHasStarted(false);
                              }
                              loadChats();
                            }).catch(err => {
                              console.error('Failed to delete chat:', err);
                              setError('删除对话失败');
                            });
                          }
                        }}
                        className="p-1 hover:bg-red-50 rounded-md transition-colors text-slate-400 hover:text-red-600"
                        title="删除对话"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </div>
        ) : activeTab === 'Modeling' ? (
          <ModelingSidebar isConnected={isDbConnected} onConnect={() => setIsDbConnected(true)} />
        ) : activeTab === 'Knowledge' ? (
          <KnowledgeSidebar onSelectFile={(id) => setSelectedKnowledgeFile(id)} />
        ) : activeTab === 'API' ? (
          <APISidebar onOpenApiRef={() => setApiRefOpen(true)} />
        ) : activeTab === 'Users' ? (
          <UsersSidebar />
        ) : (
          <div className="flex-1 p-6 text-xs text-slate-400 italic">Content coming soon...</div>
        )}

        <div className="p-4 border-t border-slate-200 space-y-1">
          <button
            onClick={() => setShowSettingsPopup(true)}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-600 hover:bg-white hover:shadow-sm rounded-lg transition-all"
          >
            <Settings className="w-4 h-4" />
            Settings
          </button>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-600 hover:bg-white hover:shadow-sm rounded-lg transition-all"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col relative">
        {/* Top Nav */}
        <header className="h-12 bg-[#2d2d2d] flex items-center px-4 justify-between">
          <nav className="flex items-center gap-1">
            {navItems.map((item) => (
              <button
                key={item}
                onClick={() => setActiveTab(item)}
                className={`px-4 py-1 text-sm font-medium rounded-md transition-colors ${
                  activeTab === item
                    ? 'bg-[#4a4a4a] text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {item}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-4">
            {activeTab === 'Modeling' && <ModelingHeaderExtras isConnected={isDbConnected} />}
            {activeTab === 'Knowledge' && <KnowledgeHeaderExtras />}
            {activeTab === 'API' && <APIHeaderExtras isApiRefOpen={apiRefOpen} onToggleApiRef={() => setApiRefOpen(!apiRefOpen)} />}
            {activeTab === 'Users' && <UsersHeaderExtras />}
            <div className="flex items-center gap-2 text-slate-300 text-sm cursor-pointer hover:text-white transition-colors">
              <span>{user?.userName || 'Guest'}</span>
              <ChevronDown className="w-4 h-4" />
            </div>
          </div>
        </header>

        {/* Content Area */}
        {activeTab === 'Home' ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 relative overflow-y-auto">
            {!hasStarted ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="max-w-3xl w-full text-center space-y-8"
              >
                {/* Central Logo */}
                <div className="relative inline-block">
                  <div className="w-24 h-24 mx-auto flex items-center justify-center relative z-10 overflow-hidden">
                    <Logo className="w-full h-full" />
                  </div>
                  <div className="absolute -inset-4 bg-indigo-500/5 blur-3xl rounded-full -z-10"></div>
                </div>

                <div className="space-y-2">
                  <h1 className="text-4xl font-bold text-slate-900 tracking-tight">Agent 11</h1>
                  <p className="text-lg text-slate-500 font-medium">Know more about your data</p>
                </div>

                <button className="inline-flex items-center gap-2 px-6 py-2.5 bg-white border border-slate-200 rounded-full text-sm font-medium text-slate-700 shadow-sm hover:shadow-md hover:border-indigo-200 transition-all group">
                  <Sparkles className="w-4 h-4 text-indigo-500 group-hover:scale-110 transition-transform" />
                  What could I ask?
                </button>

                {/* Skills Section */}
                <div className="pt-12 space-y-4">
                  <div className="flex items-center justify-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-widest">
                    <div className="h-px w-8 bg-slate-200"></div>
                    Available Skills
                    <div className="h-px w-8 bg-slate-200"></div>
                  </div>
                  <div className="flex flex-wrap justify-center gap-3">
                    {skills.map((skill, i) => (
                      <motion.button
                        key={skill.skill}
                        onClick={() => handleSkillClick(skill.skill)}
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: i * 0.1 }}
                        className={`px-3 py-1 rounded-lg border text-xs font-medium shadow-sm hover:shadow-md transition-all ${skill.color}`}
                      >
                        {skill.name}
                      </motion.button>
                    ))}
                  </div>
                </div>
              </motion.div>
            ) : (
              <div className="w-full max-w-4xl h-full flex flex-col">
                {/* Export toolbar */}
                {messages.length > 0 && (
                  <div className="flex items-center gap-2 mb-4 justify-end">
                    <button
                      onClick={handleExportPdf}
                      className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition"
                    >
                      <Download className="w-4 h-4" />
                      PDF
                    </button>
                  </div>
                )}
                <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={messagesEndRef}>
                  {messages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div
                        className={`px-4 py-2 rounded-2xl max-w-[80%] shadow-sm ${
                          msg.role === 'user'
                            ? 'bg-indigo-600 text-white rounded-tr-none'
                            : 'bg-slate-100 text-slate-800 rounded-tl-none'
                        }`}
                      >
                        <div className="whitespace-pre-wrap">{msg.content}</div>

                        {/* Structured table output (reports/query) */}
                        {msg.role !== 'user' && msg.data && (
                          (() => {
                            const table = (msg.data as any).table ?? msg.data
                            if (!table?.headers?.length || !table?.rows?.length) return null
                            return (
                              <div className="mt-3 overflow-x-auto">
                                <table className="min-w-full text-xs border border-slate-200 rounded-lg overflow-hidden bg-white">
                                  <thead className="bg-slate-50">
                                    <tr>
                                      {table.headers.map((h: string, idx: number) => (
                                        <th key={idx} className="px-2 py-1.5 text-left font-semibold text-slate-600 border-b border-slate-200">
                                          {h}
                                        </th>
                                      ))}
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {table.rows.map((row: string[], rIdx: number) => (
                                      <tr key={rIdx} className={rIdx % 2 === 0 ? 'bg-white' : 'bg-slate-50/40'}>
                                        {row.map((cell: string, cIdx: number) => (
                                          <td key={cIdx} className="px-2 py-1.5 text-slate-700 border-b border-slate-100">
                                            {cell}
                                          </td>
                                        ))}
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )
                          })()
                        )}

                        {/* Export buttons for table data */}
                        {msg.role !== 'user' && msg.data && (
                          (() => {
                            const table = (msg.data as any).table ?? msg.data
                            if (!table?.headers?.length || !table?.rows?.length) return null
                            const exportTitle = msg.skill ? `agent11_${msg.skill}` : 'agent11_export'
                            return (
                              <div className="mt-2 flex gap-2">
                                <button
                                  onClick={() => exportTableToExcel(exportTitle, table.headers, table.rows)}
                                  className="px-2 py-1 text-[10px] font-medium text-green-600 bg-green-50 border border-green-200 rounded hover:bg-green-100 transition-colors"
                                >
                                  Excel
                                </button>
                                <button
                                  onClick={async () => { try { await exportTableToPdf(exportTitle, table.headers, table.rows); } catch (e) { console.error('PDF export failed', e); } }}
                                  className="px-2 py-1 text-[10px] font-medium text-red-600 bg-red-50 border border-red-200 rounded hover:bg-red-100 transition-colors"
                                >
                                  PDF
                                </button>
                              </div>
                            )
                          })()
                        )}

                        {/* Chart rendering (bar, pie, line, donut, horizontal_bar) */}
                        {msg.role !== 'user' && msg.data && (msg.data as any).chart && (
                          <div className="mt-3">
                            <div className="text-xs font-semibold text-slate-600 mb-2">
                              {(msg.data as any).chart?.title || 'Chart'}
                            </div>
                            {(() => {
                              const chart = (msg.data as any).chart
                              const type = chart.type || 'bar'
                              const labels: string[] = chart.labels || []
                              const values: number[] = chart.values || []
                              const colors: string[] = chart.colors || []
                              const max = Math.max(1, ...values)
                              const total = values.reduce((a: number, b: number) => a + b, 0)

                              // Bar chart (horizontal)
                              if (type === 'bar' || type === 'horizontal_bar') {
                                return (
                                  <div className="space-y-1">
                                    {labels.slice(0, 30).map((label, idx) => {
                                      const v = values[idx] ?? 0
                                      const pct = Math.round((v / max) * 100)
                                      const color = colors[idx] || ['#6366f1', '#8b5cf6', '#ec4899', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#3b82f6', '#ef4444', '#84cc16'][idx % 10]
                                      return (
                                        <div key={idx} className="flex items-center gap-2">
                                          <div className="w-20 truncate text-[10px] text-slate-500">{label}</div>
                                          <div className="flex-1 h-2.5 bg-slate-200 rounded">
                                            <div className="h-2.5 rounded" style={{ width: `${pct}%`, backgroundColor: color }} />
                                          </div>
                                          <div className="w-12 text-[10px] text-slate-600 text-right">
                                            {v}{chart.unit || ''}
                                          </div>
                                        </div>
                                      )
                                    })}
                                  </div>
                                )
                              }

                              // Pie / Donut chart
                              if (type === 'pie' || type === 'donut') {
                                const radius = 40
                                const cx = 60
                                const cy = 60
                                let startAngle = -90
                                const slices = labels.map((label, idx) => {
                                  const v = values[idx] ?? 0
                                  const angle = (v / total) * 360
                                  const endAngle = startAngle + angle
                                  const largeArc = angle > 180 ? 1 : 0
                                  const x1 = cx + radius * Math.cos((startAngle * Math.PI) / 180)
                                  const y1 = cy + radius * Math.sin((startAngle * Math.PI) / 180)
                                  const x2 = cx + radius * Math.cos((endAngle * Math.PI) / 180)
                                  const y2 = cy + radius * Math.sin((endAngle * Math.PI) / 180)
                                  const path = `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`
                                  startAngle = endAngle
                                  return { label, value: v, path, color: colors[idx] || ['#6366f1', '#8b5cf6', '#ec4899', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#3b82f6', '#ef4444', '#84cc16'][idx % 10] }
                                })
                                return (
                                  <div className="flex items-center gap-4">
                                    <svg width="120" height="120" viewBox="0 0 120 120">
                                      {slices.map((s, i) => (
                                        <path key={i} d={s.path} fill={s.color} stroke="white" strokeWidth="1" />
                                      ))}
                                      {type === 'donut' && (
                                        <circle cx={cx} cy={cy} r={radius * 0.55} fill="white" />
                                      )}
                                    </svg>
                                    <div className="space-y-1">
                                      {slices.map((s, i) => (
                                        <div key={i} className="flex items-center gap-1.5">
                                          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
                                          <span className="text-[10px] text-slate-600">{s.label}: {s.value}{chart.unit || ''}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )
                              }

                              // Line chart
                              if (type === 'line') {
                                const width = 320
                                const height = 120
                                const padding = 20
                                const chartMax = Math.max(1, ...values)
                                const chartMin = 0
                                const xScale = (width - padding * 2) / Math.max(1, values.length - 1)
                                const yScale = (height - padding * 2) / Math.max(1, chartMax - chartMin)
                                const points = values.map((v, i) => {
                                  const x = padding + i * xScale
                                  const y = height - padding - (v - chartMin) * yScale
                                  return `${x},${y}`
                                }).join(' ')
                                return (
                                  <div>
                                    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
                                      {/* Grid lines */}
                                      {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                                        const y = height - padding - ratio * (height - padding * 2)
                                        return (
                                          <line key={ratio} x1={padding} y1={y} x2={width - padding} y2={y} stroke="#e2e8f0" strokeWidth="1" />
                                        )
                                      })}
                                      {/* Line */}
                                      <polyline points={points} fill="none" stroke="#6366f1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                      {/* Points */}
                                      {values.map((v, i) => {
                                        const x = padding + i * xScale
                                        const y = height - padding - (v - chartMin) * yScale
                                        return <circle key={i} cx={x} cy={y} r="3" fill="#6366f1" />
                                      })}
                                    </svg>
                                    <div className="flex justify-between px-5 mt-1">
                                      {labels.filter((_, i) => i % Math.ceil(labels.length / 6) === 0).map((label, i) => (
                                        <span key={i} className="text-[9px] text-slate-500">{label}</span>
                                      ))}
                                    </div>
                                  </div>
                                )
                              }

                              return null
                            })()}
                          </div>
                        )}

                        {/* Map rendering (device locations) */}
                        {msg.role !== 'user' && (msg as any).map_data && (
                          <DeviceMap mapData={(msg as any).map_data} />
                        )}
                      </div>
                    </div>
                  ))}
                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="bg-slate-100 text-slate-600 px-4 py-2 rounded-2xl rounded-tl-none shadow-sm">
                        Thinking...
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : activeTab === 'Modeling' ? (
          <ModelingPage isConnected={isDbConnected} />
        ) : activeTab === 'Knowledge' ? (
          <KnowledgePage selectedFile={selectedKnowledgeFile} onClearSelection={() => setSelectedKnowledgeFile(null)} />
        ) : activeTab === 'API' ? (
          <APIPage isApiRefOpen={apiRefOpen} onToggleApiRef={() => setApiRefOpen(!apiRefOpen)} />
        ) : activeTab === 'Users' ? (
          <UsersPage />
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-400">
            {activeTab} content is under development
          </div>
        )}

        {/* Bottom Input */}
        {activeTab === 'Home' && (
          <div className="p-6 border-t border-slate-100">
            {error && (
              <div className="max-w-4xl mx-auto mb-3">
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
                  {error}
                </div>
              </div>
            )}
            <div className="max-w-4xl mx-auto relative">
              <div className="absolute left-3 top-1/2 -translate-y-1/2 flex gap-1">
                <FileUpload onUploadSuccess={(filename) => console.log('Uploaded:', filename)} />
                <button
                  onClick={isRecording ? stopRecording : startRecording}
                  disabled={isVoiceProcessing}
                  className={`p-2 rounded-xl transition-all ${isRecording ? 'bg-red-100 text-red-600 animate-pulse' : 'bg-slate-50 text-slate-500 hover:bg-slate-100'} disabled:opacity-50`}
                  title={isRecording ? 'Stop recording' : 'Voice input'}
                >
                  <Mic className="w-4 h-4" />
                </button>
              </div>
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Ask Agent 11 to explore your data"
                className="w-full pl-28 pr-14 py-4 bg-white border border-slate-200 rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-slate-700 placeholder:text-slate-400"
              />
              <button
                onClick={handleSend}
                disabled={!inputText.trim() || isLoading}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-2 bg-indigo-50 text-indigo-600 rounded-xl hover:bg-indigo-600 hover:text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
            <p className="text-center text-[10px] text-slate-400 mt-3 uppercase tracking-tighter">
              AI-powered data assistant for government services
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="w-10 h-10 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
      </div>
    );
  }

  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
}

export default function App() {
  const [showSettingsPopup, setShowSettingsPopup] = useState(false);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <HomeContent showSettingsPopup={showSettingsPopup} setShowSettingsPopup={setShowSettingsPopup} />
            </ProtectedRoute>
          }
        />
      </Routes>
      <SettingsPopup opened={showSettingsPopup} onClose={() => setShowSettingsPopup(false)} />
    </BrowserRouter>
  );
}
