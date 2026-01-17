'use client'

import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'

interface Message {
  role: 'user' | 'assistant'
  content: string
  model?: string
  mode?: string
  tone?: string
  provider?: string
}

const EXAMPLE_QUESTIONS = [
  { category: "STRATEGIE", question: "Wie baue ich eine starke Personal Brand auf Social Media auf?" },
  { category: "HOOKS", question: "Welche Hook-Techniken funktionieren am besten für mehr Reichweite?" },
  { category: "CONTENT", question: "Wie entwickle ich ein wiedererkennbares Content-Format?" },
  { category: "FUNNEL", question: "Wie strukturiere ich einen Content-Funnel von Reichweite bis zum Verkauf?" },
  { category: "NISCHE", question: "Wie finde und dominiere ich meine eigene Nische?" },
]

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [model, setModel] = useState<'gpt-4.1' | 'opus-4.5'>('gpt-4.1')
  const [mode, setMode] = useState<'full' | 'rag'>('full')
  const [tone, setTone] = useState<'professional' | 'casual'>('professional')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const askQuestion = async (question: string) => {
    if (!question.trim() || loading) return

    const userMessage: Message = { role: 'user', content: question }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const res = await fetch(`${apiUrl}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          mode,
          model,
          tone,
          top_k: 40,
          profile: 'mr.doppelklick',
          data_root: 'data'
        })
      })

      const data = await res.json()

      const assistantMessage: Message = {
        role: 'assistant',
        content: data.answer || data.error || 'Keine Antwort erhalten',
        model: data.model,
        mode: data.mode,
        tone: data.tone,
        provider: data.provider
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'CONNECTION_ERROR: Backend nicht erreichbar. Starte den Server mit: uvicorn tiktok_pipeline.answer_api:app'
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    askQuestion(input)
  }

  const getModelLabel = () => model === 'gpt-4.1' ? 'GPT-4.1' : 'Opus 4.5'
  const getModeLabel = () => mode === 'full' ? 'Full Context' : 'RAG'
  const getToneLabel = () => tone === 'professional' ? 'Professionell' : 'Locker'

  const currentDate = new Date().toLocaleDateString('de-DE', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })

  return (
    <main className="min-h-screen paper-texture">
      {/* Header Bar */}
      <header className="border-b-2 border-[var(--ink)]">
        <div className="max-w-5xl mx-auto px-4">
          {/* Top meta bar */}
          <div className="flex justify-between items-center py-2 text-[10px] uppercase tracking-[0.2em] border-b border-[var(--ink)] opacity-70">
            <span>Field Report</span>
            <span>The Paper of Record for the Next Content Age</span>
            <span>{'>>>'} DEU</span>
          </div>

          {/* Main header */}
          <div className="py-6 text-center">
            <h1 className="font-gothic text-5xl md:text-7xl tracking-wide">
              The Doppelklick Times
            </h1>
            <div className="flex justify-center items-center gap-8 mt-3 text-[10px] uppercase tracking-[0.15em]">
              <span>{currentDate}</span>
              <span className="w-1 h-1 bg-[var(--ink)] rounded-full"></span>
              <span>Volume 1, Issue 121</span>
              <span className="w-1 h-1 bg-[var(--ink)] rounded-full"></span>
              <span>121 TikToks Indexed</span>
            </div>
          </div>

          {/* Controls bar */}
          <div className="flex flex-wrap justify-between items-center py-3 border-t border-[var(--ink)] gap-4">
            <div className="flex items-center gap-6">
              {/* Model */}
              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-[0.15em]">Model:</span>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value as 'gpt-4.1' | 'opus-4.5')}
                  className="model-selector"
                >
                  <option value="gpt-4.1">GPT-4.1</option>
                  <option value="opus-4.5">Opus 4.5</option>
                </select>
              </div>

              {/* Mode */}
              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-[0.15em]">Mode:</span>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as 'full' | 'rag')}
                  className="model-selector"
                >
                  <option value="full">Full Context</option>
                  <option value="rag">RAG (Top 40)</option>
                </select>
              </div>

              {/* Tone */}
              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-[0.15em]">Stil:</span>
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value as 'professional' | 'casual')}
                  className="model-selector"
                >
                  <option value="professional">Professionell</option>
                  <option value="casual">Locker</option>
                </select>
              </div>
            </div>

            <div className="text-[10px] uppercase tracking-[0.15em] opacity-70">
              {model === 'opus-4.5' ? 'Anthropic' : 'OpenAI'} / {getModeLabel()} / {getToneLabel()}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-5xl mx-auto px-4 py-8">
        {messages.length === 0 ? (
          /* Welcome / Questions Grid */
          <div className="animate-in">
            {/* Hero Section */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <div className="md:col-span-2 border-2 border-[var(--ink)] p-6 grid-overlay">
                <div className="relative z-10">
                  <span className="tag mb-4 inline-block">Hauptausgabe</span>
                  <h2 className="font-headline text-4xl md:text-5xl font-bold leading-tight mt-4">
                    The New<br />
                    Aesthetic of<br />
                    <em>Content</em>
                  </h2>
                  <p className="mt-6 text-sm leading-relaxed max-w-md">
                    121 TikTok-Transkripte. Ein AI-Gehirn. Frag mich alles uber
                    Content Marketing, Personal Branding und Social Media Strategie.
                  </p>
                  <div className="mt-6 flex items-center gap-4 text-[10px] uppercase tracking-[0.15em]">
                    <span>{'>>>>>'}</span>
                    <span>Basiert auf echten Daten</span>
                    <span className="font-mono">||||||||||||</span>
                  </div>
                </div>
              </div>

              <div className="border-2 border-[var(--ink)] p-4 flex flex-col justify-between">
                <div>
                  <span className="tag">Status</span>
                  <div className="mt-4 font-mono text-xs space-y-2">
                    <div className="flex justify-between">
                      <span>Videos:</span>
                      <span>121</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Transkripte:</span>
                      <span>121</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Model:</span>
                      <span>{getModelLabel()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Mode:</span>
                      <span>{getModeLabel()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Stil:</span>
                      <span>{getToneLabel()}</span>
                    </div>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-[var(--ink)]">
                  <span className="text-[10px] uppercase tracking-[0.15em]">(READY)</span>
                </div>
              </div>
            </div>

            {/* Questions Section */}
            <div className="double-line mb-6"></div>
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-[10px] uppercase tracking-[0.2em]">Beispiel-Anfragen</h3>
              <span className="text-[10px] uppercase tracking-[0.2em]">Klicke zum Starten</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {EXAMPLE_QUESTIONS.slice(0, 3).map((q, i) => (
                <button
                  key={i}
                  onClick={() => askQuestion(q.question)}
                  className="text-left p-4 border border-[var(--ink)] hover:bg-[var(--ink)] hover:text-[var(--paper)] transition-colors group"
                >
                  <span className="tag group-hover:border-[var(--paper)] mb-3 inline-block">{q.category}</span>
                  <p className="font-headline text-sm leading-relaxed">
                    {q.question}
                  </p>
                </button>
              ))}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              {EXAMPLE_QUESTIONS.slice(3).map((q, i) => (
                <button
                  key={i}
                  onClick={() => askQuestion(q.question)}
                  className="text-left p-4 border border-[var(--ink)] hover:bg-[var(--ink)] hover:text-[var(--paper)] transition-colors group"
                >
                  <span className="tag group-hover:border-[var(--paper)] mb-3 inline-block">{q.category}</span>
                  <p className="font-headline text-sm leading-relaxed">
                    {q.question}
                  </p>
                </button>
              ))}
            </div>

            {/* Footer note */}
            <div className="mt-8 pt-4 dashed-line text-center text-[10px] uppercase tracking-[0.15em] opacity-50">
              Oder stelle deine eigene Frage unten
            </div>
          </div>
        ) : (
          /* Messages */
          <div className="space-y-8">
            {messages.map((msg, i) => (
              <div key={i} className="animate-in">
                {msg.role === 'user' ? (
                  <div className="border-l-4 border-[var(--ink)] pl-4 py-2">
                    <span className="text-[10px] uppercase tracking-[0.2em] opacity-50">Anfrage</span>
                    <p className="font-headline text-xl mt-2">{msg.content}</p>
                  </div>
                ) : (
                  <div className="border-2 border-[var(--ink)] p-6">
                    <div className="flex justify-between items-center mb-4 pb-4 border-b border-[var(--ink)]">
                      <div className="flex items-center gap-3">
                        <span className="tag">{msg.provider === 'anthropic' ? 'Claude' : 'GPT'}</span>
                        <span className="text-[10px] uppercase tracking-[0.15em]">
                          {msg.model || 'unknown'}
                        </span>
                      </div>
                      <span className="text-[10px] uppercase tracking-[0.15em] opacity-50">
                        {msg.mode?.toUpperCase()} / {msg.tone === 'professional' ? 'PROFESSIONELL' : 'LOCKER'}
                      </span>
                    </div>
                    <div className="prose prose-neutral max-w-none">
                      <ReactMarkdown
                        components={{
                          h1: ({children}) => <h1 className="text-2xl font-bold mt-6 mb-3 border-b border-[var(--ink)]/30 pb-2">{children}</h1>,
                          h2: ({children}) => <h2 className="text-xl font-bold mt-5 mb-2">{children}</h2>,
                          h3: ({children}) => <h3 className="text-lg font-semibold mt-4 mb-2">{children}</h3>,
                          p: ({children}) => <p className="mb-3 leading-relaxed text-[15px]">{children}</p>,
                          ul: ({children}) => <ul className="mb-4 space-y-1 ml-4">{children}</ul>,
                          ol: ({children}) => <ol className="mb-4 space-y-1 list-decimal ml-6">{children}</ol>,
                          li: ({children}) => <li className="leading-relaxed text-[15px] pl-1">{children}</li>,
                          strong: ({children}) => <strong className="font-semibold">{children}</strong>,
                          em: ({children}) => <em className="italic">{children}</em>,
                          blockquote: ({children}) => <blockquote className="border-l-4 border-[var(--ink)]/40 pl-4 italic my-4 opacity-80">{children}</blockquote>,
                          code: ({children}) => <code className="bg-[var(--ink)]/10 px-1.5 py-0.5 text-sm font-mono rounded">{children}</code>,
                          hr: () => <hr className="my-6 border-t border-[var(--ink)]/30" />,
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="animate-in border-2 border-[var(--ink)] p-6">
                <div className="flex items-center gap-3">
                  <span className="tag">{model === 'opus-4.5' ? 'Claude' : 'GPT'}</span>
                  <span className="text-[10px] uppercase tracking-[0.15em]">(PROCESSING)</span>
                </div>
                <div className="mt-4 font-mono text-sm loading-cursor">
                  Analysiere {mode === 'full' ? '121' : '40'} Transkripte
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="sticky bottom-0 border-t-2 border-[var(--ink)] bg-[var(--paper)]">
        <form onSubmit={handleSubmit} className="max-w-5xl mx-auto px-4 py-6">
          <div className="flex gap-4 items-end">
            <div className="flex-1">
              <label className="text-[10px] uppercase tracking-[0.2em] opacity-50 mb-2 block">
                Deine Anfrage
              </label>
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Frag mich alles zu Content Marketing..."
                disabled={loading}
                className="text-lg"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="retro-button"
            >
              {loading ? '...' : 'Senden'}
            </button>
          </div>
          <div className="mt-4 flex justify-between text-[10px] uppercase tracking-[0.15em] opacity-50">
            <span>@mr.doppelklick</span>
            <span>121 Videos / {model === 'opus-4.5' ? 'Anthropic' : 'OpenAI'}</span>
            <span>v2.1</span>
          </div>
        </form>
      </div>
    </main>
  )
}
