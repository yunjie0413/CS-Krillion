// Prototype entry: the whole game runs in the page on the bundled sample pack.
// The day buttons move a simulated clock, so you can play other days' prompts.
import type { Pack } from "../core/pack.ts";
import { addDays, dayId, extendSchedule } from "../core/schedule.ts";
import { MemoryStore } from "../core/store.ts";
import type { MemoryDump } from "../core/store.ts";
import samplePack from "../../test/fixtures/sample-pack.json";
import { LocalApi } from "./api.ts";
import { App } from "./app.ts";

interface HotData { offset?: number; store?: MemoryDump }
interface Hot { snapshot(fn: () => HotData): void; ready?(fn: (data: HotData) => void): void; data?: HotData }
const hot = (window as unknown as { claude?: { hot?: Hot } }).claude?.hot;

const PAST_DAYS = 7;
const DAYS = 60;

function start(data: HotData): void {
  const pack = samplePack as unknown as Pack;
  const schedule = extendSchedule(pack, {}, { from: addDays(dayId(Date.now()), -PAST_DAYS), days: DAYS, seed: "prototype" });
  const store = MemoryStore.from(data.store);
  const api = new LocalApi(pack, schedule, store);
  api.offsetDays = data.offset ?? 0;
  const app = new App(document.getElementById("app")!, api, {
    prototype: {
      note: "Prototype · sample data",
      shiftDay: (by) => {
        api.offsetDays = Math.min(DAYS - PAST_DAYS - 1, Math.max(-PAST_DAYS, api.offsetDays + by));
        app.boot();
      },
    },
  });
  hot?.snapshot(() => ({ offset: api.offsetDays, store: store.dump() }));
  app.boot();
}

if (hot?.ready) hot.ready(start);
else start(hot?.data ?? {});
