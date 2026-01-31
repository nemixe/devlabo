export type ModuleType = 'prototype' | 'frontend' | 'dbml' | 'tests'

export interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: FileNode[]
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export interface AgentRequest {
  message: string
  context?: {
    userId: string
    projectId: string
    activeModule: ModuleType
  }
}

export interface AgentResponse {
  message: string
  actions?: Array<{
    type: 'file_created' | 'file_modified' | 'file_deleted'
    path: string
  }>
}

export interface SandboxFile {
  path: string
  content: string
  type: 'file' | 'directory'
}
