import http from 'k6/http';
import { check, sleep } from 'k6';

// ── Config ────────────────────────────────────────────────────────────────────
const BASE_URL = 'http://localhost:8000';
const TOKEN    = __ENV.TOKEN;

const MESSAGES = [
  // coder route
  'write a function to reverse a string',
  'implement a binary search algorithm',
  'fix this bug: index out of range',
  // reasoning route
  'how does backpropagation work',
  'explain the difference between TCP and UDP',
  'what is the CAP theorem',
  // llama route
  'what is the capital of France',
  'give me 5 productivity tips',
  'translate hello to Spanish',
];

// ── Stages ────────────────────────────────────────────────────────────────────
export const options = {
  stages: [
    { duration: '30s', target: 5  },  // ramp up
    { duration: '1m',  target: 10 },  // sustain
    { duration: '30s', target: 20 },  // spike
    { duration: '30s', target: 0  },  // ramp down
  ],
  thresholds: {
    http_req_failed:   ['rate<0.05'],   // <5% errors
    http_req_duration: ['p95<30000'],   // p95 under 30s (NIM is slow)
  },
};

// ── Test ──────────────────────────────────────────────────────────────────────
export default function () {
  const message = MESSAGES[Math.floor(Math.random() * MESSAGES.length)];

  const res = http.post(
    `${BASE_URL}/chat`,
    JSON.stringify({ message }),
    {
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${TOKEN}`,
      },
      timeout: '35s',
    }
  );

  check(res, {
    'status 200':        r => r.status === 200,
    'success true':      r => JSON.parse(r.body)?.success === true,
    'has response':      r => !!JSON.parse(r.body)?.data?.response,
  });

  sleep(1);
}
