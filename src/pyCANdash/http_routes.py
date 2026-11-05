"""HTTP request handler for pyCANdash's file server, plus the DPID logger control routes.

No Qt imports, so it can be tested on a PC. httpServerWorker serves it from a single-threaded
socketserver.TCPServer, so no route may block: start / stop return at once (the controller
waits for the logger in its own threads).

    GET  /logger              status page (auto-refresh while a run is alive)
    GET  /logger/status.json  DpidLoggerController.status() as JSON
    POST /logger/start        form field 'config' (one of list_configs()) -> 303 /logger
    POST /logger/stop         no fields                                   -> 303 /logger
    GET  /logger/start|stop   405 (GET can be prefetched)
    anything else             files from the data dir, as before
"""
import functools
import html
import http.server
import json
import urllib.parse

LOGGER_PAGE = '/logger'
STATUS_JSON = '/logger/status.json'
START_PATH = '/logger/start'
STOP_PATH = '/logger/stop'
ACTION_PATHS = (START_PATH, STOP_PATH)
LOGGER_PATHS = (LOGGER_PAGE, LOGGER_PAGE + '/', STATUS_JSON) + ACTION_PATHS

START_FIELD = 'config'                      # The only form field POST /logger/start accepts
MAX_FORM_BYTES = 1024                       # Larger POST bodies are refused (413)
# Per socket operation (request line, headers, body, each send). Without it an idle connection (a
# browser's speculative preconnect) blocks this single-threaded server, Stop included, until the
# browser drops it. Long enough not to abort a big BLF download to a phone on weak Wi-Fi.
SOCKET_TIMEOUT_S = 15.0
REFRESH_S = 2                               # Status page reload period while a run is alive
FOREIGN_TESTER_BANNER = ('FOREIGN TESTER: the logger stopped itself. Do not restart it while the '
                         'other tester is connected.')

PAGE_STYLE = """
body{font-family:sans-serif;margin:8px;font-size:16px;background:#fff;color:#000}
h1{font-size:20px;margin:4px 0}
table{border-collapse:collapse;margin:6px 0}
td,th{border:1px solid #999;padding:2px 6px;text-align:left;font-size:14px}
.banner{background:#c00;color:#fff;font-weight:bold;padding:10px;margin:6px 0;font-size:18px}
.warn{background:#fd0;padding:6px;margin:6px 0}
.msg{background:#def;padding:6px;margin:6px 0}
pre{background:#f4f4f4;padding:4px;font-size:11px;overflow-x:auto;white-space:pre}
button,select{font-size:18px;padding:6px 12px;margin:4px 0}
form{display:inline-block;margin-right:12px}
"""


def esc(value):
    """HTML-escape anything (None -> '')."""
    return '' if value is None else html.escape(str(value), quote=True)


def fmt_hex(value):
    return f'${value:X}' if isinstance(value, int) else esc(value)


def fmt_fps(value):
    return f'{value:.1f}' if isinstance(value, (int, float)) else '-'


def render_disabled_page():
    return ('<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>DPID logger</title></head><body><h1>DPID logger</h1>'
            '<p>DPID logger control is disabled (dpidLogger.enable in the pyCANdash config).</p>'
            '</body></html>')


def render_status_page(st):
    """Status page HTML from DpidLoggerController.status(). Everything rendered is escaped."""
    f = st.get('file') or {}
    alive = st['running']
    out = ['<!DOCTYPE html><html><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">']
    if alive:
        out.append(f'<meta http-equiv="refresh" content="{REFRESH_S}">')
    out.append(f'<title>DPID logger</title><style>{PAGE_STYLE}</style></head><body>')
    out.append('<h1>DPID logger</h1>')

    if st.get('foreign_tester'):
        out.append(f'<div class="banner">{esc(FOREIGN_TESTER_BANNER)} '
                   f'(exit {esc(st["process_exit_code"])})</div>')
    if st.get('message'):
        out.append(f'<div class="msg">{esc(st["message"])}</div>')
    if st.get('adopted_pid') is not None:
        out.append(f'<div class="warn">Run {esc(st.get("run"))} (pid {esc(st["adopted_pid"])}) was started by an '
                   'earlier pyCANdash that ended without stopping it. Stop works; its exit code is unknown.</div>')
    if st.get('killed'):
        out.append('<div class="warn">The logger did not stop in time and was KILLED: no stopSending, '
                   'files may be cut short.</div>')
    if st.get('status_file_stale'):
        out.append(f'<div class="warn">The status file still says {esc(f.get("state"))}, but the process '
                   'has exited: showing the process state.</div>')

    # Controls
    if alive:
        out.append(f'<form method="post" action="{STOP_PATH}"><button type="submit"'
                   f'{" disabled" if st.get("stopping") else ""}>Stop</button></form>')
    else:
        options = []
        for name in st.get('configs') or []:
            sel = ' selected' if name == st.get('default_config') else ''
            options.append(f'<option value="{esc(name)}"{sel}>{esc(name)}</option>')
        out.append(f'<form method="post" action="{START_PATH}"><select name="{START_FIELD}">'
                   f'{"".join(options)}</select> <button type="submit">Start</button></form>')
    out.append(f'<a href="{LOGGER_PAGE}">Refresh</a> | <a href="{STATUS_JSON}">status.json</a>')

    # Summary
    rows = [('State', st.get('state')),
            ('Running', 'yes' + (' (stopping)' if st.get('stopping') else '') if alive else 'no'),
            ('Run', st.get('run')), ('Config', st.get('config')), ('Started', st.get('started')),
            ('Logger pid', st.get('logger_pid')), ('Process exit code', st.get('process_exit_code')),
            ('Exit reason', st.get('exit_reason')), ('Status updated', f.get('updated')),
            ('Rate', f.get('rate')), ('Planned DPID fps', fmt_fps(f.get('planned_dpid_fps'))),
            ('Measured DPID fps', fmt_fps(f.get('measured_dpid_fps'))),
            ('Added frames fps', fmt_fps(f.get('added_frames_fps'))),
            ('Debug (simulated ECM)', st.get('debug')), ('Output dir', st.get('out_dir'))]
    out.append('<table>' + ''.join(f'<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in rows) + '</table>')

    per_dpid = f.get('measured_per_dpid_fps') or {}
    if per_dpid:
        cells = ''.join(f'<tr><td>{fmt_hex(int(k)) if str(k).isdigit() else esc(k)}</td>'
                        f'<td>{fmt_fps(v)}</td></tr>' for k, v in sorted(per_dpid.items()))
        out.append(f'<table><tr><th>DPID</th><th>Measured fps</th></tr>{cells}</table>')

    items = f.get('items') or []
    if items:
        cells = ''.join(f'<tr><td>{esc(it.get("name"))}</td><td>{esc(it.get("kind"))}</td>'
                        f'<td>{fmt_hex(it.get("id"))}</td><td>{esc(it.get("path"))}</td>'
                        f'<td>{fmt_hex(it.get("dpid"))}</td><td>{esc(it.get("reason"))}</td></tr>'
                        for it in items)
        out.append('<table><tr><th>Item</th><th>Kind</th><th>ID</th><th>Path</th><th>DPID</th>'
                   f'<th>Reason</th></tr>{cells}</table>')

    if st.get('log_source'):
        out.append(f'<p>Last {len(st["log_tail"])} lines of {esc(st["log_source"])}:</p>')
        out.append('<pre>' + esc('\n'.join(st['log_tail'])) + '</pre>')
    if st.get('stderr_tail'):
        out.append(f'<p>Last {len(st["stderr_tail"])} lines of the logger\'s stderr:</p>')
        out.append('<pre>' + esc('\n'.join(st['stderr_tail'])) + '</pre>')
    out.append('</body></html>')
    return ''.join(out)


class DataDirRequestHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler (data dir file serving) plus the /logger routes.

    controller: a DpidLoggerController, or None when dpidLogger is disabled.
    """
    timeout = SOCKET_TIMEOUT_S              # StreamRequestHandler.setup() applies it to the connection

    def __init__(self, *args, controller=None, **kwargs):
        self.controller = controller        # Before super().__init__, which handles the request
        super().__init__(*args, **kwargs)

    def _route(self):
        return urllib.parse.urlsplit(self.path).path

    # --- GET / HEAD -------------------------------------------------------------------------
    def do_GET(self):
        if self._route() in LOGGER_PATHS:
            self._logger_get(send_body=True)
        else:
            super().do_GET()

    def do_HEAD(self):
        if self._route() in LOGGER_PATHS:
            self._logger_get(send_body=False)
        else:
            super().do_HEAD()

    def _logger_get(self, send_body):
        route = self._route()
        if route in ACTION_PATHS:
            self._send(405, 'Use POST.\n', 'text/plain', send_body, extra={'Allow': 'POST'})
        elif route == STATUS_JSON:
            st = self.controller.status() if self.controller else {'enabled': False}
            self._send(200, json.dumps(st, indent=1), 'application/json', send_body)
        elif self.controller is None:
            self._send(200, render_disabled_page(), 'text/html', send_body)
        else:
            self._send(200, render_status_page(self.controller.status()), 'text/html', send_body)

    # --- POST -------------------------------------------------------------------------------
    def do_POST(self):
        route = self._route()
        if route not in LOGGER_PATHS:
            # Same answer as plain SimpleHTTPRequestHandler (it has no do_POST)
            self.send_error(501, f'Unsupported method ({self.command!r})')
            return
        if route not in ACTION_PATHS:
            self._send(405, 'Use GET.\n', 'text/plain', extra={'Allow': 'GET, HEAD'})
            return
        fields = self._read_form()
        if fields is None:
            return                          # Error already sent
        if self.controller is None:
            self._send(503, 'DPID logger control is disabled.\n', 'text/plain')
            return
        if route == START_PATH:
            values = fields.get(START_FIELD, [])
            if set(fields) != {START_FIELD} or len(values) != 1 or values[0] not in self.controller.list_configs():
                self._send(400, 'Bad request: expected exactly one form field "config" naming one of '
                                'the listed configs.\n', 'text/plain')
                return
            self.controller.start(values[0])
        else:
            if fields:
                self._send(400, 'Bad request: stop takes no form fields.\n', 'text/plain')
                return
            self.controller.stop()
        self.send_response(303)
        self.send_header('Location', LOGGER_PAGE)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _read_form(self):
        """URL-encoded form fields {name: [values]}, or None after sending an error."""
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            self._send(400, 'Bad Content-Length.\n', 'text/plain')
            return None
        if length < 0 or length > MAX_FORM_BYTES:
            self._send(413, 'Form too large.\n', 'text/plain')
            return None
        raw = b''
        if length:
            try:
                raw = self.rfile.read(length)
            except OSError:                 # socket.timeout is an OSError: client stalled or went away
                raw = None
            if raw is None or len(raw) < length:
                self.close_connection = True
                return None                 # Nothing sensible to answer
        body = raw.decode('utf-8', errors='replace')
        try:
            return urllib.parse.parse_qs(body, keep_blank_values=True, strict_parsing=bool(body))
        except ValueError:
            self._send(400, 'Bad form data.\n', 'text/plain')
            return None

    def _send(self, code, text, content_type, send_body=True, extra=None):
        data = text.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', f'{content_type}; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if send_body:
            self.wfile.write(data)


def make_handler(directory, controller=None):
    """Handler class for socketserver.TCPServer: serves directory, with the /logger routes."""
    return functools.partial(DataDirRequestHandler, directory=directory, controller=controller)
