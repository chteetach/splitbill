# SplitBill frontend

Single-page Next.js client for the SplitBill API. See the [root README](../README.md) for setup,
design notes and how amounts are handled without floating-point arithmetic.

```bash
cp .env.example .env.local
npm ci
npm run dev        # http://localhost:3000
npm test           # money and error-message unit tests
```
