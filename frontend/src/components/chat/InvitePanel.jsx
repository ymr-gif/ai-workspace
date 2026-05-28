import s from '../../lib/chatStyles.js'
import { fmtDate } from '../../lib/chatUtils.js'

export default function InvitePanel({
  inviteOpen, setInviteOpen,
  inviteList, inviteLoading,
  newToken, tokenGenerating,
  loadInvites, generateInvite,
  reEmbedding, reEmbedMsg,
  triggerReEmbed,
}) {
  return (
    <div style={{ ...s.invitePanel, transform: inviteOpen ? 'translateX(0)' : 'translateX(100%)' }}>
      <div style={s.inviteHdr}>
        <span style={s.inviteTitle}>⚡ Invite Tokens</span>
        <div style={{ display:'flex', gap:'0.4rem', alignItems:'center' }}>
          <button onClick={loadInvites} style={s.refreshBtn} disabled={inviteLoading}>{inviteLoading ? '…' : '↻'}</button>
          <button onClick={() => setInviteOpen(false)} style={s.closeBtn}>✕</button>
        </div>
      </div>
      <div style={s.inviteBody}>
        <button onClick={generateInvite} disabled={tokenGenerating}
          style={{ ...s.saveBtn, width:'100%', marginBottom:'1rem' }}>
          {tokenGenerating ? 'Generating…' : '+ Generate Invite Token'}
        </button>
        {newToken && (
          <div style={s.tokenBox}>
            <div style={{ fontSize:'0.7rem', color:'#64748b', marginBottom:'0.4rem' }}>New token (click to copy):</div>
            <div style={s.tokenText} onClick={() => { navigator.clipboard.writeText(newToken).catch(() => {}); }}>
              {newToken}
            </div>
            <div style={{ fontSize:'0.65rem', color:'#475569', marginTop:'0.3rem' }}>Valid 7 days · one-time use</div>
          </div>
        )}
        {inviteLoading && <p style={s.emptyMem}>Loading…</p>}
        {!inviteLoading && inviteList.length === 0 && <p style={s.emptyMem}>No invites yet.</p>}
        {!inviteLoading && inviteList.map(inv => (
          <div key={inv.id} style={s.inviteRow}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
              <span style={{ fontFamily:'monospace', color:'#818cf8', fontSize:'0.75rem' }}>{inv.token_prefix}</span>
              <span style={{ ...s.statusBadge, ...(inv.used ? { background:'rgba(52,211,153,0.15)', color:'#34d399' } : { background:'rgba(100,116,139,0.15)', color:'#64748b' }) }}>
                {inv.used ? 'used' : 'pending'}
              </span>
            </div>
            {inv.email && <div style={{ color:'#64748b', fontSize:'0.7rem', marginTop:'2px' }}>{inv.email}</div>}
            <div style={{ color:'#334155', fontSize:'0.68rem', marginTop:'2px' }}>
              {fmtDate(inv.created_at)}{inv.expires_at ? ` · expires ${fmtDate(inv.expires_at)}` : ''}
            </div>
          </div>
        ))}
        <div style={{ borderTop:'1px solid #1e293b', marginTop:'1rem', paddingTop:'1rem' }}>
          <div style={{ fontSize:'0.78rem', color:'#94a3b8', fontWeight:600, marginBottom:'0.5rem' }}>⚙ Embeddings</div>
          <button onClick={triggerReEmbed} disabled={reEmbedding}
            style={{ ...s.actionBtn, width:'100%', background: reEmbedding ? 'rgba(99,102,241,0.08)' : undefined }}>
            {reEmbedding ? 'Queuing…' : '↺ Re-embed All'}
          </button>
          {reEmbedMsg && <div style={{ fontSize:'0.72rem', color: reEmbedMsg.startsWith('Error') ? '#f87171' : '#34d399', marginTop:'0.4rem' }}>{reEmbedMsg}</div>}
          <div style={{ fontSize:'0.68rem', color:'#334155', marginTop:'0.3rem' }}>Re-embeds all file chunks and messages. Use after changing MODEL_EMBEDDING.</div>
        </div>
      </div>
    </div>
  )
}
