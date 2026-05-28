import { useState } from 'react'

export default function useModelParams() {
  const [selectedModel, setSelectedModel] = useState('auto')
  const [compareMode, setCompareMode] = useState(false)
  const [paramsOpen, setParamsOpen] = useState(false)
  const [tempEnabled, setTempEnabled] = useState(false)
  const [temperature, setTemperature] = useState(0.7)
  const [tokensEnabled, setTokensEnabled] = useState(false)
  const [maxTokens, setMaxTokens] = useState(1024)
  const [topPEnabled, setTopPEnabled] = useState(false)
  const [topP, setTopP] = useState(0.9)

  return {
    selectedModel, setSelectedModel,
    compareMode, setCompareMode,
    paramsOpen, setParamsOpen,
    tempEnabled, setTempEnabled,
    temperature, setTemperature,
    tokensEnabled, setTokensEnabled,
    maxTokens, setMaxTokens,
    topPEnabled, setTopPEnabled,
    topP, setTopP,
  }
}
