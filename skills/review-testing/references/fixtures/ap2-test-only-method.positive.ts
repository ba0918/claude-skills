// AP2 POSITIVE — should be detected (CONFIRMED).
// destroy() is referenced only from *.test.ts (call-site enumeration shows zero production callers).
export class Session {
  constructor(private id: string) {}

  // Production API used by the app:
  getWorkspaceInfo() { return { id: this.id }; }

  // BAD: only ever called from tests. No production path invokes destroy().
  async destroy() {
    await this._workspaceManager?.destroyWorkspace(this.id);
  }
  private _workspaceManager?: { destroyWorkspace(id: string): Promise<void> };
}

// Companion test (the ONLY caller of destroy):
//   afterEach(() => session.destroy());
