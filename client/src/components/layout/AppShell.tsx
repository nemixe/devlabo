import { IconSidebar } from './IconSidebar'
import { ListModule } from '@/components/sidebar/ListModule'
import { PreviewPane } from '@/components/preview/PreviewPane'
import { ChatPanel } from '@/components/chat/ChatPanel'
import type { ModuleType } from '@/types'

interface AppShellProps {
  activeModule: ModuleType
  onModuleChange: (module: ModuleType) => void
  userId: string
  projectId: string
}

export function AppShell({
  activeModule,
  onModuleChange,
  userId,
  projectId,
}: AppShellProps) {
  return (
    <div className="h-screen w-screen flex bg-shadow-grey text-porcelain overflow-hidden">
      {/* Icon sidebar - 48px fixed */}
      <IconSidebar activeModule={activeModule} onModuleChange={onModuleChange} />

      {/* File browser - 256px fixed */}
      <ListModule className="w-64 shrink-0" />

      {/* Preview container - flexible */}
      <div className="flex-1 relative">
        <PreviewPane
          className="w-full h-full"
          activeModule={activeModule}
          userId={userId}
          projectId={projectId}
        />

        {/* Floating chat panel */}
        <ChatPanel userId={userId} projectId={projectId} activeModule={activeModule} />
      </div>
    </div>
  )
}
