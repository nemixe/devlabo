import { useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { ModuleType } from '@/types'

function App() {
  const [activeModule, setActiveModule] = useState<ModuleType>('prototype')

  // Placeholder values - these would come from auth/routing
  const userId = 'demo-user'
  const projectId = 'demo-project'

  return (
    <TooltipProvider delayDuration={200}>
      <AppShell
        activeModule={activeModule}
        onModuleChange={setActiveModule}
        userId={userId}
        projectId={projectId}
      />
    </TooltipProvider>
  )
}

export default App
