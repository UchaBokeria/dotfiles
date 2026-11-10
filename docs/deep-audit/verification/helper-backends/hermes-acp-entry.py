1: """CLI entry point for the hermes-agent ACP adapter.
2: 
3: Loads ``~/.hermes/.env``, routes logging to stderr (stdout is reserved for ACP
4: JSON-RPC), and starts the ACP agent server.
5: 
6: Usage::
7: 
8:     python -m acp_adapter.entry   # or: hermes acp / hermes-acp
9: """
10: 
11: # IMPORTANT: hermes_bootstrap must be the very first import — UTF-8 stdio
12: # on Windows.  No-op on POSIX.  See hermes_bootstrap.py for full rationale.
13: try:
14:     import hermes_bootstrap  # noqa: F401
15: except ModuleNotFoundError as exc:
16:     # Partial ``hermes update`` (git-reset landed, ``uv pip install -e .`` did not).
17:     if exc.name != "hermes_bootstrap":
18:         raise  # the bootstrap exists but cannot load: skipping it would skip PM activation
19: else:
20:     # Stop a ``utils/``/``proxy/``/``ui/`` package in the launch cwd from shadowing Hermes modules.
21:     hermes_bootstrap.harden_import_path()
22: 
23: # `hermes-acp` runs without hermes_cli.main: repair a `hermes update` killed mid-pull here, before
24: # importing anything else from the checkout (a no-op under `hermes acp`, which already did).
25: from hermes_cli import _early_recovery
26: 
27: if _early_recovery.restore_interrupted_pull():
28:     _early_recovery.relaunch_after_restore()
29: 
30: import argparse
31: import asyncio
32: import logging
33: import os
34: import sys
35: from pathlib import Path
36: from hermes_constants import get_hermes_home
37: 
38: 
39: # Liveness-probe methods outside the ACP schema. The router correctly answers JSON-RPC -32601
40: # (clients treat that as "agent alive"), but the dispatching supervisor task also logs
41: # ``"Background task failed"`` with a traceback every probe. Keep the response; silence the noise.
42: _BENIGN_PROBE_METHODS = frozenset({"ping", "health", "healthcheck"})
43: 
44: 
45: class _BenignProbeMethodFilter(logging.Filter):
46:     """Suppress acp 'Background task failed' tracebacks caused by unknown liveness-probe methods
47:     (e.g. ``ping``); every other background-task error, incl. method_not_found for non-probe
48:     methods, stays visible."""
49: 
50:     def filter(self, record: logging.LogRecord) -> bool:
51:         if record.getMessage() != "Background task failed" or not record.exc_info:
52:             return True
53:         # Lazy import keeps this module importable without ``agent-client-protocol``.
54:         try:
55:             from acp.exceptions import RequestError
56:         except ImportError:
57:             return True
58:         exc = record.exc_info[1]
59:         if not isinstance(exc, RequestError) or getattr(exc, "code", None) != -32601:
60:             return True
61:         data = getattr(exc, "data", None)
62:         return not (isinstance(data, dict) and data.get("method") in _BENIGN_PROBE_METHODS)
63: 
64: 
65: def _setup_logging() -> None:
66:     """Route all logging to stderr so stdout stays clean for ACP stdio."""
67:     from agent.redact import RedactingFormatter
68: 
69:     handler = logging.StreamHandler(sys.stderr)
70:     handler.setFormatter(RedactingFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
71:                                             datefmt="%Y-%m-%d %H:%M:%S"))
72:     handler.addFilter(_BenignProbeMethodFilter())
73:     root = logging.getLogger()
74:     root.handlers.clear()
75:     root.addHandler(handler)
76:     root.setLevel(logging.INFO)
77:     for noisy in ("httpx", "httpcore", "openai"):
78:         logging.getLogger(noisy).setLevel(logging.WARNING)
79: 
80: 
81: def _load_env() -> None:
82:     """Load .env from HERMES_HOME (default ``~/.hermes``)."""
83:     from hermes_cli.env_loader import load_hermes_dotenv
84: 
85:     hermes_home = get_hermes_home()
86:     loaded = load_hermes_dotenv(hermes_home=hermes_home)
87:     log = logging.getLogger(__name__)
88:     for env_file in loaded or ():
89:         log.info("Loaded env from %s", env_file)
90:     if not loaded:
91:         log.info("No .env found at %s, using system env", hermes_home / ".env")
92: 
93: 
94: def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
95:     parser = argparse.ArgumentParser(prog="hermes-acp", description="Run Hermes Agent as an ACP stdio server.")
96:     parser.add_argument("--version", action="store_true", help="Print Hermes version and exit")
97:     parser.add_argument("--check", action="store_true", help="Verify ACP dependencies and adapter imports, then exit")
98:     parser.add_argument("--setup", action="store_true",
99:                         help="Run interactive Hermes provider/model setup for ACP terminal auth")
100:     parser.add_argument("--setup-browser", action="store_true",
101:                         help="Prepare PM's pinned browser tools and Chromium.")
102:     parser.add_argument("--yes", "-y", action="store_true", dest="assume_yes",
103:                         help="Accept setup prompts.")
104:     return parser.parse_args(argv)
105: 
106: 
107: def _print_version() -> None:
108:     from hermes_cli.version_info import get_version_info
109: 
110:     print(get_version_info().derived_version)
111: 
112: 
113: def _run_check() -> None:
114:     import acp  # noqa: F401
115:     from acp_adapter.server import HermesACPAgent  # noqa: F401
116: 
117:     print("Hermes ACP check OK")
118: 
119: 
120: def _run_setup() -> None:
121:     from hermes_cli.main import main as hermes_main
122: 
123:     old_argv = sys.argv[:]
124:     try:
125:         sys.argv = [old_argv[0] if old_argv else "hermes", "model"]
126:         hermes_main()
127:     finally:
128:         sys.argv = old_argv
129: 
130:     # Terminal auth is the first-run UX for registry installs, so offer the browser-tools
131:     # install here. Skip silently without a TTY.
132:     if not sys.stdin.isatty():
133:         return
134:     try:
135:         reply = input("\nInstall browser tools? Downloads the pinned browser and "
136:                       "Chromium through PM. [y/N] ").strip().lower()
137:     except (EOFError, KeyboardInterrupt):
138:         return
139:     if reply in {"y", "yes"}:
140:         _run_setup_browser(assume_yes=False)
141: 
142: 
143: def _run_setup_browser(assume_yes: bool = False) -> int:
144:     """The setup command is an explicit request for PM's browser closure."""
145:     import pm
146: 
147:     try:
148:         pm.ensure("agent-browser", explicit=True)
149:     except (pm.InstallError, OSError) as exc:
150:         print(f"Browser setup failed: {exc}", file=sys.stderr)
151:         return 1
152:     return 0
153: 
154: 
155: def _warm_memory_provider_import(logger: logging.Logger) -> None:
156:     """Import ``memory.provider``'s module + numpy (no provider instance) before the ACP threads start."""
157:     from plugins.memory import import_memory_provider_module
158: 
159:     if not import_memory_provider_module():
160:         logger.debug("memory provider not warmed (none configured or import failed; agent init reports that)")
161: 
162: 
163: def main(argv: list[str] | None = None) -> None:
164:     """Entry point: load env, configure logging, run the ACP agent."""
165:     args = _parse_args(argv)
166:     for flag, action in (("version", _print_version), ("check", _run_check), ("setup", _run_setup)):
167:         if getattr(args, flag):
168:             return action()
169:     if args.setup_browser:
170:         if rc := _run_setup_browser(assume_yes=args.assume_yes):
171:             sys.exit(rc)
172:         return
173: 
174:     _setup_logging()
175:     _load_env()
176: 
177:     logger = logging.getLogger(__name__)
178:     logger.info("Starting hermes-agent ACP adapter")
179: 
180:     # Ensure the project root is on sys.path so ``from run_agent import AIAgent`` works
181:     project_root = str(Path(__file__).resolve().parent.parent)
182:     if project_root not in sys.path:
183:         sys.path.insert(0, project_root)
184: 
185:     # One TLS authority: trust the OS store before any outbound call (bare
186:     # requests/urllib included) resolves a CA bundle — see agent/ssl_verify.py.
187:     # This console script bypasses hermes_cli.main, which does the same.
188:     from agent.ssl_verify import install_truststore
189: 
190:     install_truststore()
191: 
192:     import acp
193:     from .server import HermesACPAgent
194: 
195:     # Windows: import the configured memory provider (and numpy) on the main thread before
196:     # the MCP-discovery and ACP stdin-reader threads start (hermes_cli's ~150 ms
197:     # plugin-discovery thread is the only one already running). A first-time
198:     # native-extension import (numpy via holographic / mnemosyne / hindsight) racing another
199:     # thread's import chain deadlocked in create_module and session/new never answered
200:     # (#58083). After this the off-loop agent build finds the modules in sys.modules.
201:     if sys.platform == "win32":
202:         _warm_memory_provider_import(logger)
203: 
204:     # MCP discovery from config.yaml runs in a background daemon thread so the ACP server is
205:     # responsive immediately (blocking here cost 2-5 s); per-session MCP servers registered via
206:     # asyncio.to_thread are unaffected. Metadata-only hosts can opt out of the global startup.
207:     # Previously this blocked asyncio.run() for 2-5 s. (ACP also registers per-session MCP servers
208:     # dynamically via asyncio.to_thread inside the event loop; that path is unaffected.)  Moved from
209:     # model_tools.py module scope to avoid freezing the gateway's loop on lazy import (#16856).
210:     if os.environ.get("HERMES_ACP_SKIP_CONFIGURED_MCP", "").strip() != "1":
211:         try:
212:             from hermes_cli.mcp_startup import start_background_mcp_discovery
213: 
214:             start_background_mcp_discovery(logger=logger, thread_name="acp-mcp-discovery")
215:         except Exception:
216:             logger.debug("MCP tool discovery failed at ACP startup", exc_info=True)
217: 
218:     agent = HermesACPAgent()
219:     try:
220:         asyncio.run(acp.run_agent(agent, use_unstable_protocol=True))
221:     except KeyboardInterrupt:
222:         logger.info("Shutting down (KeyboardInterrupt)")
223:     except Exception:
224:         logger.exception("ACP agent crashed")
225:         sys.exit(1)
226:     finally:
227:         # The stdio client that drove these conversations is gone. Without an
228:         # ended_at writer here, source='acp' rows stay open forever and the
229:         # ended-session guard keeps prune/archive away from them (#118216). A
230:         # later load/resume reopens the row (acp_adapter.session._restore).
231:         agent.session_manager.end_all_sessions()
232: 
233: 
234: if __name__ == "__main__":
235:     main()
