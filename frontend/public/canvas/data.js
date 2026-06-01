/* NIM // CANVAS — mock data + initial graph state. Exposed as window.NIM_CANVAS_DATA */

const MOCK_HW = {
  cpu:  { name: 'Intel Core i9-13900K', freq_ghz: 5.40, cores: 24, threads: 32, usage_pct: 8 },
  ram:  { total_gb: 64.0, used_gb: 18.4, available_gb: 45.6 },
  gpu:  { name: 'NVIDIA RTX 4090', vram_total_gb: 24, vram_used_gb: 7.2, temp_c: 58, load_pct: 12 },
  disk: { total_tb: 2.0, free_tb: 1.34 },
  uptime: '2d 7h 14m',
  hostname: 'NIM-HOST-01',
};

function buildBootLines(hw) {
  const gpu = hw.gpu;
  const lines = [
    { label: `HOSTNAME: ${hw.hostname}`,                          status:'OK',          color:'#3dff6e' },
    { label: `CPU: ${hw.cpu.name} @ ${hw.cpu.freq_ghz.toFixed(2)} GHz`, status:'OK',   color:'#3dff6e' },
    { label: `CORES: ${hw.cpu.cores} physical / ${hw.cpu.threads} logical`, status:'OK',color:'#3dff6e' },
    { label: `RAM: ${hw.ram.used_gb} GB / ${hw.ram.total_gb} GB`, status:'OK',          color:'#3dff6e' },
    gpu
      ? { label: `GPU: ${gpu.name} ${gpu.vram_total_gb} GB`,     status:'ONLINE',       color:'#3dff6e' }
      : { label: `GPU: NO DEVICE DETECTED`,                       status:'WARN',         color:'#ffb000' },
    gpu
      ? { label: `VRAM: ${gpu.vram_used_gb} GB / ${gpu.vram_total_gb} GB`, status:'OK', color:'#3dff6e' }
      : null,
    { label: `DISK: ${hw.disk.free_tb} TB free / ${hw.disk.total_tb} TB`, status:'OK',  color:'#3dff6e' },
    { label: `UPTIME: ${hw.uptime}`,                              status:'OK',           color:'#3dff6e' },
    null, /* spacer / divider */
    { label: 'CANVAS ENGINE',          status:'INITIALIZED', color:'#3dff6e' },
    { label: 'NODE GRAPH RENDERER',    status:'READY',       color:'#3dff6e' },
    { label: 'REACT FLOW',             status:'ONLINE',      color:'#3dff6e' },
    { label: 'PULLING SESSION DATA',   status:'OK',          color:'#3dff6e' },
    { label: 'MEMORY CORE',            status:'MOUNTED',     color:'#27d8ff' },
    { label: 'ROUTING SEQUENCER',      status:'STANDBY',     color:'#ffb000' },
  ].filter(l => l !== null);
  return lines;
}

const MOCK_SESSIONS = [
  { id:'s1', name:'routing-strategy', workspace:'Infra',    lastMsg:'How should auto-routing pick between models?', ts:'14:32' },
  { id:'s2', name:'rag-pipeline',     workspace:'Research', lastMsg:'Summarize the RAG ingestion pipeline.',        ts:'11:08' },
  { id:'s3', name:'cost-ceiling',     workspace:null,       lastMsg:'Draft a per-user monthly cost ceiling.',       ts:'Tue'   },
  { id:'s4', name:'deepseek-vs-70b',  workspace:'Infra',    lastMsg:'DeepSeek vs 70B on refactors.',                ts:'Mon'   },
];

const MOCK_MEMORY = {
  factCount: 11,
  sections: [
    { name:'USER',    color:'#27d8ff', count:3 },
    { name:'STACK',   color:'#3dff6e', count:3 },
    { name:'PROJECT', color:'#ffb000', count:3 },
    { name:'GOALS',   color:'#ff2222', count:2 },
  ],
  topFact: { text:'prefers TypeScript over JS', salience:0.94, section:'STACK' },
};

const MOCK_MODELS = [
  { id:'auto',      label:'AUTO'     },
  { id:'llama',     label:'LLAMA 8B' },
  { id:'deepseek',  label:'DEEPSEEK' },
  { id:'reasoning', label:'70B'      },
];

const MOCK_FILES_CANVAS = [
  { id:'f1', filename:'architecture-notes.md',  status:'ready',      attached:true  },
  { id:'f2', filename:'routing-benchmarks.csv', status:'ready',      attached:false },
  { id:'f3', filename:'ingestion-spec.pdf',      status:'processing', attached:false },
  { id:'f4', filename:'cost-analysis-q1.xlsx',  status:'ready',      attached:false },
  { id:'f5', filename:'old-api-reference.txt',  status:'failed',     attached:false },
];

const MOCK_LOGS_CANVAS = [
  { id:'l1', name:'retrieve_context', args:'{ "k": 6, "ws": "Infra" }',        result:'6 chunks · 41ms',    ts:'14:32:01' },
  { id:'l2', name:'web_fetch',        args:'{ "url": "docs.nim.io/api" }',      result:'ok · 3.2KB · 220ms', ts:'14:32:03' },
  { id:'l3', name:'write_memory',     args:'{ "section": "STACK", "key":"..." }',result:'stored · sal 0.82', ts:'14:31:44' },
  { id:'l4', name:'retrieve_context', args:'{ "k": 4, "ws": "Research" }',      result:'4 chunks · 28ms',    ts:'11:08:15' },
];

const MOCK_USAGE_CANVAS = {
  total_tokens: 128402, total_cost: 0.0423, requests: 214,
  by_model: [
    { model:'LLaMA 3.1 8B',  tokens:42150, cost:0.0014 },
    { model:'DeepSeek V4',   tokens:31200, cost:0.0078 },
    { model:'LLaMA 3.3 70B', tokens:55052, cost:0.0331 },
  ],
  window: 'rolling 30d',
};

const MOCK_WORKSPACES = [
  { id:'ws1', name:'Research', description:'Deep-dive research tasks and synthesis.',
    system_prompt:'You are a research assistant focused on technical accuracy and thorough citations.' },
  { id:'ws2', name:'Infra',    description:'Infrastructure and architecture decisions.',
    system_prompt:'You are an expert in cloud infrastructure and backend architecture. Be concise.' },
];

const INITIAL_NODES = [
  { id:'input',     type:'inputNode',      data:{ sessions:MOCK_SESSIONS },                                                                        position:{ x:120, y:300 } },
  { id:'config',    type:'configNode',     data:{ models:MOCK_MODELS },                                                                            position:{ x:120, y:100 } },
  { id:'session',   type:'sessionNode',    data:{ session:MOCK_SESSIONS[0], recentSessions:MOCK_SESSIONS.slice(1,3), allSessions:MOCK_SESSIONS },  position:{ x:440, y:220 } },
  { id:'memory',    type:'memoryNode',     data:{ mem:MOCK_MEMORY },                                                                               position:{ x:780, y:80  } },
  { id:'files',     type:'filesNode',      data:{ files:MOCK_FILES_CANVAS },                                                                       position:{ x:780, y:300 } },
  { id:'usage',     type:'usageNode',      data:{},                                                                                                position:{ x:780, y:500 } },
  { id:'logs',      type:'logsNode',       data:{},                                                                                                position:{ x:1100,y:300 } },
  { id:'workspace', type:'workspaceNode',  data:{ workspace:MOCK_WORKSPACES[0], workspaces:MOCK_WORKSPACES },                                      position:{ x:120, y:520 } },
];

const INITIAL_EDGES = [
  { id:'e-in-ses',  source:'input',   target:'session',  style:{ stroke:'#555', strokeWidth:1.5 } },
  { id:'e-cfg-ses', source:'config',  target:'session',  style:{ stroke:'#555', strokeWidth:1.5 } },
  { id:'e-ws-ses',  source:'workspace',target:'session', style:{ stroke:'#555', strokeWidth:1.5 } },
  { id:'e-ses-mem', source:'session', target:'memory',   style:{ stroke:'#555', strokeWidth:1.5 } },
  { id:'e-ses-fil', source:'session', target:'files',    style:{ stroke:'#555', strokeWidth:1.5 } },
  { id:'e-ses-use', source:'session', target:'usage',    style:{ stroke:'#555', strokeWidth:1.5 } },
  { id:'e-fil-log', source:'files',   target:'logs',     style:{ stroke:'#555', strokeWidth:1.5 } },
];

const CTX_NODE_TYPES = [
  { id:'input',     label:'Input Node',     icon:'Terminal'      },
  { id:'session',   label:'Session Node',   icon:'MessageSquare' },
  { id:'memory',    label:'Memory Node',    icon:'Brain'         },
  { id:'files',     label:'Files Node',     icon:'FolderOpen'    },
  { id:'logs',      label:'Logs Node',      icon:'ScrollText'    },
  { id:'usage',     label:'Usage Node',     icon:'BarChart2'     },
  { id:'workspace', label:'Workspace Node', icon:'Layers'        },
  { id:'config',    label:'Config Node',    icon:'Settings'      },
];

async function fetchHardware() {
  try {
    const token = localStorage.getItem('nim_token');
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), 500);
    const res = await fetch('/api/system/hardware', {
      signal: controller.signal,
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    });
    clearTimeout(tid);
    if (!res.ok) throw new Error('unavailable');
    return await res.json();
  } catch {
    return MOCK_HW;
  }
}

const MOCK_GRAPH = {
  nodes: [
    { id:'u1',  label:'Yusuf',        type:'user'       },
    { id:'p1',  label:'NIM Gateway',  type:'project'    },
    { id:'p2',  label:'ai-workspace', type:'project'    },
    { id:'s1',  label:'FastAPI',      type:'stack'      },
    { id:'s2',  label:'React+Vite',   type:'stack'      },
    { id:'s3',  label:'Postgres',     type:'stack'      },
    { id:'pr1', label:'TypeScript',   type:'preference' },
    { id:'g1',  label:'JWT policies', type:'goal'       },
    { id:'g2',  label:'Cost ceiling', type:'goal'       },
  ],
  links: [
    { source:'u1', target:'p1',  label:'owns'      },
    { source:'u1', target:'p2',  label:'maintains' },
    { source:'p1', target:'s1',  label:'uses'      },
    { source:'p1', target:'s2',  label:'uses'      },
    { source:'p1', target:'s3',  label:'uses'      },
    { source:'u1', target:'pr1', label:'prefers'   },
    { source:'u1', target:'g1',  label:'goal'      },
    { source:'u1', target:'g2',  label:'goal'      },
    { source:'p1', target:'g1',  label:'needs'     },
  ],
};

const MOCK_HISTORY = [
  { version:'v4', desc:'added STACK.prefers', ts:'2m ago',  section:'STACK',
    diff:{ added:['prefers: TypeScript over JS'], removed:[], same:['backend: FastAPI','frontend: React+Vite'] } },
  { version:'v3', desc:'updated PROJECT.status', ts:'1h ago', section:'PROJECT',
    diff:{ added:['status: frontend complete'], removed:['status: in progress'], same:['name: NIM AI Gateway'] } },
  { version:'v2', desc:'added GOALS.then', ts:'Tue', section:'GOALS',
    diff:{ added:['then: cost ceilings per user'], removed:[], same:['next: JWT + role policies'] } },
  { version:'v1', desc:'initial memory seeded', ts:'Mon', section:'USER',
    diff:{ added:['name: Yusuf','role: solo dev','timezone: UTC+3'], removed:[], same:[] } },
];

const MOCK_MEMORY_EDIT = {
  USER:    'name: Yusuf\nrole: solo dev / operator\ntimezone: UTC+3',
  STACK:   'backend: FastAPI + Postgres\nfrontend: React + Vite\nprefers: TypeScript over JS',
  PROJECT: 'name: NIM AI Gateway\ngoal: unified multi-model API\nstatus: frontend complete',
  GOALS:   'next: JWT + role policies\nthen: cost ceilings per user',
};

const MOCK_STREAM = 'Auto-routing picks the cheapest model that clears the confidence bar.\n\n- **factual** — LLaMA 3.1 8B\n- **code** — DeepSeek V4\n- **reasoning** — LLaMA 3.3 70B\n\nConfidence below threshold escalates automatically to the next tier.';

window.NIM_CANVAS_DATA = {
  MOCK_HW, MOCK_SESSIONS, MOCK_MEMORY, MOCK_MODELS,
  MOCK_GRAPH, MOCK_HISTORY, MOCK_MEMORY_EDIT, MOCK_STREAM,
  MOCK_FILES_CANVAS, MOCK_LOGS_CANVAS, MOCK_USAGE_CANVAS, MOCK_WORKSPACES,
  buildBootLines, INITIAL_NODES, INITIAL_EDGES, CTX_NODE_TYPES, fetchHardware,
};
