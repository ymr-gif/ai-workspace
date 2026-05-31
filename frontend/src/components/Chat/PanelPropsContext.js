import { createContext, useContext } from 'react'

export const PanelPropsCtx = createContext(null)
export function usePanelProps() { return useContext(PanelPropsCtx) }
