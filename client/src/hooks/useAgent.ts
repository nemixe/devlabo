import { useMutation } from '@tanstack/react-query'
import { agentChatUrl } from '@/lib/api'
import type { ModuleType, AgentRequest, AgentResponse, Message } from '@/types'

interface UseAgentOptions {
  userId: string
  projectId: string
  activeModule: ModuleType
  chatHistory?: Message[]
  onSuccess?: (response: AgentResponse) => void
  onError?: (error: Error) => void
}

async function sendAgentMessage(request: AgentRequest): Promise<AgentResponse> {
  const response = await fetch(agentChatUrl(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(error || 'Failed to send message')
  }

  return response.json()
}

export function useAgent({
  userId,
  projectId,
  activeModule,
  chatHistory,
  onSuccess,
  onError,
}: UseAgentOptions) {
  const mutation = useMutation({
    mutationFn: (message: string) =>
      sendAgentMessage({
        message,
        chat_history: chatHistory?.map((m) => ({
          role: m.role,
          content: m.content,
        })),
        context: {
          userId,
          projectId,
          activeModule,
        },
      }),
    onSuccess,
    onError,
  })

  return {
    sendMessage: mutation.mutate,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
  }
}
