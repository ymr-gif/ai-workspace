import s, { RED, GRN, CYN, FG3, FG4, FG5, LINE, INSET, DISP, TERM } from '../../../lib/chatStyles.js'
import { fmtDate } from '../../../lib/chatUtils.js'
import { usePanelProps } from '../PanelPropsContext.js'

export default function InvitePanel() {
  const p = usePanelProps()
  const { inviteOpen, setInviteOpen, inviteList, inviteLoading, newToken, tokenGenerating, loadInvites, generateInvite, reEmbedding, reEmbedMsg, triggerReEmbed } = p.admin
  return (
    <div style={s.invitePanel}>
      <div style={s.inviteHdr}>
        <span style={s.inviteTitle}>⚡ Invite Tokens</span>
        <div style={{ display:'flex', gap:'0.4rem', alignItems:'center' }}>
          <button onClick={loadInvites} style={s.refreshBtn} disabled={inviteLoading}>{inviteLoading ? '…' : '↻'}</button>
        </div>
      </div>
      <div style={s.inviteBody}>
        <button onClick={generateInvite} disabled={tokenGenerating}
          style={{ ...s.saveBtn, width:'100%', marginBottom:'1rem' }}>
          {tokenGenerating ? 'Generating…' : '+ Generate Invite Token'}
        </button>
        {newToken && (
          <div style={s.tokenBox}>
            <div style={{ fontSize:'14px', color:FG4, marginBottom:'0.4rem' }}>New token (click to copy):</div>
            <div style={s.tokenText} onClick={() => { navigator.clipboard.writeText(newToken).catch(() => {}); }}>
              {newToken}
            </div>
            <div style={{ fontSize:'13px', color:FG4, marginTop:'0.3rem' }}>Valid 7 days · one-time use</div>
          </div>
        )}
        {inviteLoading && <p style={s.emptyMem}>Loading…</p>}
        {!inviteLoading && inviteList.length === 0 && <p style={s.emptyMem}>No invites yet.</p>}
        {!inviteLoading && inviteList.map(inv => (
          <div key={inv.id} style={s.inviteRow}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
              <span style={{ fontFamily:TERM, color:CYN, fontSize:'15px' }}>{inv.token_prefix}</span>
              <span style={{ ...s.statusBadge, ...(inv.used ? { background:'rgba(85,214,124,0.15)', color:GRN } : { background:'rgba(77,100,126,0.15)', color:FG4 }) }}>
                {inv.used ? 'used' : 'pending'}
              </span>
            </div>
            {inv.email && <div style={{ color:FG4, fontSize:'14px', marginTop:'2px' }}>{inv.email}</div>}
            <div style={{ color:FG5, fontSize:'13px', marginTop:'2px' }}>
              {fmtDate(inv.created_at)}{inv.expires_at ? ` · expires ${fmtDate(inv.expires_at)}` : ''}
            </div>
          </div>
        ))}
        <div style={{ borderTop:`1px solid ${LINE}`, marginTop:'1rem', paddingTop:'1rem' }}>
          <div style={{ fontSize:'16px', color:FG3, marginBottom:'0.5rem', fontFamily:DISP, letterSpacing:'0.08em', textTransform:'uppercase' }}>⚙ Embeddings</div>
          <button onClick={triggerReEmbed} disabled={reEmbedding}
            style={{ ...s.actionBtn, width:'100%', background: reEmbedding ? `rgba(79,156,240,0.08)` : undefined }}>
            {reEmbedding ? 'Queuing…' : '↺ Re-embed All'}
          </button>
          {reEmbedMsg && <div style={{ fontSize:'14px', color: reEmbedMsg.startsWith('Error') ? RED : GRN, marginTop:'0.4rem' }}>{reEmbedMsg}</div>}
          <div style={{ fontSize:'13px', color:FG5, marginTop:'0.3rem' }}>Re-embeds all file chunks and messages. Use after changing MODEL_EMBEDDING.</div>
        </div>
      </div>
    </div>
  )
}
