import { useState } from 'react'
import {
  ChevronRight,
  ChevronDown,
  File,
  Folder,
  FolderOpen,
  FileCode,
  FileJson,
  FileText,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { FileNode } from '@/types'

// Mock file tree for demonstration
const MOCK_FILES: FileNode[] = [
  {
    name: 'src',
    path: '/src',
    type: 'directory',
    children: [
      { name: 'index.html', path: '/src/index.html', type: 'file' },
      { name: 'App.tsx', path: '/src/App.tsx', type: 'file' },
      { name: 'styles.css', path: '/src/styles.css', type: 'file' },
      {
        name: 'components',
        path: '/src/components',
        type: 'directory',
        children: [
          { name: 'Header.tsx', path: '/src/components/Header.tsx', type: 'file' },
          { name: 'Footer.tsx', path: '/src/components/Footer.tsx', type: 'file' },
        ],
      },
    ],
  },
  { name: 'package.json', path: '/package.json', type: 'file' },
  { name: 'README.md', path: '/README.md', type: 'file' },
]

function getFileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'tsx':
    case 'ts':
    case 'jsx':
    case 'js':
      return FileCode
    case 'json':
      return FileJson
    case 'md':
    case 'txt':
      return FileText
    default:
      return File
  }
}

interface FileTreeItemProps {
  node: FileNode
  depth: number
  onSelect: (path: string) => void
}

function FileTreeItem({ node, depth, onSelect }: FileTreeItemProps) {
  const [isOpen, setIsOpen] = useState(depth === 0)
  const isDirectory = node.type === 'directory'
  const Icon = isDirectory
    ? isOpen
      ? FolderOpen
      : Folder
    : getFileIcon(node.name)

  return (
    <div>
      <button
        onClick={() => {
          if (isDirectory) {
            setIsOpen(!isOpen)
          } else {
            onSelect(node.path)
          }
        }}
        className={cn(
          'w-full flex items-center gap-1 py-1 px-2 text-sm text-porcelain hover:bg-surface rounded cursor-pointer transition-colors duration-150',
          'text-left'
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {isDirectory && (
          <span className="w-4 h-4 flex items-center justify-center">
            {isOpen ? (
              <ChevronDown className="w-3 h-3" />
            ) : (
              <ChevronRight className="w-3 h-3" />
            )}
          </span>
        )}
        {!isDirectory && <span className="w-4" />}
        <Icon
          className={cn(
            'w-4 h-4 shrink-0',
            isDirectory ? 'text-golden-glow' : 'text-muted-foreground'
          )}
        />
        <span className="truncate">{node.name}</span>
      </button>
      {isDirectory && isOpen && node.children && (
        <div>
          {node.children.map((child) => (
            <FileTreeItem
              key={child.path}
              node={child}
              depth={depth + 1}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface ListModuleProps {
  className?: string
  onFileSelect?: (path: string) => void
}

export function ListModule({ className, onFileSelect }: ListModuleProps) {
  const [filter, setFilter] = useState('')

  const handleSelect = (path: string) => {
    onFileSelect?.(path)
  }

  return (
    <aside
      className={cn(
        'h-full bg-shadow-grey border-r border-border flex flex-col',
        className
      )}
    >
      <div className="p-3 border-b border-border">
        <h2 className="text-sm font-semibold text-porcelain mb-2 font-mono">
          Files
        </h2>
        <Input
          type="text"
          placeholder="Filter files..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="h-8 text-sm"
        />
      </div>
      <ScrollArea className="flex-1">
        <div className="py-2">
          {MOCK_FILES.map((node) => (
            <FileTreeItem
              key={node.path}
              node={node}
              depth={0}
              onSelect={handleSelect}
            />
          ))}
        </div>
      </ScrollArea>
    </aside>
  )
}
