// Production entry: the page talks to the Worker API. No answers ship to the browser.
import { RemoteApi } from "./api.ts";
import { App } from "./app.ts";

new App(document.getElementById("app")!, new RemoteApi()).boot();
