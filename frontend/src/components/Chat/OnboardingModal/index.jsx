import s, { LAYERS, RED, GRN, CYN, FG3, FG4, LINE2, INSET, DISP, TERM } from '../../../lib/chatStyles.js'
import { usePanelProps } from '../PanelPropsContext.js'

export default function OnboardingModal() {
  const p = usePanelProps()
  const o = p.onboarding
  const integ = p.integ
  const { onboardingOpen, currentStep, email, setEmail, saveEmail, emailSaving, emailError, completeOnboarding, skipOnboarding } = o

  if (!onboardingOpen) return null

  const connectorTypes = ['google_drive', 'google_calendar', 'gmail']

  const steps = [0, 1, 2]

  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.82)', zIndex:LAYERS.onboarding, display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div style={{ ...s.settingsModal, zIndex:LAYERS.onboarding }}>
        <div style={s.settingsHeader}>
          <span style={s.settingsTitle}>Get Started</span>
          <button onClick={skipOnboarding} style={s.closeBtn}>✕</button>
        </div>

        <div style={s.settingsBody}>
          {currentStep === 0 && (
            <div>
              <div style={{ fontFamily:TERM, fontSize:'20px', color:FG3, lineHeight:1.5, marginBottom:'1rem' }}>
                Welcome to <span style={{ color:RED, fontWeight:700 }}>Eidetic</span>.
              </div>
              <div style={{ fontFamily:TERM, fontSize:'17px', color:FG4, lineHeight:1.5 }}>
                Your AI-powered research assistant. Ask questions, attach files,
                search the web, and let AI help you reason through complex topics.
              </div>
              <div style={{ marginTop:'1.2rem', fontFamily:TERM, fontSize:'17px', color:FG4, lineHeight:1.5 }}>
                In a few quick steps you can set up your account and connect
                external services.
              </div>
            </div>
          )}

          {currentStep === 1 && (
            <div>
              <div style={{ fontFamily:TERM, fontSize:'17px', color:FG3, marginBottom:'1rem' }}>
                Set an email address for notifications and account recovery.
              </div>
              <input
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                style={{ width:'100%', padding:'0.55rem 0.7rem', borderRadius:0, border:`1px solid ${LINE2}`, background:'#000', color:'#fff', fontFamily:TERM, fontSize:'18px', outline:'none', boxSizing:'border-box' }}
              />
              {emailError && (
                <div style={{ fontFamily:TERM, fontSize:'15px', color:RED, marginTop:'0.4rem' }}>{emailError}</div>
              )}
              <div style={{ fontFamily:TERM, fontSize:'15px', color:FG4, marginTop:'0.6rem' }}>
                You can skip this and set it later.
              </div>
            </div>
          )}

          {currentStep === 2 && (
            <div>
              <div style={{ fontFamily:TERM, fontSize:'17px', color:FG3, marginBottom:'1rem' }}>
                Connect external services for AI-powered access to your data.
              </div>
              <div style={{ display:'flex', flexDirection:'column', gap:'0.5rem', marginBottom:'0.8rem' }}>
                {connectorTypes.map(type => {
                  const connected = integ.connectedTypes.has(type)
                  return (
                    <button key={type}
                      onClick={() => { if (!connected) integ.startOAuth(type) }}
                      disabled={connected}
                      style={{
                        display:'flex', alignItems:'center', gap:'0.6rem',
                        padding:'0.55rem 0.7rem',
                        border:`1px solid ${connected ? GRN : LINE2}`,
                        background: connected ? 'rgba(85,214,124,0.06)' : INSET,
                        color: connected ? GRN : FG3,
                        cursor: connected ? 'default' : 'pointer',
                        fontFamily:TERM, fontSize:'17px', textAlign:'left',
                      }}>
                      <span style={{ flex:1 }}>{integ.CONNECTOR_LABELS[type]}</span>
                      {connected && <span style={{ color:GRN }}>✓ Connected</span>}
                    </button>
                  )
                })}
              </div>
              <div style={{ fontFamily:TERM, fontSize:'15px', color:FG4 }}>
                Free account doesn't require integrations. You can connect later.
              </div>
            </div>
          )}
        </div>

        <div style={{ ...s.settingsFooter, flexDirection:'column', gap:'0.6rem' }}>
          <div style={{ display:'flex', justifyContent:'center', gap:'0.4rem' }}>
            {steps.map(i => (
              <div key={i} style={{
                width:'8px', height:'8px', borderRadius:'50%',
                background: i === currentStep ? RED : FG4,
                boxShadow: i === currentStep ? `0 0 5px ${RED}` : 'none',
              }} />
            ))}
          </div>

          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <button onClick={skipOnboarding}
              style={{ background:'none', border:'none', color:FG4, cursor:'pointer', fontFamily:DISP, fontSize:'9px', letterSpacing:'0.08em', textTransform:'uppercase', padding:0 }}>
              Skip onboarding
            </button>

            <div style={{ display:'flex', gap:'0.5rem' }}>
              {currentStep === 0 && (
                <>
                  <button onClick={completeOnboarding} style={s.cancelBtn}>Skip all</button>
                  <button onClick={o.nextStep} style={s.saveBtn}>Get started</button>
                </>
              )}
              {currentStep === 1 && (
                <>
                  <button onClick={() => { o.nextStep() }} style={s.cancelBtn}>Skip</button>
                  <button onClick={saveEmail} disabled={emailSaving} style={s.saveBtn}>
                    {emailSaving ? 'Saving…' : 'Save & Next'}
                  </button>
                </>
              )}
              {currentStep === 2 && (
                <>
                  <button onClick={completeOnboarding} style={s.cancelBtn}>Skip</button>
                  <button onClick={completeOnboarding} style={s.saveBtn}>Finish</button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
