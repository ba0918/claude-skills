// AP2 NEGATIVE — must NOT be detected.
// close() is invoked on a real production path (the request handler), not only from tests.
export class Session {
  constructor(private id: string) {}
  async close() { /* releases resources */ }
}

export async function handleRequest(session: Session) {
  try { /* ... */ } finally {
    await session.close(); // production caller — not test-only.
  }
}
