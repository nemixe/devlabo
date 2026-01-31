import { Layout, Code, Database, TestTube } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { ModuleType } from '@/types'

const NAV_ITEMS: { id: ModuleType; icon: typeof Layout; label: string }[] = [
  { id: 'prototype', icon: Layout, label: 'Prototype' },
  { id: 'frontend', icon: Code, label: 'Frontend' },
  { id: 'dbml', icon: Database, label: 'DBML' },
  { id: 'tests', icon: TestTube, label: 'Tests' },
]

interface IconSidebarProps {
  activeModule: ModuleType
  onModuleChange: (module: ModuleType) => void
}

export function IconSidebar({ activeModule, onModuleChange }: IconSidebarProps) {
  return (
    <aside className="w-12 h-full bg-shadow-grey border-r border-border flex flex-col items-center py-3 gap-2">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon
        const isActive = activeModule === item.id

        return (
          <Tooltip key={item.id}>
            <TooltipTrigger asChild>
              <button
                onClick={() => onModuleChange(item.id)}
                className={cn(
                  'w-10 h-10 rounded-lg flex items-center justify-center cursor-pointer transition-colors duration-150',
                  isActive
                    ? 'bg-golden-glow text-shadow-grey'
                    : 'text-porcelain hover:bg-surface'
                )}
                aria-label={item.label}
                aria-pressed={isActive}
              >
                <Icon className="w-5 h-5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <p>{item.label}</p>
            </TooltipContent>
          </Tooltip>
        )
      })}
    </aside>
  )
}
