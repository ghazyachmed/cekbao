// Markers written during browser capture: seconds since the recording started, one per real app state.
export type Marker = { label: string; t: number; detail?: string; at?: { x: number; y: number } };

export function assertCaptureComplete(scenario: string, markers: Marker[], required: string[]): void {
  const have = new Set(markers.map((m) => m.label));
  const missing = required.filter((r) => !have.has(r));
  if (missing.length) {
    throw new Error(`capture for scenario "${scenario}" is incomplete; missing: ${missing.join(", ")}. ` +
                    "Not rendering a video from a partial capture.");
  }
}
