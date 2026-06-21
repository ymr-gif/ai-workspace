import { useState, useEffect } from 'react'

export default function useOnboarding(token) {
  const [loading, setLoading] = useState(true)
  const [hasOnboarded, setHasOnboarded] = useState(null)
  const [onboardingOpen, setOnboardingOpen] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [email, setEmail] = useState('')
  const [emailSaving, setEmailSaving] = useState(false)
  const [emailError, setEmailError] = useState('')

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  useEffect(() => {
    fetch('/api/auth/me', { headers: authHeaders })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) {
          const onboarded = d.has_onboarded === true
          setHasOnboarded(onboarded)
          if (!onboarded) setOnboardingOpen(true)
        }
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [token])

  function nextStep() {
    setCurrentStep(s => s + 1)
  }

  async function completeOnboarding() {
    try {
      await fetch('/api/auth/me/onboarding-complete', {
        method: 'POST', headers: authHeaders,
      })
      setHasOnboarded(true)
      setOnboardingOpen(false)
    } catch { /* ignore */ }
  }

  function skipOnboarding() {
    completeOnboarding()
  }

  async function saveEmail() {
    const val = email.trim()
    if (!val) { nextStep(); return }
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!re.test(val)) { setEmailError('Enter a valid email address'); return }
    setEmailSaving(true)
    setEmailError('')
    try {
      const r = await fetch('/api/auth/me/email', {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: val }),
      })
      if (r.ok) nextStep()
      else if (r.status === 409) setEmailError('Email already in use')
      else setEmailError('Failed to save email')
    } catch {
      setEmailError('Network error')
    } finally {
      setEmailSaving(false)
    }
  }

  return {
    loading, hasOnboarded, onboardingOpen, setOnboardingOpen,
    currentStep, nextStep,
    email, setEmail, saveEmail, emailSaving, emailError,
    completeOnboarding, skipOnboarding,
  }
}
