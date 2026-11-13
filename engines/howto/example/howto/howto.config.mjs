/**
 * howto-video config for the example app. Copy this file beside your own step files and change it.
 *
 *   app         the name in your app's own header (it goes on every title card)
 *   baseUrl     where the app runs; the example server listens on 4173 (override with HOWTO_BASE)
 *   viewport    the browser size; 1440x900 at 1.5x is what the renderer expects
 *   accent      your app's brand color (used on the title card and the tutorial page)
 *   hideCss     CSS that hides things you do not want filmed (a feedback widget, a chat bubble)
 *   replaceText real names that show up on screen even on demo data, swapped for invented ones
 *               in the browser before anything is filmed: { "Real Name": "Invented Name" }
 *   readsOverPost  POST routes that only read (a file parse, a preview). Exact path, or a pattern:
 *               `*` is one path segment, `**` is the rest of the path. Leave empty unless you
 *               have read the route and know it never writes.
 *   signIn      optional async (context, { baseUrl }) => void. Add a cookie for a DEDICATED DEMO
 *               login here (context.addCookies). Never a real person's account.
 */
export default {
  app: "Sample Customer Tracker",
  baseUrl: process.env.HOWTO_BASE ?? "http://127.0.0.1:4173",
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1.5,
  accent: "#1735BB",
  hideCss: "",
  replaceText: {},
  readsOverPost: [],
  // signIn: async (context, { baseUrl }) => {
  //   await context.addCookies([{ name: "session", value: process.env.DEMO_SESSION, url: baseUrl }]);
  // },
};
