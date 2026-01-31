import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { Message } from '@/types'

interface MessageListProps {
  messages: Message[]
  isLoading?: boolean
}

export function MessageList({ messages, isLoading }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <ScrollArea className="flex-1 px-3">
      <div className="py-3 space-y-3">
        {messages.length === 0 && !isLoading && (
          <div className="text-center py-8">
            <p className="text-sm text-muted-foreground">
              Start a conversation with the AI agent
            </p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              'flex',
              message.role === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            <div
              className={cn(
                'max-w-[85%] rounded-lg px-3 py-2 text-sm',
                message.role === 'user'
                  ? 'bg-golden-glow text-shadow-grey'
                  : 'bg-surface text-porcelain'
              )}
            >
              <p className="whitespace-pre-wrap break-words">{message.content}</p>
              <span
                className={cn(
                  'text-xs mt-1 block',
                  message.role === 'user'
                    ? 'text-shadow-grey/70'
                    : 'text-muted-foreground'
                )}
              >
                {message.timestamp.toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-surface rounded-lg px-3 py-2">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-golden-glow rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-golden-glow rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-golden-glow rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
