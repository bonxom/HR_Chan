import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { endSession } from "@/features/auth/session";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  endSession();
});

// jsdom has neither the Web Locks API nor BroadcastChannel; provide faithful stand-ins.
if (!("locks" in navigator)) {
  const chains = new Map<string, Promise<unknown>>();
  Object.defineProperty(navigator, "locks", {
    configurable: true,
    value: {
      request(name: string, callback: () => Promise<unknown>) {
        const previous = chains.get(name) ?? Promise.resolve();
        const next = previous.then(callback, callback);
        chains.set(
          name,
          next.catch(() => undefined),
        );
        return next;
      },
    },
  });
}

if (typeof globalThis.BroadcastChannel === "undefined") {
  class InMemoryBroadcastChannel {
    static readonly channels = new Set<InMemoryBroadcastChannel>();
    onmessage: ((event: MessageEvent) => void) | null = null;

    constructor(public readonly name: string) {
      InMemoryBroadcastChannel.channels.add(this);
    }

    postMessage(data: unknown): void {
      for (const channel of InMemoryBroadcastChannel.channels) {
        if (channel !== this && channel.name === this.name) {
          channel.onmessage?.({ data } as MessageEvent);
        }
      }
    }

    close(): void {
      InMemoryBroadcastChannel.channels.delete(this);
    }
  }
  globalThis.BroadcastChannel = InMemoryBroadcastChannel as unknown as typeof BroadcastChannel;
}
