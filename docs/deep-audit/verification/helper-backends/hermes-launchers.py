1: """Source-install launchers shared by setup, installers, and Windows repair.
2: 
3: Launchers execute store Python in isolated mode. They set the install's
4: default home and load hermes_bootstrap before the entry point. Bootstrap
5: reads the selected dependency generation at each start.
6: 
7: Windows uses distlib executables or a command-file fallback. POSIX uses
8: an executable shell wrapper. The standalone writer requires PM's store
9: interpreter before it publishes either command.
10: """
11: 
12: from __future__ import annotations
13: 
14: import json
15: import os
16: import shlex
17: import sys
18: from pathlib import Path
19: 
20: if __name__ == "__main__":
21:     sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
22: 
23: from pm.environments import owning_home_root, store_root
24: 
25: # ``sys`` attribute a launcher sets before ``import hermes_bootstrap``: pin HERMES_HOME to the
26: # install's default root once the launch-time repair ran (``hermes_bootstrap._pin_launcher_home``).
27: PIN_DEFAULT_HOME_FLAG = "_hermes_pin_default_home"
28: 
29: 
30: def _inline_string_literal(value: str) -> str:
31:     """Keep inline Python source intact through Windows PowerShell's native argv quoting."""
32:     if os.name != "nt":
33:         return repr(value)
34:     escaped = value.encode("unicode_escape").decode("ascii")
35:     return "'" + escaped.replace("'", "\\x27").replace('"', "\\x22") + "'"
36: 
37: 
38: def runtime_command(repo_root: Path, args=(), *, module: str = "hermes_cli.main",
39:                     code: str | None = None, python: str | Path | None = None,
40:                     home: str | Path | None = None) -> list[str]:
41:     """An installation-bound command, safe to persist across dependency GC.
42: 
43:     Store Python owns the ABI; bootstrap selects and leases dependencies at
44:     child start. Nix and developer interpreters retain their external owner.
45:     No selected generation or ambient PYTHONPATH is captured in the command.
46:     """
47:     root = Path(repo_root).resolve()
48:     python = python or resolve_store_python(root) or Path(sys.executable)
49:     entry = f"exec({_inline_string_literal(code)})" if code is not None else (
50:         f"runpy.run_module({_inline_string_literal(module)}, run_name='__main__', alter_sys=True)")
51:     # A literal home is pinned up front; the default one needs ``hermes_constants`` from the
52:     # checkout, so it is pinned only after ``hermes_bootstrap``'s launch-time repair (see
53:     # ``_launcher_script``), here again for a bootstrap that predates that hook.
54:     if home is not None:
55:         pin, settle = (f"os.environ['HERMES_HOME'] = os.environ.get('HERMES_HOME') or "
56:                        f"{_inline_string_literal(str(home))}; "), ""
57:     else:
58:         pin = f"sys.{PIN_DEFAULT_HOME_FLAG} = True; "
59:         settle = ("os.environ.get('HERMES_HOME') or os.environ.__setitem__('HERMES_HOME', "
60:                   "str(__import__('hermes_constants').get_default_hermes_root())); ")
61:     bootstrap = (
62:         "import os, sys, runpy; "
63:         "os.environ.pop('PYTHONHOME', None); os.environ.pop('PYTHONPATH', None); "
64:         "os.environ.pop('VIRTUAL_ENV', None); "
65:         f"sys.path.insert(0, {_inline_string_literal(str(root))}); "
66:         + pin
67:         + "import hermes_bootstrap; "
68:         + settle
69:         + entry
70:     )
71:     return [str(python), "-I", "-c", bootstrap, *args]
72: 
73: 
74: def print_runtime_command(repo_root: Path, argv: list[str]) -> None:
75:     """Machine boundary for consumers holding the exact published launcher."""
76:     import argparse
77: 
78:     parser = argparse.ArgumentParser(description="Resolve this installation's launch command.")
79:     parser.add_argument("--module", default="hermes_cli.main")
80:     parser.add_argument("args", nargs=argparse.REMAINDER)
81:     options = parser.parse_args(argv)
82:     args = options.args[1:] if options.args[:1] == ["--"] else options.args
83:     print(json.dumps(runtime_command(repo_root, args, module=options.module)))
84: 
85: 
86: def installation_command(repo_root: Path, args=(), *, module: str = "hermes_cli.main",
87:                          python: str | Path | None = None, home: str | Path | None = None) -> list[str]:
88:     """Persist a source launcher, never the versioned tool it currently uses.
89: 
90:     External/Nix installs retain their externally owned interpreter contract.
91:     Source installation/update publication refreshes the local launcher when
92:     the managed Python pin changes.
93:     """
94:     root = Path(repo_root)
95:     if resolve_store_python(root) is None:
96:         return runtime_command(root, args, module=module, python=python, home=home)
97:     prefix = [] if module == "hermes_cli.main" else ["--run-module", module]
98:     return [str(root / ".hermes" / "bin" / "hermes"), *prefix, *args]
99: 
100: #: Launcher command names — keep in lockstep with scripts/install.ps1
101: #: Publish-UserCommand and hermes_cli/_install_repair.py.
102: WINDOWS_BIN_LAUNCHERS = ("hermes", "hermes-acp")
103: 
104: #: command name -> (entry module, callable) — mirrors pyproject.toml
105: #: [project.scripts].
106: ENTRY_POINTS = {
107:     "hermes": ("hermes_cli.main", "main"),
108:     "hermes-acp": ("acp_adapter.entry", "main"),
109: }
110: 
111: 
112: def _is_windows() -> bool:
113:     return os.name == "nt"
114: 
115: 
116: def resolve_store_python(repo_root: Path, *, publication: bool = False) -> Path | None:
117:     """Read PM's committed Python tool, without adopting unrecorded bytes.
118: 
119:     Callers that PERSIST the result in a launcher (``stage_launcher`` and the
120: [CREDENTIAL-RELATED LINE OMITTED]
121:     wins over an inherited ``HERMES_RUNTIME_DIR``. The override names a store
122:     for the running process (an e2e fixture, a desktop toolchain) that a later
123:     scratch cleanup may delete, leaving the launcher to exit 127 forever
124:     (#131745). It still supplies the store when the tree records none.
125:     """
126:     if publication:
127:         own = _store_python(store_root(repo_root, honor_runtime_override=False))
128:         if own is not None:
129:             return own
130:     return _store_python(store_root(repo_root))
131: 
132: 
133: def _store_python(runtime: Path) -> Path | None:
134:     rel = "python.exe" if _is_windows() else "bin/python3"
135: 
136:     facts = runtime / "facts.json"
137:     if facts.is_file():
138:         try:
139:             packages = json.loads(facts.read_text(encoding="utf-8-sig")).get(
140:                 "packages", {}
141:             )
142:             entry = (packages.get("python") or {}).get("entry")
143:         except (OSError, ValueError):
144:             entry = None
145:         if entry:
146:             candidate = runtime / entry / rel
147:             if candidate.is_file():
148:                 return candidate
149: 
150:     return None
151: 
152: 
153: def _load_script_maker():
154:     """distlib's ScriptMaker — standalone first, then pip's vendored copy."""
155:     try:
156:         from distlib.scripts import ScriptMaker
157: 
158:         return ScriptMaker
159:     except ImportError:
160: [CREDENTIAL-RELATED LINE OMITTED]
161:     try:
162:         from pip._vendor.distlib.scripts import ScriptMaker
163: 
164:         return ScriptMaker
165:     except ImportError:
166:         return None
167: 
168: 
169: def exe_is_venv_bound(exe: Path, venv_dir: Path | None) -> bool:
170:     """True when an existing launcher exe embeds the venv interpreter —
171:     i.e. it is a copied venv console-script trampoline from the pre-pm
172:     installer, which boots through ``venv\\Scripts\\python.exe`` and must be
173:     replaced. distlib launchers append the interpreter shebang after the zip
174:     payload; both encodings are scanned to be safe."""
175:     if venv_dir is None:
176:         return False
177:     needles = set()
178:     for interpreter in (
179:         venv_dir / "Scripts" / "hermes.exe",
180:         venv_dir / "Scripts" / "hermes-acp.exe",
181:         venv_dir / "Scripts" / "python.exe",
182:         venv_dir / "bin" / "python3",
183:         venv_dir / "bin" / "hermes",
184:         venv_dir / "bin" / "hermes-acp",
185:     ):
186:         for enc in ("utf-8", "utf-16-le"):
187:             try:
188:                 needles.add(str(interpreter).encode(enc))
189:             except Exception:
190:                 continue
191:     try:
192:         data = Path(exe).read_bytes()
193:     except OSError:
194:         return False
195:     return any(needle in data for needle in needles)
196: 
197: 
198: def _write_atomic(target: Path, write) -> Path | None:
199:     """Stage under a pid-suffixed name then os.replace, so a concurrent
200:     process start never sees a torn launcher."""
201:     staging = target.with_name(f"{target.name}.stage.{os.getpid()}")
202:     try:
203:         write(staging)
204:         os.replace(staging, target)
205:         return target
206:     except OSError:
207:         try:
208:             staging.unlink()
209:         except OSError:
210: [CREDENTIAL-RELATED LINE OMITTED]
211:         return None
212: 
213: 
214: def mint_launcher(
215:     name: str,
216:     repo_root: Path,
217:     out_dir: Path,
218:     python_exe: Path,
219:     site_packages: Path | None,
220: ) -> Path | None:
221:     """Write a native launcher with the shared bootstrap script, or return None."""
222:     module, func = ENTRY_POINTS[name]
223:     out_dir = Path(out_dir)
224:     script = _launcher_script(name, Path(repo_root), site_packages)
225: 
226:     if not _is_windows():
227:         return _mint_shell_launcher(name, out_dir, python_exe, script)
228: 
229:     script_maker_cls = _load_script_maker()
230:     if script_maker_cls is not None:
231:         class _PathedScriptMaker(script_maker_cls):  # type: ignore[misc,valid-type]
232:             def _get_script_text(self, entry):
233:                 return script
234: 
235:         import tempfile
236:         from zipfile import BadZipFile, ZipFile
237: 
238:         def make(directory: Path) -> list[str]:
239:             maker = _PathedScriptMaker(None, str(directory), add_launchers=True)
240:             maker.executable = str(python_exe)
241:             maker.variants = {""}
242:             maker.clobber = True
243:             return maker.make(f"{name} = {module}:{func}", {"interpreter_args": ["-I"]})
244: 
245:         # distlib's exe ZIP records the current time, so byte equality cannot
246:         # detect an unchanged launcher. Compare its loader + shebang and script;
247:         # leave an active executable alone when only the ZIP timestamp changed.
248:         with tempfile.TemporaryDirectory(prefix=f".{name}-", dir=out_dir) as staging:
249:             try:
250:                 candidate = next((Path(p) for p in make(Path(staging))
251:                                   if Path(p).suffix.lower() == ".exe"), None)
252:             except Exception:
253:                 candidate = None
254:             if candidate is not None:
255:                 target = out_dir / candidate.name
256:                 try:
257:                     with ZipFile(target) as old, ZipFile(candidate) as new:
258:                         if (old.namelist() == new.namelist() == ["__main__.py"]
259:                                 and target.read_bytes()[:old.infolist()[0].header_offset]
260:                                 == candidate.read_bytes()[:new.infolist()[0].header_offset]
261:                                 and old.read("__main__.py") == new.read("__main__.py")):
262:                             return target
263:                 except (OSError, BadZipFile, KeyError):
264: [CREDENTIAL-RELATED LINE OMITTED]
265:                 # For changed launchers, distlib's .deleteme replacement can
266:                 # move an executable Windows still has mapped in memory.
267:                 try:
268:                     written = make(out_dir)
269:                 except Exception:
270:                     written = []
271:                 for path in written:
272:                     if Path(path).suffix.lower() == ".exe":
273:                         return Path(path)
274:         # distlib ran but produced no exe (unexpected) — fall through to cmd.
275: 
276:     # A prepared app environment need not include distlib, even when the
277:     # installer used it to publish a native exe. Keep that executable if its
278:     # embedded interpreter and script still match; replacing it with a cmd
279:     # would require unlinking the currently running exe on Windows.
280:     existing = out_dir / f"{name}.exe"
281:     from zipfile import BadZipFile, ZipFile
282:     try:
283:         with ZipFile(existing) as archive:
284:             if archive.namelist() == ["__main__.py"]:
285:                 prefix = existing.read_bytes()[:archive.infolist()[0].header_offset]
286:                 shebangs = (f"#!{python_exe} -I\n".encode("utf-8"),
287:                             f'#!"{python_exe}" -I\n'.encode("utf-8"))
288:                 # Vendored distlib trails the shebang with an extra CRLF
289:                 # before the zip; compare the shebang line itself.
290:                 tail = prefix.rstrip(b"\r\n")
291:                 if (any(tail.endswith(shebang.rstrip(b"\r\n")) for shebang in shebangs)
292:                         and archive.read("__main__.py") == script.encode("utf-8")):
293:                     return existing
294:     except (OSError, BadZipFile, KeyError):
295: [CREDENTIAL-RELATED LINE OMITTED]
296: 
297:     # The script is data to Python, not interpolated shell source.
298:     import base64
299:     encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
300:     code = f"import base64; exec(base64.b64decode('{encoded}'))"
301:     body = (
302:         "@echo off\r\n"
303:         f'"{python_exe}" -I -c "{code}" %*\r\n'
304:     )
305:     return _write_atomic(out_dir / f"{name}.cmd", lambda p: p.write_text(body, encoding="utf-8"))
306: 
307: 
308: # A killed move can tear the repair's own code (``hermes_bootstrap``, ``hermes_cli``). With the
309: # marker still there, a launcher whose checkout import failed runs the copy of the repair that the
310: # updater published beside the marker (``update_cmd_commit.publish_recovery_closure``) once every
311: # file hashes to the blob id its manifest names; a missing, torn or foreign closure (or none, from
312: # an updater predating it) is rebuilt from git's objects at the marker's ``pre`` with the recorded
313: # git or an absolute PATH entry (never one from the current directory) and verified the same way.
314: # Stdlib plus that copy only, under the same claim and checkout lock (a live writer still refuses,
315: # which exits 1 with the repair's own reason), then a relaunch from the restored tree.
316: _CLOSURE_REPAIR = """\
317: def _hermes_closure_repair():
318:     import contextlib, hashlib, io, shutil, subprocess
319:     from pathlib import Path
320:     root = Path(__ROOT__)
321:     git = root / '.git'
322:     try:
323:         if git.is_file():
324:             text = git.read_text(encoding='utf-8-sig').strip()
325:             git = root / text[7:].strip() if text.startswith('gitdir:') else git
326:         fields = dict(line.partition('=')[::2] for line in (git / __MARKER__).read_text(encoding='utf-8-sig').splitlines())
327:     except OSError:
328:         return
329:     pre = fields.get('pre', '').strip()
330:     if not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', pre):
331:         return
332:     closure = git / __CLOSURE_DIR__ / pre
333:     files = (*__CLOSURE__, __INIT__)
334: 
335:     def blob_id(data):
336:         return hashlib.new('sha1' if len(pre) == 40 else 'sha256', b'blob %d\\0' % len(data) + data).hexdigest()
337: 
338:     def verified():
339:         try:
340:             listed = dict(line.split(' ', 1)[::-1] for line in (closure / __MANIFEST__).read_text(encoding='utf-8-sig').splitlines())
341:             return (set(listed) == set(files) and listed[__INIT__] == blob_id(b'')
342:                     and all(blob_id((closure / rel).read_bytes()) == oid for rel, oid in listed.items()))
343:         except (OSError, ValueError):
344:             return False
345: 
346:     if not verified():
347:         exe = fields.get('git', '').strip()
348:         if not (os.path.isabs(exe) and os.path.isfile(exe)):
349:             names = ('git.exe',) if os.name == 'nt' else ('git',)
350:             exe = next((os.path.join(d, n) for d in os.environ.get('PATH', '').split(os.pathsep) if os.path.isabs(d)
351:                         for n in names if os.path.isfile(os.path.join(d, n))), '')
352:         if not exe:
353:             return
354: 
355:         def git_out(*args):
356:             done = subprocess.run([exe, '--no-replace-objects', '-C', str(root), *args], capture_output=True, timeout=60,
357:                                   stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
358:             if done.returncode != 0:
359:                 raise OSError(done.stderr)
360:             return done.stdout
361: 
362:         staging = closure.with_name('.%s.%d.launch' % (pre, os.getpid()))
363:         try:
364:             ids = {}
365:             for entry in git_out('ls-tree', '-z', '--full-tree', pre, '--', *__CLOSURE__).split(b'\\0'):
366:                 meta, _, rel = entry.decode('utf-8', 'replace').partition('\\t')
367:                 if meta.split()[1:2] == ['blob']:
368:                     ids[rel] = meta.split()[2]
369:             blobs = {__INIT__: b''}
370:             for rel in __CLOSURE__:
371:                 blobs[rel] = git_out('cat-file', 'blob', ids[rel])
372:                 if blob_id(blobs[rel]) != ids[rel]:  # an object that inflates to bytes pre never had
373:                     raise OSError('%s does not hash to %s' % (rel, ids[rel]))
374:             blobs[__MANIFEST__] = ''.join('%s %s\\n' % (blob_id(data), rel) for rel, data in blobs.items()).encode('utf-8')
375:             for rel, data in blobs.items():
376:                 (staging / rel).parent.mkdir(parents=True, exist_ok=True)
377:                 (staging / rel).write_bytes(data)
378:             shutil.rmtree(closure, ignore_errors=True)
379:             os.replace(staging, closure)
380:         except (OSError, KeyError, subprocess.SubprocessError):
381: [CREDENTIAL-RELATED LINE OMITTED]
382:         finally:
383:             shutil.rmtree(staging, ignore_errors=True)
384:         if not verified():
385:             return
386:     for name in [n for n in sys.modules if n.split('.')[0] in ('hermes_cli', 'hermes_bootstrap', 'hermes_constants', 'pm')]:
387:         del sys.modules[name]
388:     tree = os.path.normcase(os.path.realpath(root))
389:     sys.path[:] = [str(closure)] + [p for p in sys.path if p and os.path.normcase(os.path.realpath(p)) != tree
390:                                     and not os.path.normcase(os.path.realpath(p)).startswith(tree + os.sep)]
391:     sys.dont_write_bytecode = True
392:     said = io.StringIO()
393:     restored = False
394:     try:
395:         with contextlib.redirect_stderr(said):
396:             from hermes_cli import _early_recovery
397:             restored = _early_recovery.restore_interrupted_pull(root)
398:     except Exception as exc:
399:         said.write('hermes: the checkout cannot start after an interrupted `hermes update`, and it was not '
400:                    'repaired: %s\\n' % (exc,))
401:     if restored:
402:         sys.stderr.write('hermes: the checkout could not start after an interrupted `hermes update`; '
403:                          'repaired it with the recovery code saved before the update.\\n' + said.getvalue())
404:         _early_recovery.relaunch_after_restore()
405:     sys.stderr.write(said.getvalue() or 'hermes: the checkout cannot start after an interrupted `hermes update`; '
406:                      'launch again once the update that owns it finishes.\\n')
407:     raise SystemExit(1)
408: """
409: 
410: 
411: def _launcher_script(name: str, repo_root: Path, dependencies: Path | None) -> str:
412:     module, func = ENTRY_POINTS[name]
413:     # Profile boot repairs shared launchers: their default must stay at the
414:     # install's dependency root, not whichever profile triggered publication.
415:     #
416:     # The launch-time repair of a checkout a killed update left torn (``hermes_bootstrap`` ->
417:     # ``_early_recovery.restore_interrupted_pull``) runs before ANY other checkout module is
418:     # imported: a merge killed while writing ``hermes_constants.py`` must not stop every launch
419:     # before the repair. The default-home pin (which needs ``hermes_constants``) happens inside
420:     # ``hermes_bootstrap`` right after the repair (``_PIN_DEFAULT_HOME``), and here again for a
421:     # bootstrap that predates that hook.
422:     root = str(repo_root.resolve())
423:     from hermes_cli._early_recovery import (
424:         INTERRUPTED_PULL_MARKER,
425:         RECOVERY_CLOSURE,
426:         RECOVERY_CLOSURE_DIR,
427:         RECOVERY_CLOSURE_INIT,
428:         RECOVERY_CLOSURE_MANIFEST,
429:     )
430: 
431:     closure_repair = (_CLOSURE_REPAIR.replace("__MARKER__", repr(INTERRUPTED_PULL_MARKER))
432:                       .replace("__CLOSURE_DIR__", repr(RECOVERY_CLOSURE_DIR))
433:                       .replace("__MANIFEST__", repr(RECOVERY_CLOSURE_MANIFEST))
434:                       .replace("__INIT__", repr(RECOVERY_CLOSURE_INIT))
435:                       .replace("__CLOSURE__", repr(RECOVERY_CLOSURE))
436:                       .replace("__ROOT__", repr(root)))  # last: a path is never re-substituted
437:     return (
438:         # The repair's own stdlib, bound before the checkout root goes on sys.path: a stdlib-named
439:         # file in the tree must not run in its place ahead of the closure's verification. The first
440:         # line stays the shape gateway.status._BOOTSTRAPS recognises as this launcher (#124318).
441:         "import os, re, sys\n"
442:         "import contextlib, hashlib, io, pathlib, shutil, subprocess\n"
443:         "os.environ.pop('PYTHONHOME', None)\n"
444:         "os.environ.pop('PYTHONPATH', None)\n"
445:         f"sys.path.insert(0, {root!r})\n"
446:         + closure_repair +
447:         "if sys.argv[1:2] == ['--print-runtime-command']:\n"
448:         "    sys.dont_write_bytecode = True\n"
449:         "    from pathlib import Path\n"
450:         "    try:\n"
451:         "        from hermes_cli import _early_recovery\n"
452:         "    except Exception as exc:\n"
453:         "        if _hermes_closure_repair() or not isinstance(exc, ImportError):\n"
454:         "            raise\n"
455:         "        _early_recovery = None  # a tree without the repair: the imports below report real damage\n"
456:         f"    if _early_recovery is not None and _early_recovery.restore_interrupted_pull(Path({root!r})):\n"
457:         "        _early_recovery.relaunch_after_restore()\n"
458:         "    from hermes_constants import get_default_hermes_root\n"
459:         "    os.environ['HERMES_HOME'] = os.environ.get('HERMES_HOME') or str(get_default_hermes_root())\n"
460:         "    from hermes_cli._launchers import print_runtime_command\n"
461:         f"    print_runtime_command(Path({root!r}), sys.argv[2:])\n"
462:         "    sys.exit(0)\n"
463:         f"sys.{PIN_DEFAULT_HOME_FLAG} = True\n"
464:         "try:\n"
465:         "    import hermes_bootstrap\n"
466:         "except Exception:\n"
467:         "    _hermes_closure_repair()\n"
468:         "    raise\n"
469:         "if not os.environ.get('HERMES_HOME'):\n"
470:         "    from hermes_constants import get_default_hermes_root\n"
471:         "    os.environ['HERMES_HOME'] = str(get_default_hermes_root())\n"
472:         "if sys.argv[1:2] == ['--run-module']:\n"
473:         "    import runpy\n"
474:         "    if len(sys.argv) < 3: sys.exit('hermes: --run-module needs a module')\n"
475:         "    module = sys.argv.pop(2)\n"
476:         "    del sys.argv[1]\n"
477:         "    runpy.run_module(module, run_name='__main__', alter_sys=True)\n"
478:         "    sys.exit(0)\n"
479:         f"from {module} import {func}\n"
480:         "sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])\n"
481:         f"sys.exit({func}())\n"
482:     )
483: 
484: 
485: def _write_shell(target: Path, command: list[str]) -> Path | None:
486:     body = f'#!/bin/sh\nexec {shlex.join(command)} "$@"\n'
487:     try:
488:         if not target.is_symlink() and target.read_bytes() == body.encode("utf-8"):
489:             if os.access(target, os.X_OK):
490:                 return target
491:     except OSError:
492: [CREDENTIAL-RELATED LINE OMITTED]
493: 
494:     def write(staging: Path) -> None:
495:         staging.write_text(body, encoding="utf-8", newline="\n")
496:         staging.chmod(0o755)
497: 
498:     return _write_atomic(target, write)
499: 
500: 
501: def _mint_shell_launcher(name: str, out_dir: Path, python_exe: Path, script: str) -> Path | None:
502:     return _write_shell(out_dir / name, [str(python_exe), "-I", "-c", script])
503: 
504: 
505: def _owns_launcher(target: Path, root: Path) -> bool:
506:     """Recognize our old source/venv launchers, never a mere mention in a comment."""
507:     if target.is_symlink():
508:         return target.resolve().is_relative_to(root)
509:     try:
510: [CREDENTIAL-RELATED LINE OMITTED]
511:     except (OSError, UnicodeError, ValueError):
512:         return False
513:     paths = {str(root / p) for p in (
514:         "hermes", "run_agent.py", "venv/bin/python", "venv/bin/python3",
515:         "venv/bin/hermes",
516:         ".hermes/bin/hermes", ".hermes/bin/hermes-acp",
517:     )}
518: [CREDENTIAL-RELATED LINE OMITTED]
519:     bootstrap = f"sys.path.insert(0, {str(root)!r})"
520: [CREDENTIAL-RELATED LINE OMITTED]
521:         return True
522:     # The historical updater wrote ACP as a sibling-hermes forwarder. Adopt
523:     # it only when that sibling demonstrably belongs to this installation.
524:     if target.name == "hermes-acp":
525:         sibling = target.with_name("hermes")
526: [CREDENTIAL-RELATED LINE OMITTED]
527:                 and _owns_launcher(sibling, root))
528:     return False
529: 
530: 
531: def _publish_conveniences(root: Path, out_dir: Path, names, *, create: bool = True) -> dict[Path, bool]:
532:     """User-bin commands forward to durable local launchers, not a Python pin."""
533:     if create:
534:         out_dir.mkdir(parents=True, exist_ok=True)
535:     elif not out_dir.is_dir():
536:         return {}
537:     published = {}
538:     for name in names:
539:         target = out_dir / name
540:         if (not create or target.exists() or target.is_symlink()) and not _owns_launcher(target, root):
541:             continue
542:         before = target.lstat().st_mtime_ns if target.exists() or target.is_symlink() else None
543:         command = ([str(root / ".hermes/bin/hermes"), "--run-module", "run_agent"]
544:                    if name == "hermes-agent" else [str(root / ".hermes/bin" / name)])
545:         if _write_shell(target, command) is None:
546:             raise OSError(f"could not publish launcher {target}")
547:         published[target] = before != target.lstat().st_mtime_ns
548:     return published
549: 
550: 
551: def stage_launcher(name: str, repo_root: Path, out_dir: Path) -> Path | None:
552:     """Publish one launcher bound to store Python, or refuse missing tools."""
553:     repo_root = Path(repo_root)
554:     # A launcher outlives the process that writes it, so the inherited
555:     # runtime override must not displace the tree's own interpreter.
556:     store_python = resolve_store_python(repo_root, publication=True)
557:     if store_python is not None:
558:         path = mint_launcher(name, repo_root, out_dir, store_python, None)
559:         if path is not None and path.suffix == ".cmd":
560:             # cmd.exe prefers .exe. An older launcher must not shadow the
561:             # newly published command when distlib is unavailable.
562:             try:
563:                 (Path(out_dir) / f"{name}.exe").unlink(missing_ok=True)
564:             except OSError:
565:                 return None
566:         return path
567:     return None
568: 
569: 
570: [CREDENTIAL-RELATED LINE OMITTED]
571: [CREDENTIAL-RELATED LINE OMITTED]
572: 
573: [CREDENTIAL-RELATED LINE OMITTED]
574:     (quoted only when the path holds spaces), so full shell lexing — which
575:     would also eat Windows backslashes as escapes — is the wrong tool."""
576:     text = line.strip()
577:     if not text:
578:         return None
579:     if text[0] in "\"'":
580:         end = text.find(text[0], 1)
581:         if end == -1:
582:             return None
583:         return Path(text[1:end])
584:     return Path(text.split(None, 1)[0])
585: 
586: 
587: def _launcher_python(target: Path) -> Path | None:
588:     """Embedded interpreter of an existing launcher, else None.
589: 
590:     Fail-open: an unrecognized layout republishes exactly as before."""
591:     try:
592:         data = Path(target).read_bytes()
593:     except OSError:
594:         return None
595:     line: str | None = None
596:     suffix = Path(target).suffix.lower()
597:     if suffix == ".exe":
598:         # distlib native launcher: loader stub, "#!<python> -I" shebang, zip.
599:         # The shebang follows the loader's last NUL byte. distlib leaves
600:         # ScriptMaker.executable unquoted, and a Windows path may hold a space
601:         # or "#!", so take the whole line up to " -I".
602:         from zipfile import BadZipFile, ZipFile
603:         try:
604:             with ZipFile(target) as archive:
605:                 prefix = data[:archive.infolist()[0].header_offset]
606:         except (BadZipFile, IndexError, OSError):
607:             return None
608:         start = prefix.find(b"#!", prefix.rfind(b"\0") + 1)
609:         shebang = prefix[start + 2:].rstrip(b"\r\n") if start != -1 else b""
610:         if not shebang.endswith(b" -I") or b"\n" in shebang:
611:             return None
612:         try:
613:             return Path(shebang[:-3].decode("utf-8").strip('"'))
614:         except UnicodeDecodeError:
615:             return None
616:     else:
617:         try:
618:             text = data.decode("utf-8-sig")
619:         except UnicodeDecodeError:
620:             return None
621:         lines = text.splitlines()
622:         if suffix == ".cmd":
623:             # "@echo off", then '"<python>" -I -c "<code>" %*'. The file's
624:             # own \r\n pair gains a translated extra \r on Windows writes,
625:             # so the command may sit past a blank line — never assume its index.
626:             line = next((entry for entry in lines[1:] if entry.strip()), None)
627:             if line is None:
628:                 return None
629:         else:
630:             # POSIX shell wrapper: "#!/bin/sh", then "exec <python> -I -c ...".
631:             line = next((entry for entry in lines if entry.startswith("exec ")), None)
632:             if line is None:
633:                 return None
634:             # The writer quotes with shlex.join, which splices an apostrophe in as
635: [CREDENTIAL-RELATED LINE OMITTED]
636:             # rest of the line opens a multi-line -c argument.
637:             lexer = shlex.shlex(line.removeprefix("exec "), posix=True)
638:             lexer.whitespace_split = True
639:             try:
640: [CREDENTIAL-RELATED LINE OMITTED]
641:             except ValueError:
642:                 return None
643: [CREDENTIAL-RELATED LINE OMITTED]
644:     try:
645: [CREDENTIAL-RELATED LINE OMITTED]
646:     except (ValueError, OSError):
647:         return None
648: 
649: 
650: def _kept_shared_launcher(name: str, local: Path, store: Path, own: Path | None) -> Path | None:
651:     """Existing checkout launcher already bound outside this root's store.
652: 
653:     Checkout launchers are shared by every HERMES_HOME; a launch under one
654:     data root must never repoint them at another root's interpreter (#123238):
655:     once that root is deleted, every hermes breaks. Keep the file when it
656:     execs a live interpreter outside *store*. Missing launchers, dead
657:     interpreters and same-store repins still publish. A launcher whose
658:     interpreter is gone is never left in front of a kept one: PATHEXT resolves
659:     the ``.exe`` first, so the kept ``.cmd`` would not be the file that runs."""
660:     if own is None:
661:         # No interpreter recorded for this root: nothing says whether the
662:         # launcher is ours, and callers read the returned count as success, so
663:         # a keep here would report a half-finished store as healthy.
664:         return None
665:     candidates = [local / name] if not _is_windows() else [local / f"{name}.exe", local / f"{name}.cmd"]
666:     dead: list[Path] = []
667:     for target in candidates:
668:         try:
669:             present = target.is_file() or target.is_symlink()
670:         except OSError:
671:             continue
672:         if not present:
673:             continue
674:         python = _launcher_python(target)
675:         if python is None or python == own:
676:             continue
677:         if not python.is_file():
678:             dead.append(target)
679:             continue
680:         try:
681:             # Resolve the store's directories, not the interpreter: a store
682:             # Python may link to one shared outside it.
683:             store_dir = store.resolve()
684:             foreign = not any(parent.resolve() == store_dir for parent in python.parents)
685:         except (OSError, RuntimeError, ValueError):
686:             continue
687:         if foreign:
688:             for stale in dead:
689:                 # cmd.exe picks the .exe first; leaving a dead one would run
690:                 # instead of the command just kept. stage_launcher drops the
691:                 # same shadow when it has to mint a .cmd.
692:                 try:
693:                     stale.unlink(missing_ok=True)
694:                 except OSError:
695: [CREDENTIAL-RELATED LINE OMITTED]
696:             return target
697:     return None
698: 
699: 
700: def ensure_install_launchers(repo_root: Path, out_dir: Path) -> list[str]:
701:     """Publish exact-install commands; conveniences follow them across Python repins."""
702:     root = Path(repo_root).resolve()
703:     local = root / ".hermes" / "bin"
704:     local.mkdir(parents=True, exist_ok=True)
705:     store = store_root(root)
706:     own = resolve_store_python(root)
707:     from hermes_constants import get_default_hermes_root
708:     home = get_default_hermes_root().resolve()
709:     # The data root this checkout was installed into (<home>/hermes-agent with
710:     # <home>/tools) always republishes, which also heals an install that an
711:     # earlier foreign launch already rebound. The layout alone is not proof: a
712:     # root that only borrows the checkout can match it through
713:     # HERMES_RUNTIME_DIR=<home>/tools, so it must also own the checkout.
714:     owner = (root.parent == home and store.resolve() == (home / "tools").resolve()
715:              and owning_home_root(root) is None)
716:     written = []
717:     for name in WINDOWS_BIN_LAUNCHERS:
718:         # ponytail: one guard here covers every caller (launch, sync, repair,
719:         # install); per-home outputs below stay unguarded. Upgrade to a stamped
720:         # owning store if shared checkouts ever need cross-home repins.
721:         kept = None if owner else _kept_shared_launcher(name, local, store, own)
722:         if kept is not None:
723:             written.append(str(kept))
724:             continue
725:         if (path := stage_launcher(name, root, local)) is not None:
726:             written.append(str(path))
727:     if Path(out_dir).resolve() == local:
728:         return written
729:     if len(written) != len(WINDOWS_BIN_LAUNCHERS):
730:         return []
731:     if not _is_windows():
732:         return [str(path) for path in _publish_conveniences(root, Path(out_dir), WINDOWS_BIN_LAUNCHERS)]
733:     Path(out_dir).mkdir(parents=True, exist_ok=True)
734:     return [str(path) for name in WINDOWS_BIN_LAUNCHERS
735:             if (path := stage_launcher(name, root, Path(out_dir))) is not None]
736: 
737: 
738: def expose_cli(project_root: Path | None = None, *, create: bool = True) -> dict:
739:     """Repair PATH conveniences without taking over another installation's files.
740: 
741:     macOS CLI-first launches link the bundle's signed shims directly; Electron
742:     need not have run. Source installs converge on the store launcher owner.
743:     Shell rc/PATH registration remains installer-owned.
744: 
745:     Before dependency sync succeeds, create=False maintains only commands we
746:     already own, without loading application config or enabling new exposure.
747:     """
748:     # Resolved before the platform branch: the Windows path needs it too.
749:     from pm.paths import install_root
750: 
751:     root = Path(project_root or install_root()).resolve()
752:     if _is_windows():
753:         # The installer stages the user-facing commands into $HERMES_HOME\bin
754:         # and registers that directory in the User PATH. An update skipped both
755:         # (this used to answer "windows-installer-owned"), so a machine updated
756:         # from a release predating that convention kept the old
757:         # venv\Scripts entry and never converged on it. Mirror the installer.
758:         return _expose_windows_user_bin(root, create=create)
759:     if create:
760:         try:
761:             from hermes_cli.config import load_config
762:         except ImportError:
763:             # Installers expose after sync; never invent a config reader here.
764:             return {"ok": True, "skipped": "config-unavailable"}
765:         cli_cfg = (load_config() or {}).get("cli", {})
766:         if isinstance(cli_cfg, dict) and not cli_cfg.get("expose_on_path", True):
767:             return {"ok": True, "skipped": "config-disabled"}
768:     from hermes_cli.steward import read_install_stamp
769: 
770:     if _is_bundled_payload(root):
771:         if create and sys.platform == "darwin":
772:             return _symlink_sealed_launchers(root.parent / "bin")
773:         return {"ok": True, "skipped": "bundle-owns-launchers"}
774:     if read_install_stamp(root).get("updateMechanism") == "external":
775:         return {"ok": True, "skipped": "externally-owned"}
776:     if resolve_store_python(root, publication=True) is None:
777:         return {"ok": True, "skipped": "no-store-python"}
778:     try:
779:         local = root / ".hermes" / "bin"
780:         if len(ensure_install_launchers(root, local)) != len(WINDOWS_BIN_LAUNCHERS):
781:             return {"ok": False, "error": "source launcher publication failed"}
782:         dirs = [Path.home() / ".local" / "bin"]
783:         # Repair existing FHS/custom-home exposure, but never create new global
784:         # entries or reclaim a convenience that was repointed to another root.
785:         from hermes_constants import get_default_hermes_root
786:         for directory in (get_default_hermes_root() / "bin", Path("/usr/local/bin")):
787:             if directory not in dirs and (not create or _owns_launcher(directory / "hermes", root)):
788:                 dirs.append(directory)
789:         written = []
790:         for directory in dirs:
791:             published = _publish_conveniences(root, directory, (*WINDOWS_BIN_LAUNCHERS, "hermes-agent"), create=create)
792:             written.extend(path.name for path, changed in published.items() if changed)
793:         return {"ok": True, "written": written}
794:     except OSError as exc:
795:         return {"ok": False, "error": str(exc)}
796: 
797: 
798: def _merge_user_path(existing: str, entry: str) -> str | None:
799:     """``entry`` first, or None when the PATH already names it.
800: 
801:     Windows paths are case-insensitive and may carry a trailing separator, so
802:     compare that way rather than by exact string.
803:     """
804:     wanted = entry.rstrip("\\/")
805:     parts = [part for part in (existing or "").split(";") if part]
806:     if any(part.rstrip("\\/").casefold() == wanted.casefold() for part in parts):
807:         return None
808:     return ";".join([entry, *parts])
809: 
810: 
811: def _register_windows_user_path(entry: Path) -> str:
812:     """Put ``entry`` on the User PATH. Returns 'present' or 'added'.
813: 
814:     Preserves the stored value type: install.ps1 writes expandable entries
815:     (``%LOCALAPPDATA%\\...``), and rewriting the value as a plain string would
816:     freeze those.
817:     """
818:     import winreg  # type: ignore
819: 
820:     with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
821:                         winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
822:         try:
823:             current, kind = winreg.QueryValueEx(key, "Path")
824:         except FileNotFoundError:
825:             current, kind = "", winreg.REG_EXPAND_SZ
826:         merged = _merge_user_path(str(current), str(entry))
827:         if merged is None:
828:             return "present"
829:         if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
830:             kind = winreg.REG_EXPAND_SZ
831:         winreg.SetValueEx(key, "Path", 0, kind, merged)
832:     _broadcast_environment_change()
833:     return "added"
834: 
835: 
836: def _broadcast_environment_change() -> None:
837:     """Tell running processes the environment changed (best effort)."""
838:     import ctypes
839: 
840:     try:
841:         ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0x0002, 5000, None)  # type: ignore[attr-defined]
842:     except Exception:  # noqa: BLE001 - never fail an update over the broadcast
843: [CREDENTIAL-RELATED LINE OMITTED]
844: 
845: 
846: def _expose_windows_user_bin(root: Path, *, create: bool) -> dict:
847:     """Windows twin of expose_cli's POSIX half.
848: 
849:     Stage the user-facing commands into ``$HERMES_HOME\\bin`` and register that
850:     directory in the User PATH -- the same two things scripts/install.ps1 does --
851:     so an update converges a machine installed under the older venv\\Scripts
852:     convention instead of leaving it there forever.
853:     """
854:     from hermes_constants import get_default_hermes_root
855: 
856:     directory = get_default_hermes_root() / "bin"
857:     try:
858:         if not create:
859:             # Bootstrap: repair only commands we already own, enable nothing new.
860:             published = _publish_conveniences(root, directory, WINDOWS_BIN_LAUNCHERS, create=False)
861:             return {"ok": True, "written": [path.name for path, changed in published.items() if changed]}
862:         directory.mkdir(parents=True, exist_ok=True)
863:         written = ensure_install_launchers(root, directory)
864:         if len(written) != len(WINDOWS_BIN_LAUNCHERS):
865:             return {"ok": False, "error": "source launcher publication failed"}
866:         return {"ok": True, "path": _register_windows_user_path(directory),
867:                 "written": [Path(path).name for path in written]}
868:     except OSError as exc:
869:         return {"ok": False, "error": str(exc)}
870: 
871: 
872: def _is_bundled_payload(root: Path) -> bool:
873:     """Is ``root`` a desktop bundle's agent payload? The stamp is the
874:     authority (payload marker / desktop-app distribution), never a
875:     sibling-directory sniff; a .git tree is a dev checkout regardless."""
876:     if (root / ".git").exists():
877:         return False
878:     from hermes_cli.steward import STEWARD_DESKTOP, read_install_stamp
879: 
880:     stamp = read_install_stamp(root)
881:     if not stamp:
882:         return False
883:     return bool(stamp.get("payload")) or stamp.get("distribution") == STEWARD_DESKTOP
884: 
885: 
886: def _symlink_sealed_launchers(payload_bin) -> dict:
887:     """Link ~/.local/bin/{hermes,hermes-agent,hermes-acp} at a sealed
888:     bundle's own prebuilt shims (macOS only).
889: 
890:     Symlinks, not copies: the shims are signed as part of the app bundle,
891:     and a copy would both orphan the signature's context and go stale on
892:     every app update — a symlink into the .app follows the bundle's
893:     content wherever Squirrel.Mac swaps it.
894: 
895:     Ownership guard mirrors expose_cli's wrapper logic: an existing
896:     entry is replaced only when it is ours — a symlink into THIS app
897:     bundle's payload — or missing/broken. A user's own `hermes` (pipx,
898:     another checkout's wrapper) is never touched.
899:     """
900:     link_dir = Path.home() / ".local" / "bin"
901:     payload_root = payload_bin.parent
902:     written: list[str] = []
903:     try:
904:         link_dir.mkdir(parents=True, exist_ok=True)
905:         for name in ("hermes", "hermes-agent", "hermes-acp"):
906:             source = payload_bin / name
907:             if not source.is_file():
908:                 continue
909:             target = link_dir / name
910:             if target.is_symlink():
911:                 current = os.readlink(target)
912:                 if current == str(source):
913:                     continue  # already ours and current
914:                 # Ours if it points into this payload (stale app path from
915:                 # a previous version counts — resolve() of a dangling link
916:                 # still yields the old path text) — or dangling entirely.
917:                 points_into_payload = str(Path(current)).startswith(str(payload_root) + os.sep)
918:                 if not points_into_payload and target.exists():
919:                     continue  # a live foreign link — user's arrangement
920:             elif target.exists():
921:                 continue  # a real file we did not write — never clobber
922:             target.unlink(missing_ok=True)
923:             target.symlink_to(source)
924:             written.append(name)
925:     except OSError as exc:
926:         return {"ok": False, "error": str(exc)}
927:     return {"ok": True, "written": written, "mode": "sealed-symlinks"}
928: 
929: 
930: if __name__ == "__main__":
931:     import argparse
932: 
933:     if sys.argv[1:2] == ["--print-runtime-command"]:
934:         print_runtime_command(Path(__file__).resolve().parents[1], sys.argv[2:])
935:         raise SystemExit(0)
936: 
937:     parser = argparse.ArgumentParser(description="Publish source-install launchers.")
938:     parser.add_argument("out_dir", type=Path)
939:     args = parser.parse_args()
940:     repo_root = Path(__file__).resolve().parents[1]
941:     if resolve_store_python(repo_root, publication=True) is None:
942:         parser.exit(1, "hermes: store interpreter is missing; finish pm install before publishing launchers\n")
943:     args.out_dir.mkdir(parents=True, exist_ok=True)
944:     written = ensure_install_launchers(repo_root, args.out_dir)
945:     if len(written) != len(ENTRY_POINTS):
946:         parser.exit(1, "hermes: launcher publication failed\n")
947:     print("\n".join(written))
