import { useState } from 'react'
import { RefreshCw, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import type { ModuleType } from '@/types'

interface PreviewPaneProps {
  className?: string
  activeModule: ModuleType
  userId: string
  projectId: string
}

const MODULE_LABELS: Record<ModuleType, string> = {
  prototype: 'Prototype Preview',
  frontend: 'Frontend Preview',
  dbml: 'Database Schema',
  tests: 'Test Results',
}

export function PreviewPane({
  className,
  activeModule,
  userId,
  projectId,
}: PreviewPaneProps) {
  const [refreshKey, setRefreshKey] = useState(0)

  const previewUrl = `/connect/${userId}/${projectId}/${activeModule}/`

  const handleRefresh = () => {
    setRefreshKey((prev) => prev + 1)
  }

  const handleOpenExternal = () => {
    window.open(previewUrl, '_blank')
  }

  return (
    <div className={cn('flex flex-col bg-surface', className)}>
      {/* Header bar */}
      <div className="h-10 px-3 flex items-center justify-between border-b border-border bg-shadow-grey">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-porcelain">
            {MODULE_LABELS[activeModule]}
          </span>
          <span className="text-xs text-muted-foreground font-mono truncate max-w-[300px]">
            {previewUrl}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleRefresh}
            aria-label="Refresh preview"
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleOpenExternal}
            aria-label="Open in new tab"
          >
            <ExternalLink className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Iframe container */}
      <div className="flex-1 relative">
        <iframe
          key={refreshKey}
          src={previewUrl}
          className="absolute inset-0 w-full h-full border-0 bg-white"
          title={`${activeModule} preview`}
        />

        {/* Placeholder overlay when no content */}
        <div className="absolute inset-0 flex items-center justify-center bg-surface pointer-events-none">
          <div className="text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-shadow-grey flex items-center justify-center">
              <span className="text-2xl text-golden-glow font-mono">
                {activeModule[0].toUpperCase()}
              </span>
            </div>
            <p className="text-muted-foreground text-sm">
              Loading {MODULE_LABELS[activeModule]}...
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
