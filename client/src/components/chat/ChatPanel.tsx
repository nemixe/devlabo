import { useState } from 'react'
import { MessageCircle, X, Minus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'
import { useAgent } from '@/hooks/useAgent'
import type { ModuleType, Message } from '@/types'

interface ChatPanelProps {
  userId: string
  projectId: string
  activeModule: ModuleType
}

export function ChatPanel({ userId, projectId, activeModule }: ChatPanelProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])

  const { sendMessage, isPending } = useAgent({
    userId,
    projectId,
    activeModule,
    onSuccess: (response) => {
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.message,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, assistantMessage])
    },
  })

  const handleSend = (content: string) => {
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMessage])
    sendMessage(content)
  }

  return (
    <div
      className={cn(
        'absolute bottom-4 right-4 z-50 transition-all duration-300 ease-in-out',
        isOpen ? 'w-80 h-[60vh] min-h-[400px] max-h-[600px]' : 'w-12 h-12'
      )}
    >
      {isOpen ? (
        <div className="h-full flex flex-col bg-shadow-grey border border-border rounded-lg shadow-xl overflow-hidden">
          {/* Header */}
          <div className="h-10 px-3 flex items-center justify-between border-b border-border bg-surface shrink-0">
            <div className="flex items-center gap-2">
              <MessageCircle className="w-4 h-4 text-golden-glow" />
              <span className="text-sm font-medium text-porcelain">AI Assistant</span>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => setIsOpen(false)}
                aria-label="Minimize chat"
              >
                <Minus className="w-3 h-3" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => setIsOpen(false)}
                aria-label="Close chat"
              >
                <X className="w-3 h-3" />
              </Button>
            </div>
          </div>

          {/* Messages */}
          <MessageList messages={messages} isLoading={isPending} />

          {/* Input */}
          <ChatInput onSend={handleSend} isLoading={isPending} />
        </div>
      ) : (
        <button
          onClick={() => setIsOpen(true)}
          className="w-12 h-12 rounded-full bg-golden-glow text-shadow-grey flex items-center justify-center cursor-pointer hover:bg-banana-cream hover:scale-105 transition-all duration-150 shadow-lg"
          aria-label="Open chat"
        >
          <MessageCircle className="w-6 h-6" />
        </button>
      )}
    </div>
  )
}
