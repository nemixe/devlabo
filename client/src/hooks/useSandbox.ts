import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { FileNode, SandboxFile } from '@/types'

interface UseSandboxOptions {
  userId: string
  projectId: string
  module: string
}

async function fetchFileTree(
  userId: string,
  projectId: string,
  module: string
): Promise<FileNode[]> {
  const response = await fetch(
    `/connect/${userId}/${projectId}/${module}/api/files`
  )

  if (!response.ok) {
    throw new Error('Failed to fetch file tree')
  }

  return response.json()
}

async function readFile(
  userId: string,
  projectId: string,
  module: string,
  path: string
): Promise<SandboxFile> {
  const response = await fetch(
    `/connect/${userId}/${projectId}/${module}/api/files?path=${encodeURIComponent(path)}`
  )

  if (!response.ok) {
    throw new Error('Failed to read file')
  }

  return response.json()
}

async function writeFile(
  userId: string,
  projectId: string,
  module: string,
  path: string,
  content: string
): Promise<void> {
  const response = await fetch(
    `/connect/${userId}/${projectId}/${module}/api/files`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ path, content }),
    }
  )

  if (!response.ok) {
    throw new Error('Failed to write file')
  }
}

export function useSandbox({ userId, projectId, module }: UseSandboxOptions) {
  const queryClient = useQueryClient()

  const fileTreeQuery = useQuery({
    queryKey: ['fileTree', userId, projectId, module],
    queryFn: () => fetchFileTree(userId, projectId, module),
    staleTime: 30 * 1000, // 30 seconds
  })

  const readFileMutation = useMutation({
    mutationFn: (path: string) => readFile(userId, projectId, module, path),
  })

  const writeFileMutation = useMutation({
    mutationFn: ({ path, content }: { path: string; content: string }) =>
      writeFile(userId, projectId, module, path, content),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['fileTree', userId, projectId, module],
      })
    },
  })

  return {
    // File tree
    fileTree: fileTreeQuery.data ?? [],
    isLoadingTree: fileTreeQuery.isLoading,
    refetchTree: fileTreeQuery.refetch,

    // Read file
    readFile: readFileMutation.mutate,
    isReadingFile: readFileMutation.isPending,

    // Write file
    writeFile: writeFileMutation.mutate,
    isWritingFile: writeFileMutation.isPending,
  }
}
