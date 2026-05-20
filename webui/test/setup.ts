import { vi } from 'vitest'

HTMLCanvasElement.prototype.getContext = vi.fn() as any
