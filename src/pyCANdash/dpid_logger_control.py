"""Start, stop and watch the gmlan_dpid_logger as a subprocess.

The logger transmits diagnostic requests to the ECM and installs its own signal handlers,
threading.excepthook and logging, so it never runs inside the Qt process. This module has no Qt
or gpiozero imports so it can be tested on a PC.

Contract: gmlan-dpid-logger/docs/interfaces.md (CLI, exit codes, <STEM>_* files, _status.json
schema 1, stop rules, console rule).

    HTTP thread                       DpidLoggerController                   logger process
    -----------                       --------------------                   --------------
    start(name)  -- validate -------> Popen(python -I -m gmlan_dpid_logger)  writes <STEM>_*
                                       '- waiter thread: popen.wait()  <---- exit code
    stop()       -- returns at once -> stop signal (SIGTERM / CTRL_BREAK)
                                       '- stop thread: wait, kill if stuck
    status()     -- reads files -----> <STEM>_status.json, <STEM>_dpid.log / _stderr.txt

Orphan (Linux): a logger left running by an earlier pyCANdash that died hard. At construction
the controller looks in /proc for a process whose command line is exactly ours with this
out_dir, and adopts it: shown on the page, Stop sends SIGTERM to it, start is refused until it
has exited. It is never started or restarted, and a pid is signalled only after its command line
was checked again right before.
"""
import datetime
import glob
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------------------------
LOGGER_MODULE = 'gmlan_dpid_logger'         # python -m target
CONFIG_SUBDIR = 'config'                    # Selection configs, relative to projectDir
CONFIG_GLOB = 'dpid_config*.py'             # Configs offered in the dropdown
DEFAULT_OUT_SUBDIR = 'dpid'                 # path = <dataDir>/<this> when the cfg path is None
VENV_PYTHON_LINUX = ('.venv', 'bin', 'python')
VENV_PYTHON_WINDOWS = ('.venv', 'Scripts', 'python.exe')

RUN_NAME_FORMAT = '%Y-%m-%d_%H-%M-%S'       # Contract: local start time, safe on FAT
RUN_NAME_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}')   # Contract charset and length
RUN_NAME_MAX_TRIES = 100                    # Suffixes tried when a STEM is already used
# Our file: the logger's stderr only (its console log, the exit 2/10 messages written before the
# logfile exists, tracebacks). Its stdout is the 5 Hz live table: DEVNULL, or it grows this file
# on the USB stick by megabytes per hour. The logfile has everything the console log has.
STDERR_SUFFIX = '_stderr.txt'
LOG_SUFFIX = '_dpid.log'
STATUS_SUFFIX = '_status.json'
# Every file of a run; a STEM is free only if none of these exists (contract: exit 10 otherwise)
RUN_FILE_SUFFIXES = (STDERR_SUFFIX, LOG_SUFFIX, STATUS_SUFFIX, '_dpid_map.json', '_dpid.csv',
                     '_debug_bus.blf')
ROOT_MOUNT = '/'                            # Linux: a run dir on this mount is on the RAM overlay (Pi)

# The contract allows up to 15 s in 'stopping' before a stop counts as stuck
CONTRACT_STOPPING_MAX_S = 15.0
STOP_TIMEOUT_S = 20.0                       # Wait this long after the stop signal, then kill
KILL_WAIT_S = 5.0                           # Wait after the kill for the process to be reaped

STATUS_READ_TRIES = 3                       # Contract: retry on OSError / invalid JSON
STATUS_READ_RETRY_S = 20e-3
TAIL_READ_MAX_BYTES = 64 * 1024             # Read at most this much from the end of a log
LOG_LINES_DEFAULT = 50
STDERR_LINES_ON_FAILURE = 20                # stderr lines shown next to the log after a failed run

PROC_DIR = '/proc'                          # Orphan detection (Linux only)
ORPHAN_POLL_S = 0.5                         # How often an adopted logger is checked for exit

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFIG_REJECTED = 10
EXIT_OTHER_TESTER_AT_START = 11
EXIT_FOREIGN_TESTER_MID_RUN = 12
FOREIGN_TESTER_EXIT_CODES = (EXIT_OTHER_TESTER_AT_START, EXIT_FOREIGN_TESTER_MID_RUN)
TERMINAL_STATES = ('stopped', 'aborted', 'failed')
STATE_LAUNCHING = 'launching'               # Process running, no status file yet
STATE_KILLED = 'killed'                     # We had to kill it (no clean stop)
STATE_UNKNOWN = 'unknown'                   # Adopted logger: no exit code and no terminal status file

IS_WINDOWS = sys.platform == 'win32'
SIGNAL_STOP = signal.SIGTERM
SIGNAL_KILL = getattr(signal, 'SIGKILL', None)      # Linux only


def state_for_exit_code(exit_code):
    """Terminal state the contract assigns to a process exit code."""
    if exit_code == EXIT_OK:
        return 'stopped'
    if exit_code in FOREIGN_TESTER_EXIT_CODES:
        return 'aborted'
    return 'failed'


def make_run_name(now=None):
    """Local time STEM, YYYY-MM-DD_HH-MM-SS (contract charset)."""
    return (now or datetime.datetime.now()).strftime(RUN_NAME_FORMAT)


def read_status_file(status_path):
    """Read <STEM>_status.json, retrying while the logger replaces it. None if not readable."""
    for attempt in range(STATUS_READ_TRIES):
        try:
            with open(status_path, encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            if not os.path.exists(status_path + '.tmp'):
                return None                 # Not written yet (no replace in progress)
        except (OSError, ValueError):
            pass                            # Being replaced (Windows) or a partial read
        if attempt < STATUS_READ_TRIES - 1:
            time.sleep(STATUS_READ_RETRY_S)
    return None


def tail_lines(file_path, n_lines):
    """Last n_lines of a text file (UTF-8, undecodable bytes replaced). [] if not readable."""
    try:
        with open(file_path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TAIL_READ_MAX_BYTES))
            data = f.read()
    except OSError:
        return []
    lines = data.decode('utf-8', errors='replace').splitlines()
    if size > TAIL_READ_MAX_BYTES and lines:
        lines = lines[1:]                   # First line is probably cut
    return lines[-n_lines:] if n_lines > 0 else []


def mount_point(path):
    """Mount point of the file system an existing path is on."""
    path = os.path.realpath(path)
    while not os.path.ismount(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return path


def read_cmdline(pid, proc_dir=None):
    """argv of a Linux process (/proc/<pid>/cmdline). None if it is gone, a zombie or unreadable."""
    try:
        with open(os.path.join(proc_dir or PROC_DIR, str(pid), 'cmdline'), 'rb') as f:
            raw = f.read()
    except OSError:
        return None
    if not raw:
        return None                         # Zombie or kernel thread
    return [a.decode('utf-8', errors='replace') for a in raw.rstrip(b'\0').split(b'\0')]


def parse_logger_cmdline(argv, out_dir):
    """(run name, config) if argv is a logger started exactly the way _command() starts one, with
    --out-dir out_dir; else None. This check is what makes a pid verifiably our logger."""
    if not argv or argv[1:4] != ['-I', '-m', LOGGER_MODULE]:
        return None
    args = argv[4:]
    opts = {}
    for flag in ('--config', '--out-dir', '--run-name'):
        if args.count(flag) != 1 or args.index(flag) + 1 >= len(args):
            return None
        opts[flag] = args[args.index(flag) + 1]
    if os.path.normcase(os.path.abspath(opts['--out-dir'])) != os.path.normcase(os.path.abspath(out_dir)):
        return None
    if not RUN_NAME_PATTERN.fullmatch(opts['--run-name']):
        return None
    return opts['--run-name'], opts['--config']


def find_orphan_loggers(out_dir, proc_dir=None):
    """[(pid, run name, config)] of live loggers writing to out_dir, oldest run first. [] without /proc."""
    proc_dir = proc_dir or PROC_DIR
    try:
        entries = os.listdir(proc_dir)
    except OSError:
        return []
    found = []
    for entry in entries:
        if not entry.isdigit() or int(entry) == os.getpid():
            continue
        parsed = parse_logger_cmdline(read_cmdline(entry, proc_dir), out_dir)
        if parsed:
            found.append((int(entry),) + parsed)
    return sorted(found, key=lambda o: o[1])


def any_logger_pids(proc_dir=None, exclude=()):
    """pids of every live 'python -I -m gmlan_dpid_logger' (any out dir), from /proc. Only used to
    refuse a start, never to signal. [] without /proc."""
    proc_dir = proc_dir or PROC_DIR
    try:
        entries = os.listdir(proc_dir)
    except OSError:
        return []
    pids = []
    for entry in entries:
        if not entry.isdigit() or int(entry) == os.getpid() or int(entry) in exclude:
            continue
        argv = read_cmdline(entry, proc_dir)
        if argv and argv[1:4] == ['-I', '-m', LOGGER_MODULE]:
            pids.append(int(entry))
    return sorted(pids)


def signal_process_group(pid, sig):
    """Linux: signal pid's process group if pid leads it (the logger has its own session), else pid."""
    if os.getpgid(pid) == pid:
        os.killpg(pid, sig)
    else:
        os.kill(pid, sig)


class DpidLoggerController:
    """Runs at most one gmlan_dpid_logger process. Thread-safe; no method blocks except shutdown().

    cfg: the 'dpidLogger' block of the pyCANdash config. data_dir: pyCANdash's data dir, used
    when cfg['path'] is None.
    """

    def __init__(self, cfg, data_dir=None, stop_timeout_s=STOP_TIMEOUT_S):
        self.cfg = dict(cfg)
        self.stop_timeout_s = stop_timeout_s
        self.project_dir = os.path.abspath(self.cfg['projectDir'])
        self.config_dir = os.path.join(self.project_dir, CONFIG_SUBDIR)
        self.python = self.cfg.get('python') or os.path.join(
            self.project_dir, *(VENV_PYTHON_WINDOWS if IS_WINDOWS else VENV_PYTHON_LINUX))
        if self.cfg.get('path'):
            self.out_dir = os.path.abspath(self.cfg['path'])
        elif data_dir is not None:
            self.out_dir = os.path.abspath(os.path.join(data_dir, DEFAULT_OUT_SUBDIR))
        else:
            raise ValueError('dpidLogger: path is None and no data dir was given')
        self.debug = bool(self.cfg.get('debug', False))
        self.debug_args = self._check_debug_args(self.cfg.get('debugArgs') or [])
        self.log_lines = int(self.cfg.get('logLines', LOG_LINES_DEFAULT))
        self.default_config = self.cfg.get('config')
        self.allow_root_fs = self.cfg.get('allowRootFs') is True

        self._lock = threading.RLock()
        self._popen = None
        self._adopted_pid = None            # Orphan logger we adopted (no Popen), Linux only
        self._exited = threading.Event()
        self._exited.set()                  # Nothing running
        self._exit_code = None
        self._run = None                    # STEM of the current / last run
        self._config = None                 # Config name of the current / last run
        self._started = None                # Local time the process was started
        self._stop_requested = False
        self._killed = False
        self._message = None                # Last controller message for the status page
        self._shut_down = False
        self._shutdown_deadline = None      # time.monotonic() by which shutdown() gives up

        logger.info(f'dpidLogger: python {self.python}, project {self.project_dir}, out dir {self.out_dir}, '
                    f'debug {self.debug}')
        if not os.path.isfile(self.python):
            logger.error(f'dpidLogger: python not found: {self.python}')
        if not os.path.isdir(self.config_dir):
            logger.error(f'dpidLogger: config dir not found: {self.config_dir}')
        if not IS_WINDOWS:
            self._adopt_orphan()

    # -----------------------------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------------------------
    def list_configs(self):
        """Selection config file names offered for start(), sorted."""
        return sorted(os.path.basename(p) for p in glob.glob(os.path.join(self.config_dir, CONFIG_GLOB))
                      if os.path.isfile(p))

    def is_running(self):
        return not self._exited.is_set()

    def start(self, config_name):
        """Start the logger with config_name (one of list_configs()). Returns (ok, message)."""
        with self._lock:
            if self._shut_down:
                return self._refuse('Not started: pyCANdash is shutting down')
            if self.is_running():
                return self._refuse(f'Not started: the logger is already running (run {self._run}). '
                                    'Stop it first.')
            # Any other logger (a 2nd orphan, one with another out dir, one started by hand): never two
            others = [] if IS_WINDOWS else any_logger_pids()
            if others:
                return self._refuse(f'Not started: another gmlan_dpid_logger is running (pid {others}) that this '
                                    'pyCANdash did not start and cannot stop from here. Stop it by hand.')
            if config_name not in self.list_configs():
                return self._refuse(f'Not started: unknown config {config_name!r}')
            if not os.path.isfile(self.python):
                return self._refuse(f'Not started: python not found: {self.python}')
            try:
                self._make_out_dir()
                run_name, stderr_file = self._claim_run_name()
            except OSError as e:
                return self._refuse(f'Not started: output dir {self.out_dir} not usable: {e}')

            cmd = self._command(config_name, run_name)
            logger.info(f'dpidLogger: starting run {run_name}: {subprocess.list2cmdline(cmd)} (cwd {self.out_dir})')
            try:
                popen = subprocess.Popen(cmd, cwd=self.out_dir, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=stderr_file, **self._group_kwargs())
            except OSError as e:
                return self._refuse(f'Not started: {e}')
            finally:
                stderr_file.close()         # The child has its own handle

            self._popen = popen
            self._adopted_pid = None
            self._exited.clear()
            self._exit_code = None
            self._run = run_name
            self._config = config_name
            self._started = datetime.datetime.now().isoformat(timespec='seconds')
            self._stop_requested = False
            self._killed = False
            self._message = f'Started run {run_name} with {config_name}'
            threading.Thread(target=self._wait_for_exit, args=(popen, run_name),
                             name=f'dpidLogger-waiter-{run_name}', daemon=True).start()
            return True, self._message

    def stop(self):
        """Ask the running logger to stop cleanly. Returns at once; a thread waits and kills it if stuck."""
        with self._lock:
            if not self.is_running():
                self._message = 'Stop: the logger is not running'
                return False, self._message
            if self._stop_requested:
                self._message = f'Stop: already stopping run {self._run}'
                return False, self._message
            self._stop_requested = True
            popen, run_name = self._popen, self._run
            if popen is not None:
                self._send_stop_signal(popen, run_name)
            else:
                self._signal_adopted(SIGNAL_STOP, 'stop signal')
            self._message = f'Stop requested for run {run_name}'
            threading.Thread(target=self._stop_watchdog, args=(popen, run_name),
                             name=f'dpidLogger-stop-{run_name}', daemon=True).start()
            return True, self._message

    def shutdown(self):
        """pyCANdash is closing: stop a running logger and wait for it (kill as a last resort).

        Blocks up to stop_timeout_s + 2 * KILL_WAIT_S from the first call; a later (or concurrent)
        call waits only for what is left of that deadline.
        """
        with self._lock:
            first = not self._shut_down
            if first:
                self._shut_down = True
                self._shutdown_deadline = time.monotonic() + self.stop_timeout_s + KILL_WAIT_S + KILL_WAIT_S
            running = self.is_running()
        if not running:
            return
        if first:
            logger.info('dpidLogger: shutdown, stopping the logger')
            self.stop()
        if not self._exited.wait(max(0.0, self._shutdown_deadline - time.monotonic())):
            logger.critical('dpidLogger: shutdown: the logger process is still running after the kill')

    def status(self):
        """Snapshot for the status page / status.json. Trusts the process over the status file."""
        with self._lock:
            popen, run_name = self._popen, self._run
            running = self.is_running()
            adopted = self._adopted_pid is not None
            st = {
                'enabled': True,
                'running': running,
                'stopping': running and self._stop_requested,
                'run': run_name,
                'config': self._config,
                'started': self._started,
                'out_dir': self.out_dir,
                'debug': self.debug,
                'popen_pid': popen.pid if popen else None,
                'adopted_pid': self._adopted_pid,
                'process_exit_code': self._exit_code,
                'killed': self._killed,
                'message': self._message,
                'configs': self.list_configs(),
                'default_config': self.default_config,
            }
        file_status = read_status_file(self._path(run_name, STATUS_SUFFIX)) if run_name else None
        if not isinstance(file_status, dict):
            file_status = None
        st['file'] = file_status
        st['logger_pid'] = file_status.get('pid') if file_status else st['adopted_pid']
        file_state = file_status.get('state') if file_status else None

        if run_name is None:
            st['state'] = None
        elif running:
            st['state'] = file_state or (STATE_UNKNOWN if adopted else STATE_LAUNCHING)
        elif st['killed']:
            st['state'] = STATE_KILLED
        elif st['process_exit_code'] is None:
            st['state'] = STATE_UNKNOWN     # Adopted, exited without a terminal status file
        else:
            st['state'] = state_for_exit_code(st['process_exit_code'])
        # A hard-killed process or a hung drive leaves a non-terminal state in the file
        st['status_file_stale'] = (not running and run_name is not None and file_state is not None
                                   and file_state not in TERMINAL_STATES)
        st['foreign_tester'] = (not running and st['process_exit_code'] in FOREIGN_TESTER_EXIT_CODES)
        st['exit_reason'] = file_status.get('exit_reason') if file_status else None

        st['log_source'], st['log_tail'], st['stderr_tail'] = None, [], []
        if run_name:
            log_path, stderr_path = self._path(run_name, LOG_SUFFIX), self._path(run_name, STDERR_SUFFIX)
            if os.path.isfile(log_path):
                st['log_source'], st['log_tail'] = os.path.basename(log_path), tail_lines(log_path, self.log_lines)
                # A failed run may have left a traceback on stderr only (e.g. after the logfile closed)
                if not running and st['process_exit_code'] not in (EXIT_OK, None):
                    st['stderr_tail'] = tail_lines(stderr_path, STDERR_LINES_ON_FAILURE)
            elif os.path.isfile(stderr_path):
                # No logfile: exit 2 / 10 before it was created, the reason is on stderr only
                st['log_source'], st['log_tail'] = os.path.basename(stderr_path), tail_lines(stderr_path,
                                                                                            self.log_lines)
        return st

    # -----------------------------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------------------------
    def _refuse(self, message):
        logger.warning(f'dpidLogger: {message}')
        self._message = message
        return False, message

    def _check_debug_args(self, debug_args):
        if not (isinstance(debug_args, (list, tuple)) and all(isinstance(a, str) for a in debug_args)):
            raise ValueError(f'dpidLogger: debugArgs must be a list of strings, got {debug_args!r}')
        if debug_args and not self.debug:
            logger.warning(f'dpidLogger: debugArgs {debug_args} ignored because debug is False')
            return []
        return list(debug_args)

    def _command(self, config_name, run_name):
        # -I: the cwd is the output dir on the USB stick, keep it (and PYTHON* env vars) off sys.path.
        # parse_logger_cmdline() recognises exactly this form: change both together.
        cmd = [self.python, '-I', '-m', LOGGER_MODULE, '--config', config_name, '--out-dir', self.out_dir,
               '--run-name', run_name]
        if self.debug:
            cmd += ['--debug'] + self.debug_args
        return cmd

    @staticmethod
    def _group_kwargs():
        """Own process group, so the stop signal reaches the logger (and on Windows its launcher child)."""
        if IS_WINDOWS:
            return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
        return {'start_new_session': True}

    def _make_out_dir(self):
        # Create only the last level: a missing parent (USB stick not mounted) must not silently
        # put the run on the RAM overlay
        exists = os.path.isdir(self.out_dir)
        parent = os.path.dirname(self.out_dir)
        if not exists and not os.path.isdir(parent):
            raise OSError(f'parent dir {parent} does not exist (USB stick not mounted?)')
        # An empty mount point dir (/mnt/usb_drive with no stick) exists on the root fs: check the mount
        if not IS_WINDOWS and not self.allow_root_fs:
            where = mount_point(self.out_dir if exists else parent)
            if where == ROOT_MOUNT:
                raise OSError(f'{self.out_dir} is on the root file system (the RAM overlay on the Pi), not on a '
                              'mounted drive (USB stick not mounted?). Set allowRootFs to allow it.')
        if not exists:
            os.mkdir(self.out_dir)

    def _path(self, run_name, suffix):
        return os.path.join(self.out_dir, run_name + suffix)

    def _claim_run_name(self):
        """Free STEM (local time, then _1, _2, ... if a run already used it) and its stderr file."""
        base = make_run_name()
        for i in range(RUN_NAME_MAX_TRIES):
            run_name = base if i == 0 else f'{base}_{i}'
            if not RUN_NAME_PATTERN.fullmatch(run_name):
                raise OSError(f'run name {run_name!r} breaks the contract charset')
            if any(os.path.exists(self._path(run_name, s)) for s in RUN_FILE_SUFFIXES):
                continue
            try:
                return run_name, open(self._path(run_name, STDERR_SUFFIX), 'xb')
            except FileExistsError:
                continue
        raise OSError(f'no free run name for {base}')

    def _send_stop_signal(self, popen, run_name):
        if popen.poll() is not None:
            return                          # Already gone; the waiter thread records it
        try:
            if IS_WINDOWS:
                # Reaches every process in the group (the venv launcher and the logger)
                os.kill(popen.pid, signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(popen.pid, SIGNAL_STOP)
            logger.info(f'dpidLogger: stop signal sent to run {run_name} (process group {popen.pid})')
        except OSError as e:
            logger.error(f'dpidLogger: could not send the stop signal to run {run_name}: {e}')

    def _stop_watchdog(self, popen, run_name):
        if not self._exited.wait(self.stop_timeout_s):
            logger.critical(f'dpidLogger: run {run_name} did not stop within {self.stop_timeout_s} s: KILLING IT. '
                            'No stopSending; the ECM drops the stream after P3C. The status file stays '
                            'non-terminal and the CSV may be cut short.')
            with self._lock:
                self._killed = True         # Before the kill, so the waiter's exit message says so
            sent = self._kill(popen, run_name) if popen is not None else self._signal_adopted(SIGNAL_KILL, 'kill')
            if not sent:
                with self._lock:
                    self._killed = False    # It exited on its own at the timeout edge
            if not self._exited.wait(KILL_WAIT_S):
                logger.critical(f'dpidLogger: run {run_name} still running after the kill')

    def _kill(self, popen, run_name):
        """True if the kill was sent."""
        if popen.poll() is not None:
            return False                    # Exited just now: its pid / group id may be reused
        try:
            if IS_WINDOWS:
                # popen.kill() would only end the venv launcher; /T takes the logger child too
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(popen.pid)], stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                popen.kill()
            else:
                os.killpg(popen.pid, SIGNAL_KILL)
            return True
        except OSError as e:
            logger.error(f'dpidLogger: kill of run {run_name} failed: {e}')
            return True                     # Assume the worst: it may have been partly killed

    def _wait_for_exit(self, popen, run_name):
        exit_code = popen.wait()
        with self._lock:
            if self._popen is popen:
                self._exit_code = exit_code
                self._message = f'Run {run_name} ended with exit {exit_code}'
                if exit_code in FOREIGN_TESTER_EXIT_CODES:
                    self._message += ': FOREIGN TESTER. Not restarted.'
                elif self._killed:
                    self._message += ' (killed after the stop timeout)'
            self._exited.set()
        log = logger.info if exit_code == EXIT_OK else logger.error
        if exit_code in FOREIGN_TESTER_EXIT_CODES:
            log = logger.critical
        log(f'dpidLogger: run {run_name} exited with code {exit_code} ({state_for_exit_code(exit_code)})')

    # --- Orphan logger (Linux) ---------------------------------------------------------------
    def _is_our_logger(self, pid, run_name):
        parsed = parse_logger_cmdline(read_cmdline(pid), self.out_dir)
        return parsed is not None and parsed[0] == run_name

    def _adopt_orphan(self):
        """Adopt a logger an earlier pyCANdash left running in out_dir. Never starts anything."""
        orphans = find_orphan_loggers(self.out_dir)
        if not orphans:
            return
        if len(orphans) > 1:
            logger.critical(f'dpidLogger: {len(orphans)} orphan loggers are running: {orphans}. Adopting the '
                            'newest only; stop the others by hand.')
        pid, run_name, config = orphans[-1]
        file_status = read_status_file(self._path(run_name, STATUS_SUFFIX))
        self._adopted_pid = pid
        self._run = run_name
        self._config = os.path.basename(config)
        self._started = file_status.get('started') if isinstance(file_status, dict) else None
        self._exited.clear()
        self._message = (f'Found run {run_name} (pid {pid}) still running from an earlier pyCANdash. '
                         'Adopted: Stop works, exit code unknown.')
        logger.warning(f'dpidLogger: {self._message}')
        threading.Thread(target=self._watch_adopted, args=(pid, run_name),
                         name=f'dpidLogger-adopted-{run_name}', daemon=True).start()

    def _watch_adopted(self, pid, run_name):
        while self._is_our_logger(pid, run_name):
            time.sleep(ORPHAN_POLL_S)
        # Not our child, so no exit code: take it from the final status write if there is one
        file_status = read_status_file(self._path(run_name, STATUS_SUFFIX))
        exit_code = None
        if isinstance(file_status, dict) and file_status.get('state') in TERMINAL_STATES:
            exit_code = file_status.get('exit_code')
        with self._lock:
            if self._adopted_pid == pid and self._popen is None:
                self._exit_code = exit_code if isinstance(exit_code, int) else None
                self._message = f'Adopted run {run_name} ended (exit {self._exit_code}, from its status file)'
                if self._exit_code in FOREIGN_TESTER_EXIT_CODES:
                    self._message += ': FOREIGN TESTER. Not restarted.'
            self._exited.set()
        logger.info(f'dpidLogger: adopted run {run_name} (pid {pid}) exited, exit code {exit_code}')

    def _signal_adopted(self, sig, what):
        """Signal the adopted logger, only if its pid still has our logger's command line. True if sent."""
        with self._lock:
            pid, run_name = self._adopted_pid, self._run
        if pid is None or not self._is_our_logger(pid, run_name):
            logger.warning(f'dpidLogger: {what} not sent: pid {pid} is no longer run {run_name}')
            return False
        try:
            signal_process_group(pid, sig)
            logger.info(f'dpidLogger: {what} sent to adopted run {run_name} (pid {pid})')
            return True
        except OSError as e:
            logger.error(f'dpidLogger: could not send the {what} to adopted run {run_name}: {e}')
            return False
