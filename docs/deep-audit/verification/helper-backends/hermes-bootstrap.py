1: """Process bootstrap for Hermes entry points: Windows UTF-8 stdio and ANSI console, import-path
2: hardening, durable lazy-install target, and dual-stack (Happy Eyeballs) connects.
3: 
4: Windows binds stdio to the console code page (cp1252), so ``print("café")`` raises
5: ``UnicodeEncodeError``, and Python children inherit the same default unless
6: ``PYTHONUTF8``/``PYTHONIOENCODING`` are set. Import this module first in every entry
7: point (``hermes``, ``hermes-agent``, ``hermes-acp``, ``gateway.run``, ``batch_runner``,
8: ``cron/scheduler``). It does NOT re-exec with ``-X utf8``: ``open()`` in the current
9: process still needs an explicit ``encoding="utf-8"`` (ruff ``PLW1514``). POSIX is left
10: alone deliberately — users' ``LANG``/``LC_*`` choices are respected.
11: 
12: Stdlib only: entry points import this before ``harden_import_path()`` runs, so nothing
13: here may pull in a Hermes package that a project-local directory could shadow.
14: """
15: 
16: from __future__ import annotations
17: 
18: import errno
19: import importlib.abc
20: import importlib.util
21: import os
22: import selectors
23: import socket
24: import sys
25: import time
26: 
27: _IS_WINDOWS = sys.platform == "win32"
28: _bootstrap_applied = False
29: _HAPPY_EYEBALLS_DELAY_SECONDS = 0.25
30: _URLLIB3_CONNECTION_MODULE = "urllib3.util.connection"
31: 
32: 
33: def _interleave_addrinfos(addrinfos: list[tuple]) -> list[tuple]:
34:     """Round-robin the resolved address families (deduped), preserving resolver order within each."""
35:     queues: dict[int, list[tuple]] = {}
36:     seen: set[tuple] = set()
37:     for addrinfo in addrinfos:
38:         family, socktype, proto, _canonname, sockaddr = addrinfo
39:         if (family, socktype, proto, sockaddr) not in seen:
40:             seen.add((family, socktype, proto, sockaddr))
41:             queues.setdefault(family, []).append(addrinfo)
42:     interleaved: list[tuple] = []
43:     while any(queues.values()):
44:         interleaved.extend(queue.pop(0) for queue in queues.values() if queue)
45:     return interleaved
46: 
47: 
48: def _quiet_unregister(selector, sock) -> None:
49:     try:
50:         selector.unregister(sock)
51:     except Exception:
52: [CREDENTIAL-RELATED LINE OMITTED]
53: 
54: 
55: def _happy_eyeballs_create_connection(address: tuple[str, int], timeout: float | None,
56:                                       source_address: tuple[str, int] | None = None, socket_options=()):
57:     """RFC 8305-style connect: staggered non-blocking attempts across families.
58: 
59:     ``socket.create_connection`` tries addresses serially, so broken-but-
60:     advertised IPv6 can burn the whole timeout per AAAA record before IPv4.
61:     """
62:     host, port = address
63:     addrinfos = _interleave_addrinfos(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
64:     if not addrinfos:
65:         raise OSError(f"getaddrinfo returned no addresses for {host}")
66: 
67:     selector = selectors.DefaultSelector()
68:     active: set[socket.socket] = set()
69:     winner = None
70:     last_error: OSError | None = None
71:     deadline = None if timeout is None else time.monotonic() + max(timeout, 0.0)
72:     next_launch = time.monotonic()
73:     pending = list(addrinfos)
74:     in_progress = {0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY, errno.EINTR, getattr(errno, "WSAEWOULDBLOCK", 10035)}
75: 
76:     def start_attempt(addrinfo):
77:         family, socktype, proto, _canonname, sockaddr = addrinfo
78:         candidate = socket.socket(family, socktype, proto)
79:         try:
80:             if source_address is not None:
81:                 local_infos = socket.getaddrinfo(source_address[0], source_address[1], family=family, type=socktype)
82:                 if not local_infos:
83:                     raise OSError(f"getaddrinfo returned no local {family} address for {source_address[0]}")
84:                 candidate.bind(local_infos[0][4])
85:             candidate.setblocking(False)
86:             result = candidate.connect_ex(sockaddr)
87:             if result in (0, errno.EISCONN):
88:                 return candidate
89:             if result not in in_progress:
90:                 raise OSError(result, os.strerror(result))
91:             selector.register(candidate, selectors.EVENT_WRITE)
92:             active.add(candidate)
93:             return None
94:         except Exception:
95:             candidate.close()
96:             raise
97: 
98:     try:
99:         while pending or active:
100:             now = time.monotonic()
101:             if deadline is not None and now >= deadline:
102:                 raise socket.timeout("timed out")
103:             if pending and now >= next_launch:
104:                 try:
105:                     winner = start_attempt(pending.pop(0))
106:                 except OSError as exc:
107:                     last_error = exc
108:                     if not active:
109:                         next_launch = now
110:                     continue
111:                 if winner is not None:
112:                     break
113:                 next_launch = now + _HAPPY_EYEBALLS_DELAY_SECONDS
114:             wait_timeout = None if deadline is None else max(0.0, deadline - now)
115:             if pending:
116:                 until_launch = max(0.0, next_launch - now)
117:                 wait_timeout = until_launch if wait_timeout is None else min(wait_timeout, until_launch)
118:             for key, _mask in selector.select(wait_timeout):
119:                 candidate = key.fileobj
120:                 error_code = candidate.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
121:                 selector.unregister(candidate)
122:                 active.discard(candidate)
123:                 if error_code == 0:
124:                     winner = candidate
125:                     break
126:                 candidate.close()
127:                 last_error = OSError(error_code, os.strerror(error_code))
128:             if winner is not None:
129:                 break
130:             if not active and pending:
131:                 next_launch = time.monotonic()
132: 
133:         if winner is None:
134:             raise last_error if last_error is not None else OSError(f"Could not connect to {host}:{port}")
135:         _quiet_unregister(selector, winner)
136:         active.discard(winner)
137:         winner.settimeout(timeout)
138:         for option in socket_options or ():
139:             winner.setsockopt(*option)
140:         winner.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
141:         return winner
142:     finally:
143:         for candidate in active:
144:             _quiet_unregister(selector, candidate)
145:             candidate.close()
146:         selector.close()
147: 
148: 
149: def _patch_urllib3_create_connection(module) -> None:
150:     """Point ``urllib3.util.connection.create_connection`` (its own serial walker) at the racer."""
151:     if getattr(module.create_connection, "_hermes_happy_eyeballs", False):
152:         return
153:     urllib3_sentinel = module._DEFAULT_TIMEOUT
154: 
155:     def _urllib3_racer(address, timeout=urllib3_sentinel, source_address=None, socket_options=None):
156:         effective = socket.getdefaulttimeout() if timeout is urllib3_sentinel else timeout
157:         # OSError = every candidate failed (identical to the serial original); anything else is a
158:         # racer bug and must surface rather than silently fall back to the serial stall.
159:         return _happy_eyeballs_create_connection(
160:             address, effective, source_address=source_address, socket_options=tuple(socket_options or ()))
161: 
162:     _urllib3_racer._hermes_happy_eyeballs = True  # type: ignore[attr-defined]
163:     module.create_connection = _urllib3_racer
164: 
165: 
166: class _Urllib3ConnectionPatcher(importlib.abc.MetaPathFinder, importlib.abc.Loader):
167:     """One-shot import hook: patch urllib3's connect walker the moment the module loads.
168: 
169:     Importing urllib3 eagerly costs ~50 ms on every CLI start, and ``hermes`` / the TUI
170:     gateway never load it unless something actually calls ``requests``.
171:     """
172: 
173:     def find_spec(self, fullname, path, target=None):
174:         if fullname != _URLLIB3_CONNECTION_MODULE:
175:             return None
176:         if self in sys.meta_path:
177:             sys.meta_path.remove(self)
178:         spec = importlib.util.find_spec(fullname)
179:         if spec is None or spec.loader is None:
180:             return None
181:         self._inner = spec.loader
182:         spec.loader = self
183:         return spec
184: 
185:     def create_module(self, spec):
186:         return self._inner.create_module(spec)
187: 
188:     def exec_module(self, module):
189:         self._inner.exec_module(module)
190:         _patch_urllib3_create_connection(module)
191: 
192: 
193: def install_happy_eyeballs_socket_connect() -> None:
194:     """Race IPv6/IPv4 for every sync TCP connect in the process (RFC 8305, #114265).
195: 
196:     The startup path does not build its HTTP clients in one place: the model catalog
197: [CREDENTIAL-RELATED LINE OMITTED]
198:     httpcore, plugins through ``urllib``/``http.client``. All of them funnel their TCP
199:     connect into ``socket.create_connection`` (``http.client`` re-reads it per connection;
200:     httpcore looks it up at call time) or into urllib3's own serial copy in
201:     ``urllib3.util.connection``. The stock implementations walk the ``getaddrinfo``
202:     results serially — on a network whose advertised IPv6 route is blackholed, each AAAA
203:     record burns the full connect timeout before IPv4 answers. Idempotent, best-effort.
204:     """
205:     if getattr(socket.create_connection, "_hermes_happy_eyeballs", False):
206:         return
207: 
208:     def _socket_racer(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, *, all_errors=False):
209:         # Stock create_connection leaves the sentinel alone, so the socket keeps the
210:         # process default from socket.setdefaulttimeout(); the racer re-applies the
211:         # timeout on the winner, so it must resolve the sentinel the same way.
212:         effective = socket.getdefaulttimeout() if timeout is socket._GLOBAL_DEFAULT_TIMEOUT else timeout
213:         # OSError = every candidate failed (identical to the serial original); anything else is a
214:         # racer bug and must surface rather than silently fall back to the serial stall.
215:         return _happy_eyeballs_create_connection(address, effective, source_address=source_address)
216: 
217:     _socket_racer._hermes_happy_eyeballs = True  # type: ignore[attr-defined]
218:     socket.create_connection = _socket_racer
219: 
220:     urllib3_connection = sys.modules.get(_URLLIB3_CONNECTION_MODULE)
221:     if urllib3_connection is not None:
222:         _patch_urllib3_create_connection(urllib3_connection)
223:     elif not any(isinstance(finder, _Urllib3ConnectionPatcher) for finder in sys.meta_path):
224:         sys.meta_path.insert(0, _Urllib3ConnectionPatcher())
225: 
226: 
227: def apply_windows_utf8_bootstrap() -> bool:
228:     """Apply the Windows UTF-8 bootstrap once; True only when it was applied this call."""
229:     global _bootstrap_applied
230: 
231:     if not _IS_WINDOWS or _bootstrap_applied:
232:         return False
233: 
234:     # setdefault() so a user can opt out with PYTHONUTF8=0 / PYTHONIOENCODING=...
235:     os.environ.setdefault("PYTHONUTF8", "1")
236:     os.environ.setdefault("PYTHONIOENCODING", "utf-8")
237: 
238:     # os.environ changes don't rebind streams bound at interpreter startup, so
239:     # reconfigure them in-process. errors="replace" keeps a non-UTF-8 legacy
240:     # pipe on stdin from crashing us (U+FFFD instead of an exception).
241:     # Non-TextIOWrapper streams (BytesIO in tests, embedded hosts) have no
242:     # reconfigure(): skip — the env-var fix for children is the bigger win.
243:     for stream_name in ("stdout", "stderr", "stdin"):
244:         reconfigure = getattr(getattr(sys, stream_name, None), "reconfigure", None)
245:         if reconfigure is None:
246:             continue
247:         try:
248:             reconfigure(encoding="utf-8", errors="replace")
249:         except (OSError, ValueError):
250: [CREDENTIAL-RELATED LINE OMITTED]
251: 
252:     _bootstrap_applied = True
253:     return True
254: 
255: 
256: _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
257: 
258: 
259: def enable_windows_vt(streams=None) -> bool:
260:     """Opt the console behind stdout/stderr in to ANSI escape processing.
261: 
262:     ``hermes_cli.colors`` and the skins emit raw SGR codes whenever stdout is a TTY. A
263:     conhost console (PowerShell 5.1, cmd.exe, the installer's ``hermes setup``) prints
264:     them as ``←[35m`` until the output handle has ENABLE_VIRTUAL_TERMINAL_PROCESSING, and
265:     shells hand native children a console with it off. The mode belongs to the console
266:     buffer, so setting it here also covers the relaunched child. Handles that are not a
267:     console (pipes, files, NUL, a windowless pythonw) fail GetConsoleMode and are left
268:     alone. A console that refuses VT (pre-Windows 10) gets NO_COLOR instead, which
269:     ``should_use_color`` and rich honour, so it shows plain text rather than garbage.
270:     Returns False only in that fallback case.
271:     """
272:     if not _IS_WINDOWS:
273:         return True
274:     import ctypes
275:     import msvcrt
276:     from ctypes import wintypes
277: 
278:     kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
279:     enabled = True
280:     for stream in (sys.stdout, sys.stderr) if streams is None else streams:
281:         try:
282:             handle = msvcrt.get_osfhandle(stream.fileno())
283:         except (AttributeError, OSError, ValueError):
284:             continue  # no fd (None under pythonw, StringIO in embedders)
285:         mode = wintypes.DWORD()
286:         if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
287:             continue
288:         if mode.value & _ENABLE_VIRTUAL_TERMINAL_PROCESSING:
289:             continue
290:         if not kernel32.SetConsoleMode(handle, mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING):
291:             enabled = False
292:     if not enabled:
293:         os.environ.setdefault("NO_COLOR", "1")
294:     return enabled
295: 
296: 
297: def suppress_platform_ver_console() -> None:
298:     """Stub ``platform._syscmd_ver`` on Windows — decode-crash + console-flash guard.
299: 
300:     ``platform.win32_ver()`` (reached via ``platform.platform()``, which the OpenAI SDK
301:     calls) shells out ``cmd /c ver`` with ``shell=True`` and no ``CREATE_NO_WINDOW``: a
302:     windowless parent (pythonw gateway, slash/kanban workers) flashes a console per call,
303:     and Python 3.11.0/3.11.1 (no ``encoding="locale"`` fix) strict-utf-8-decodes the OEM
304:     code page output under PEP 540 mode and raises (#69413). Returning the inputs makes
305:     ``win32_ver()`` fall back to ``sys.getwindowsversion()`` — same data, no subprocess.
306:     Mirrors ``hermes_cli._subprocess_compat.suppress_platform_ver_console`` for callers
307:     that never import ``hermes_cli.main``; double application is harmless.
308:     """
309:     if not _IS_WINDOWS:
310:         return
311:     try:
312:         import platform
313: 
314:         if hasattr(platform, "_syscmd_ver"):
315:             def _quiet_syscmd_ver(system="", release="", version="",
316:                                   supported_platforms=("win32", "win16", "dos")):
317:                 return system, release, version
318: 
319:             platform._syscmd_ver = _quiet_syscmd_ver
320:     except Exception:
321: [CREDENTIAL-RELATED LINE OMITTED]
322: 
323: 
324: def _glibc_frees_environ() -> bool:
325:     """True on glibc < 2.41, whose ``setenv`` of a NEW name reallocs the ``environ`` array
326:     and frees the old one (2.41+ never frees it, so a concurrent ``getenv`` stays safe)."""
327:     if not sys.platform.startswith("linux"):
328:         return False
329:     try:
330:         libc, _, version = (os.confstr("CS_GNU_LIBC_VERSION") or "").partition(" ")
331:         return libc == "glibc" and tuple(int(p) for p in version.split(".")[:2]) < (2, 41)
332:     except (AttributeError, OSError, TypeError, ValueError):
333:         return False
334: 
335: 
336: def install_never_free_environ() -> None:
337:     """Make ``os.environ`` writes safe against native ``getenv`` in other threads.
338: 
339:     On glibc < 2.41 adding a name reallocs ``environ`` and frees the old array while a
340:     thread that dropped the GIL (``getaddrinfo``, OpenSSL's ``SSL_CERT_FILE`` lookup) may
341:     still be walking it; the freed slots hold tcache pointers, so the walk segfaults the
342:     whole process. Hermes writes new names at runtime from many places (``session.create``
343:     turns on gateway prompts, the agent build sets ``HERMES_SESSION_ID``) while background
344:     threads fetch catalogs, so the tui_gateway died with SIGSEGV. This is glibc 2.41's own
345:     fix: entry strings are cached per ``NAME=value`` and never freed; a new name is
346:     appended in place to an array with spare room, and only a full array is replaced by
347:     a bigger one, the old one kept forever. Set/del churn of the same names therefore
348:     allocates nothing after the first cycle.
349: 
350:     Residual: a NEW-name ``setenv`` from native code (a C or Rust extension, not
351:     ``os.environ``) bypasses the lock and still reallocs glibc's own last array, so a
352:     ``getenv`` that started walking that array before our swap can still fault. None of
353:     the gateway's crash paths do this.
354:     """
355:     if getattr(os.putenv, "_hermes_never_free_environ", False) or not _glibc_frees_environ():
356:         return
357:     import _thread
358:     import ctypes
359: 
360:     try:
361:         libc = ctypes.CDLL(None)
362:         environ = ctypes.c_void_p.in_dll(libc, "environ")
363:         getenv = libc.getenv
364:     except (AttributeError, OSError, ValueError):
365:         return
366:     getenv.restype, getenv.argtypes = ctypes.c_void_p, [ctypes.c_char_p]
367:     real_putenv, real_unsetenv = os.putenv, os.unsetenv
368:     # Two unserialized writers both copy the live array and the later publish drops the
369:     # other's new name or undoes its replacement. Reentrant: audit hooks run inside it.
370:     lock = _thread.RLock()
371:     # A fork while another thread holds the lock would leave it held forever in the child.
372:     os.register_at_fork(before=lock.acquire, after_in_parent=lock.release, after_in_child=lock.release)
373:     lines: dict[bytes, ctypes.Array] = {}  # b"NAME=value" -> its C string (glibc's known_values)
374:     arrays: list[tuple[ctypes.Array, int]] = []  # every array we published + its address; only the last grows
375:     gen = [0]  # bumped by every publish, so a nested write inside an audited call forces a redo
376: 
377:     def _putenv(key, value) -> None:
378:         name, val = os.fsencode(key), os.fsencode(value)
379:         if not name or b"=" in name or b"\0" in name + val:
380:             real_putenv(key, value)  # the usual OSError/ValueError
381:             return
382:         sys.audit("os.putenv", name, val)
383:         prefix = name + b"="
384:         with lock:
385:             if (line := lines.get(prefix + val)) is None:
386:                 line = lines[prefix + val] = ctypes.create_string_buffer(prefix + val)
387:             entry = ctypes.addressof(line)
388:             # create_string_buffer/addressof above are audited and a hook may write os.environ
389:             # re-entrantly (RLock): redo the read if any write was published before ours. The loop
390:             # itself makes no audited call, so a hook that writes on every event cannot spin it.
391:             while True:
392:                 start = gen[0]
393:                 # getenv returns a pointer just past "NAME=" inside the matching entry, so the
394:                 # walk compares pointers instead of reading every string.
395:                 found = getenv(name)
396:                 target = found - len(prefix) if found else None
397:                 live = ctypes.cast(environ.value, ctypes.POINTER(ctypes.c_void_p)) if environ.value else None
398:                 n, hit = 0, False
399:                 while live and (current := live[n]):
400:                     if current == target:
401:                         hit = True
402:                         break
403:                     n += 1
404:                 own, own_addr = arrays[-1] if arrays else (None, None)
405:                 grow = not hit and not (own is not None and environ.value == own_addr and n + 2 <= len(own))
406:                 if grow:
407:                     fresh = (ctypes.c_void_p * max(2 * (n + 2), 64))(*(live[:n] if live else ()), entry)
408:                     fresh_addr = ctypes.cast(fresh, ctypes.c_void_p).value  # unaudited, unlike addressof
409:                 if gen[0] == start:
410:                     break
411:             # No audited call from here on. Plain aligned stores: a concurrent walker sees them in
412:             # order on x86-64 (TSO). aarch64 may reorder them, which is theoretical there and
413:             # matches glibc < 2.41's own plain-store publish; Python has no cheap portable fence.
414:             gen[0] += 1
415:             if hit:
416:                 live[n] = entry  # replace in place, as glibc does
417:             elif not grow:
418:                 own[n + 1] = None  # terminator first, so a walker never runs past the new entry
419:                 own[n] = entry
420:             else:
421:                 arrays.append((fresh, fresh_addr))
422:                 environ.value = fresh_addr
423: 
424:     def _unsetenv(key) -> None:
425:         with lock:  # glibc shifts the entries of the live array (ours included) in place
426:             real_unsetenv(key)
427:             gen[0] += 1
428: 
429:     _putenv._hermes_never_free_environ = True  # type: ignore[attr-defined]
430:     _unsetenv._hermes_never_free_environ = True  # type: ignore[attr-defined]
431:     os.putenv, os.unsetenv = _putenv, _unsetenv
432: 
433: 
434: def harden_import_path(src_root: str | None = None) -> None:
435:     """Stop a package in the current directory from shadowing Hermes modules.
436: 
437:     Hermes ships top-level modules with common names (``utils``, ``proxy``, ``ui``); a
438:     project with its own ``utils/`` launched from its directory would win the import.
439:     The cwd reaches ``sys.path`` as ``""``/``"."`` (script/``-m`` launches) AND as an
440:     absolute path (venv activation, PYTHONPATH), so both are handled: relative forms are
441:     dropped and the Hermes root is *relocated* to the front, not merely inserted when
442:     absent. ``src_root`` defaults to this module's directory (the repo root for every
443:     shipped entry point), so no spawner env var is required.
444:     """
445:     root = src_root or os.environ.get("HERMES_PYTHON_SRC_ROOT") or os.path.dirname(
446:         os.path.abspath(__file__)
447:     )
448: 
449:     sys.path[:] = [p for p in sys.path if p not in ("", ".")]
450: 
451:     root_abs = os.path.abspath(root)
452:     sys.path[:] = [p for p in sys.path if os.path.abspath(p) != root_abs]
453:     sys.path.insert(0, root)
454: 
455: 
456: def export_scratch_tmp_env() -> None:
457:     """Point ``TMPDIR``/``TMP``/``TEMP`` at ``HERMES_HOME/cache/scratch`` unless the user set them.
458: 
459:     System temp is tmpfs on most Linux hosts and containers; Hermes' browser profiles, PTY
460:     probes and every ``tempfile`` default a child script makes would eat RAM there. Runs at
461:     import so every entry point and every child they spawn inherits it; ``hermes_cli.main``
462:     re-runs it after ``--profile`` re-homes the process. Never raises.
463:     """
464:     try:
465:         from hermes_constants import export_scratch_tmp_env as _export
466:         _export()
467:     except Exception:
468: [CREDENTIAL-RELATED LINE OMITTED]
469: 
470: 
471: # Apply on import — entry points just need ``import hermes_bootstrap``
472: # (or ``from hermes_bootstrap import apply_windows_utf8_bootstrap``) at
473: # the very top of their module, before importing anything else.  The
474: # import side effect does the right thing.
475: apply_windows_utf8_bootstrap()
476: enable_windows_vt()
477: suppress_platform_ver_console()
478: install_never_free_environ()
479: 
480: # Every entry point imports this module before its dependency graph.
481: from pathlib import Path
482: 
483: _root = Path(__file__).resolve().parent
484: try:
485:     os.getcwd()
486: except FileNotFoundError:
487:     # Reaped workspaces leave children in a deleted cwd. PM resolves relative
488:     # import paths before the CLI's guards, so recover before any PM work.
489:     os.chdir(_root)
490: 
491: 
492: def _legacy_post_swap_invocation(argv: list[str]) -> tuple[Path, list[str]] | None:
493:     """Recognize the exact fresh-checkout command emitted by shipped updaters."""
494:     if not argv or argv[0] != "update":
495:         return None
496:     try:
497:         marker = argv.index("--post-swap", 1)
498:     except ValueError:
499:         return None
500:     if marker + 2 != len(argv):
501:         return None
502:     return Path(argv[marker + 1]), argv[1:marker]
503: 
504: 
505: # Everything below imports Hermes packages, so the root goes on sys.path first. A venv
506: # editable-installed from a pre-PM tree maps only the top-level packages it knew then:
507: # without this, ``pm`` is unimportable and the launch silently skips PM adoption.
508: harden_import_path(str(_root))
509: 
510: 
511: def _settle_interrupted_update() -> None:
512:     """Put back the tree a killed ``hermes update`` left half-moved, before PM, launch preparation or
513:     any Hermes package imports from it (``hermes_cli._early_recovery``; ``hermes_cli.main`` repeats the
514:     call for entries that never reach this module). A killed ZIP swap can leave ``hermes_cli/`` itself
515:     moved aside: the journal-driven restore then runs from that moved-aside copy, the code that wrote
516:     the journal. Root files are never absent mid-swap (``update_cmd_zip._commit_staged_replacements``)."""
517:     try:
518:         from hermes_cli import _early_recovery as recovery
519:     except ImportError:
520:         moved_aside = _root / "hermes_cli.hermes-update-old" / "_early_recovery.py"
521:         if not (_root / ".hermes-update-zip-swap").is_file() or not moved_aside.is_file():
522:             return  # not a torn update: the imports below report the real damage
523:         import types
524: 
525:         # The moved-aside directory stands in as ``hermes_cli`` (its ``__init__`` not run), so the
526:         # repair's own ``from hermes_cli import update_lock`` finds the custody code beside it:
527:         # without that the restore refuses to repair unguarded. Dropped again unless it relaunches.
528:         package = types.ModuleType("hermes_cli")
529:         package.__path__ = [str(moved_aside.parent), str(_root / "hermes_cli")]
530:         sys.modules["hermes_cli"] = package
531:         try:
532:             from hermes_cli import _early_recovery as recovery
533: 
534:             if recovery.restore_interrupted_pull(_root):
535:                 recovery.relaunch_after_restore()
536:         finally:
537:             for name in [n for n in sys.modules if n == "hermes_cli" or n.startswith("hermes_cli.")]:
538:                 del sys.modules[name]
539:         return
540:     if recovery.restore_interrupted_pull(_root):
541:         recovery.relaunch_after_restore()
542: 
543: 
544: _settle_interrupted_update()
545: 
546: 
547: def _pin_launcher_home() -> None:
548:     """A minted launcher (``hermes_cli._launchers``) pins ``HERMES_HOME`` to the install's default
549:     root. That needs ``hermes_constants`` from the checkout, so the launcher asks for it here, after
550:     the repair above: a merge killed while writing ``hermes_constants.py`` must not keep the repair
551:     from ever running. The flag name is ``_launchers.PIN_DEFAULT_HOME_FLAG``."""
552:     if getattr(sys, "_hermes_pin_default_home", False) and not os.environ.get("HERMES_HOME"):
553:         from hermes_constants import get_default_hermes_root
554: 
555:         os.environ["HERMES_HOME"] = str(get_default_hermes_root())
556: 
557: 
558: _pin_launcher_home()
559: 
560: _legacy_post_swap = _legacy_post_swap_invocation(sys.argv[1:])
561: if _legacy_post_swap is not None:
562:     # This continuation exists precisely because the replacement tree may not
563:     # run under the old release's dependency graph. Take it over before PM
564:     # activation, launch preparation, or argparse imports any of that graph.
565:     from hermes_cli.update_handoff import _continue_legacy_post_swap
566: 
567:     _handoff_path, _argv_tail = _legacy_post_swap
568:     raise SystemExit(_continue_legacy_post_swap(_handoff_path, argv_tail=_argv_tail))
569: 
570: 
571: class RelaunchExit(SystemExit):
572:     """Exit carrying a relaunched child's status: that child already produced this run's output,
573:     so callers that report their own boot failures (the Bot Chat delivery runner) must not."""
574:     relaunched = True
575: 
576: 
577: from pm.environments import activate_dependencies, install_state_permission_message
578: from hermes_cli._early_recovery import recover_if_needed
579: 
580: from hermes_cli._parser import command_argv
581: 
582: # Repair needs only stdlib. Do not activate the damaged tree to reach it.
583: _pm_repair = command_argv(sys.argv[1:])[:2] == ["pm", "repair"]
584: if not _pm_repair:
585:     from hermes_cli.venv_sync import prepare_launch, relaunch_command
586: 
587:     try:
588:         _launch_python = prepare_launch(_root, sys.argv[1:])
589:         if _launch_python is not None:
590:             _main_spec = getattr(sys.modules.get("__main__"), "__spec__", None)
591:             _command = relaunch_command(
592:                 _launch_python, _root, sys.argv, sys.orig_argv,
593:                 getattr(_main_spec, "name", None),
594:             )
595:             if os.name == "nt":
596:                 import subprocess
597: 
598:                 raise RelaunchExit(subprocess.call(_command))
599:             os.execv(str(_launch_python), _command)
600:     except Exception as exc:
601:         if isinstance(exc, PermissionError) and (message := install_state_permission_message(_root, exc)):
602:             print(f"hermes: {message}", file=sys.stderr)
603:             raise SystemExit(1) from None
604:         # Degrade, never brick the CLI: the previous dependency generation is still selected
605:         # (a failed sync commits nothing), so an offline or half-finished update leaves a
606:         # usable Hermes plus a warning. Activation below is the real gate — a tree whose
607:         # dependencies cannot load still exits with the repair remedy.
608:         print(f"hermes: source-update completion failed: {exc}; "
609:               "running with the previous dependencies — run `hermes update` to finish it",
610:               file=sys.stderr)
611:     try:
612:         recover_if_needed(_root)
613:         activate_dependencies(_root)
614:     except (RuntimeError, OSError) as exc:
615:         if isinstance(exc, PermissionError) and (message := install_state_permission_message(_root, exc)):
616:             print(f"hermes: {message}", file=sys.stderr)
617:             raise SystemExit(1) from None
618:         if command_argv(sys.argv[1:])[:1] != ["pm"]:
619:             print(f"hermes: {exc}; run `hermes pm repair`", file=sys.stderr)
620:             raise SystemExit(1) from None
621: install_happy_eyeballs_socket_connect()
622: export_scratch_tmp_env()
