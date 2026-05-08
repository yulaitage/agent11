import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface DbContextType {
  isConnected: boolean
  setIsConnected: (connected: boolean) => void
  lastConnected: number | null
}

const DbContext = createContext<DbContextType | undefined>(undefined)

const DB_CONNECTED_KEY = 'agent11_db_connected'
const DB_CONNECTED_TIME_KEY = 'agent11_db_connected_time'

export function DbProvider({ children }: { children: ReactNode }) {
  const [isConnected, setIsConnectedState] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem(DB_CONNECTED_KEY)
    if (stored === 'true') {
      setIsConnectedState(true)
    }
  }, [])

  const setIsConnected = (connected: boolean) => {
    setIsConnectedState(connected)
    if (connected) {
      localStorage.setItem(DB_CONNECTED_KEY, 'true')
      localStorage.setItem(DB_CONNECTED_TIME_KEY, String(Date.now()))
    } else {
      localStorage.removeItem(DB_CONNECTED_KEY)
      localStorage.removeItem(DB_CONNECTED_TIME_KEY)
    }
  }

  return (
    <DbContext.Provider
      value={{
        isConnected,
        setIsConnected,
        lastConnected: localStorage.getItem(DB_CONNECTED_TIME_KEY)
          ? Number(localStorage.getItem(DB_CONNECTED_TIME_KEY))
          : null,
      }}
    >
      {children}
    </DbContext.Provider>
  )
}

export function useDb() {
  const context = useContext(DbContext)
  if (context === undefined) {
    throw new Error('useDb must be used within a DbProvider')
  }
  return context
}

export default DbContext