'use client'

import { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  model?: string
  provider?: string
}

const COMPLEX_QUESTIONS = [
  {
    category: "STRATEGIE",
    question: "Wie baue ich als Finanzdienstleister eine Personal Brand auf TikTok auf, ohne cringe zu wirken?",
    tag: "P. 01"
  },
  {
    category: "PSYCHOLOGIE",
    question: "Welche psychologischen Trigger nutzt Mr. Doppelklick um Aufmerksamkeit zu halten?",
    tag: "P. 02"
  },
  {
    category: "FRAMEWORK",
    question: "Erklar mir das 4-Saulen-System fur Content und wie ich es auf meine Nische anwende",
    tag: "P. 03"
  },
  {
    category: "MONETARISIERUNG",
    question: "Wie strukturiere ich meinen Content-Funnel von Reichweite bis zum Sale?",
    tag: "P. 04"
  },
  {
    category: "DIFFERENZIERUNG",
    question: "Wie finde ich meine eigene Kategorie statt den Marktfuhrer zu kopieren?",
    tag: "P. 05"
  },
]

function formatAnswer(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^- /gm, '<li>')
    .replace(/#(\d+)/g, '<span class="tag ml-1">#$1</span>')
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [model, setModel] = useState('opus-4.5')
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
          mode: model === 'opus-4.5' ? 'rag' : 'full',
          model: model,
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

          {/* Model selector bar */}
          <div className="flex justify-between items-center py-3 border-t border-[var(--ink)]">
            <div className="flex items-center gap-4">
              <span className="text-[10px] uppercase tracking-[0.15em]">AI Engine:</span>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="model-selector"
              >
                <option value="opus-4.5">Claude Opus 4.5</option>
                <option value="gpt-4.1">GPT-4.1</option>
              </select>
            </div>
            <div className="text-[10px] uppercase tracking-[0.15em]">
              {model === 'opus-4.5' ? 'Anthropic / RAG Mode' : 'OpenAI / Full Context'}
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
                      <span>{model === 'opus-4.5' ? 'Opus 4.5' : 'GPT-4.1'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Mode:</span>
                      <span>Full Context</span>
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
              <h3 className="text-[10px] uppercase tracking-[0.2em]">Spezialisierte Anfragen</h3>
              <span className="text-[10px] uppercase tracking-[0.2em]">Klicke zum Starten</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {COMPLEX_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  onClick={() => askQuestion(q.question)}
                  className="text-left p-4 border border-[var(--ink)] hover:bg-[var(--ink)] hover:text-[var(--paper)] transition-colors group"
                >
                  <div className="flex justify-between items-start mb-3">
                    <span className="tag group-hover:border-[var(--paper)]">{q.category}</span>
                    <span className="text-[10px] opacity-50">{q.tag}</span>
                  </div>
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
                        Full Context / 121 Videos
                      </span>
                    </div>
                    <div
                      className="answer-content"
                      dangerouslySetInnerHTML={{ __html: `<p>${formatAnswer(msg.content)}</p>` }}
                    />
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
                  Analysiere 121 Transkripte
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
            <span>v2.0</span>
          </div>
        </form>
      </div>
    </main>
  )
}
