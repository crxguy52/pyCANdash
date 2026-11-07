"""Tab that starts and stops the gmlan_dpid_logger (DpidLoggerController) from the dash.

Every controller call runs in one background thread. start() and status() touch the USB stick
(run dir, status file, log tail), and a slow or hung stick must never freeze the GUI. The thread
sends each status snapshot to the GUI thread through a Qt signal (queued across threads).

    GUI thread                         poll thread                       DpidLoggerController
    ----------                         -----------                       --------------------
    button press  -- action queue -->  start(name) / stop()  ---------> subprocess
    statusSignal  <-- snapshot ------  status() every POLL_PERIOD_S --> <STEM>_status.json, logs
"""
import logging
import queue
import threading

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QComboBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QHBoxLayout,
)

logger = logging.getLogger(__name__)

POLL_PERIOD_S = 1.0                 # How often the status is read while nothing else happens
POLL_THREAD_NAME = 'dpidLoggerTab-poll'

ACTION_START = 'start'
ACTION_STOP = 'stop'

# Button looks, (text, background color)
BUTTON_START = ('Start', '#2e7d32')         # Green
BUTTON_STOP = ('Stop', '#c62828')           # Red
BUTTON_STOPPING = ('Stopping...', '#757575')    # Grey, disabled
BUTTON_BUSY = ('...', '#757575')            # Grey, disabled: waiting for the first status after a press
BUTTON_TEXT_COLOR = '#ffffff'
BUTTON_MIN_HEIGHT_PX = 80
BUTTON_MIN_WIDTH_PX = 200
BUTTON_FONT_PT = 24
COMBO_MIN_HEIGHT_PX = 60
COMBO_FONT_PT = 16
STATE_FONT_PT = 18
WARN_STYLE = 'background:#fdd835; color:#000000; padding:4px;'
BANNER_STYLE = 'background:#c62828; color:#ffffff; font-weight:bold; padding:6px;'

FOREIGN_TESTER_TEXT = ('FOREIGN TESTER: the logger stopped itself. Do not restart it while the other '
                       'tester is connected.')
KILLED_TEXT = 'The logger did not stop in time and was KILLED: no stopSending, files may be cut short.'
NO_CONFIGS_TEXT = 'No dpid_config*.py found in {dir}'
UNREACHABLE_TEXT = 'Logger status unavailable (controller call failed)'


class DpidLoggerTab(QWidget):
    # Status snapshot (DpidLoggerController.status()) from the poll thread
    statusSignal = pyqtSignal(dict)

    def __init__(self, controller, errorText=None):
        """controller: a DpidLoggerController, or None if creating it failed (errorText says why)."""
        super(DpidLoggerTab, self).__init__()
        self.controller = controller
        self._lastStatus = None
        self._busy = False                  # A press was sent, waiting for the status that follows it
        self._actions = queue.Queue()
        self._stopEvent = threading.Event()
        self._thread = None

        self._buildWidgets()
        self.statusSignal.connect(self._showStatus)

        if controller is None:
            self.stateLabel.setText(errorText or 'DPID logger controller not available')
            self._setButton(BUTTON_START, enabled=False)
            self.configCombo.setEnabled(False)
            return

        self._setButton(BUTTON_BUSY, enabled=False)
        self._thread = threading.Thread(target=self._pollLoop, name=POLL_THREAD_NAME, daemon=True)
        self._thread.start()

    # -----------------------------------------------------------------------------------------
    # Public
    # -----------------------------------------------------------------------------------------
    def update(self, vals):
        # Called by the display timer with the CAN values like every tab; this one polls on its own
        pass

    def requestStart(self, configName):
        """Start the logger with configName (autoStart). Runs in the poll thread."""
        if self.controller is not None:
            self._actions.put((ACTION_START, configName))

    def stopPolling(self):
        """App shutdown: end the poll thread. Doesn't stop the logger (controller.shutdown() does)."""
        self._stopEvent.set()
        self._actions.put(None)             # Wake the thread

    # -----------------------------------------------------------------------------------------
    # Widgets
    # -----------------------------------------------------------------------------------------
    def _buildWidgets(self):
        self.configCombo = QComboBox()
        self.configCombo.setMinimumHeight(COMBO_MIN_HEIGHT_PX)
        self.configCombo.setFont(QFont(self.configCombo.font().family(), COMBO_FONT_PT))
        self.configCombo.setToolTip('Which logger config to run: each is a dpid_config*.py in the '
                                    'gmlan-dpid-logger config folder and sets which ECM values are logged '
                                    'and how fast. Locked while a run is going.')

        self.startStopButton = QPushButton()
        self.startStopButton.setMinimumSize(BUTTON_MIN_WIDTH_PX, BUTTON_MIN_HEIGHT_PX)
        self.startStopButton.setFont(QFont(self.startStopButton.font().family(), BUTTON_FONT_PT))
        self.startStopButton.setToolTip('Start: launch the DPID logger with the selected config, it asks the '
                                        'ECM for fast data and writes it to the USB stick.\n'
                                        'Stop: end the run cleanly (the ECM is told to stop sending).')
        self.startStopButton.clicked.connect(self._buttonPressed)

        self.stateLabel = QLabel('')
        self.stateLabel.setFont(QFont(self.stateLabel.font().family(), STATE_FONT_PT))
        self.stateLabel.setWordWrap(True)

        self.ratesLabel = QLabel('')
        self.ratesLabel.setWordWrap(True)

        self.messageLabel = QLabel('')
        self.messageLabel.setWordWrap(True)

        self.warnLabel = QLabel('')
        self.warnLabel.setWordWrap(True)
        self.warnLabel.hide()

        self.logBox = QPlainTextEdit()
        self.logBox.setReadOnly(True)
        self.logBox.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.logBox.setToolTip("Last lines of the current (or last) run's log file")

        controls = QHBoxLayout()
        controls.addWidget(self.configCombo, 1)
        controls.addWidget(self.startStopButton, 0)

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addWidget(self.stateLabel)
        layout.addWidget(self.ratesLabel)
        layout.addWidget(self.warnLabel)
        layout.addWidget(self.messageLabel)
        layout.addWidget(self.logBox, 1)
        self.setLayout(layout)

    def _setButton(self, look, enabled):
        text, color = look
        self.startStopButton.setText(text)
        self.startStopButton.setEnabled(enabled)
        self.startStopButton.setStyleSheet(f'background-color:{color}; color:{BUTTON_TEXT_COLOR};')

    # -----------------------------------------------------------------------------------------
    # GUI thread
    # -----------------------------------------------------------------------------------------
    def _buttonPressed(self):
        st = self._lastStatus
        if self._busy or st is None or st.get('stopping'):
            return
        if st.get('running'):
            self._actions.put((ACTION_STOP, None))
        else:
            configName = self.configCombo.currentText()
            if not configName:
                return
            self._actions.put((ACTION_START, configName))
        # Grey until the status that follows the action arrives (no double press)
        self._busy = True
        self._setButton(BUTTON_BUSY, enabled=False)
        self.configCombo.setEnabled(False)

    def _showStatus(self, st):
        if st.get('_afterAction'):
            self._busy = False
        if st.get('_unreachable'):
            # No status ever read: keep the dropdown, show the error, allow no action
            self.stateLabel.setText(UNREACHABLE_TEXT)
            self.messageLabel.setText(st.get('message') or '')
            self._setButton(BUTTON_BUSY, enabled=False)
            return
        self._lastStatus = st
        running, stopping = st.get('running'), st.get('stopping')

        self._updateCombo(st)

        if self._busy:
            pass                            # Keep the grey button until the action's status arrives
        elif stopping:
            self._setButton(BUTTON_STOPPING, enabled=False)
        elif running:
            self._setButton(BUTTON_STOP, enabled=True)
        else:
            self._setButton(BUTTON_START, enabled=bool(st.get('configs')))
        self.configCombo.setEnabled(not running and not self._busy)

        self.stateLabel.setText(self._stateText(st))
        self.ratesLabel.setText(self._ratesText(st))
        self.messageLabel.setText(st.get('message') or '')

        warnings, banner = self._warnings(st)
        if warnings:
            self.warnLabel.setText('\n'.join(warnings))
            self.warnLabel.setStyleSheet(BANNER_STYLE if banner else WARN_STYLE)
            self.warnLabel.show()
        else:
            self.warnLabel.hide()

        lines = list(st.get('log_tail') or [])
        if st.get('stderr_tail'):
            lines += ['', "--- logger's stderr ---"] + list(st['stderr_tail'])
        text = '\n'.join(lines)
        if self.logBox.toPlainText() != text:
            self.logBox.setPlainText(text)
            self.logBox.verticalScrollBar().setValue(self.logBox.verticalScrollBar().maximum())

    def _updateCombo(self, st):
        configs = st.get('configs') or []
        current = self.configCombo.currentText()
        if [self.configCombo.itemText(i) for i in range(self.configCombo.count())] != configs:
            self.configCombo.blockSignals(True)
            self.configCombo.clear()
            self.configCombo.addItems(configs)
            self.configCombo.blockSignals(False)
            # Keep the user's pick, else the config default
            keep = current if current in configs else st.get('default_config')
            if keep in configs:
                self.configCombo.setCurrentText(keep)
        # While a run is going, show its config
        if st.get('running') and st.get('config') in configs:
            self.configCombo.setCurrentText(st['config'])

    @staticmethod
    def _stateText(st):
        if not st.get('configs') and not st.get('running'):
            return NO_CONFIGS_TEXT.format(dir=st.get('config_dir', 'the config dir'))
        state = st.get('state')
        if state is None:
            text = 'Idle (no run yet)'
        else:
            text = f'State: {state}'
            if st.get('run'):
                text += f'  |  run {st["run"]}'
            if st.get('config'):
                text += f'  |  {st["config"]}'
        if st.get('debug'):
            text += '  |  DEBUG (simulated ECM)'
        return text

    @staticmethod
    def _ratesText(st):
        # From the logger's status file: DPID frame rates and how each item is logged
        f = st.get('file') or {}
        parts = []
        measured, planned = f.get('measured_dpid_fps'), f.get('planned_dpid_fps')
        if isinstance(measured, (int, float)) or isinstance(planned, (int, float)):
            fmt = lambda v: f'{v:.1f}' if isinstance(v, (int, float)) else '-'
            parts.append(f'DPID fps {fmt(measured)} measured / {fmt(planned)} planned')
        items = f.get('items') or []
        if items:
            counts = {}
            for it in items:
                counts[it.get('path')] = counts.get(it.get('path'), 0) + 1
            parts.append('items: ' + ', '.join(f'{n} {path}' for path, n in sorted(counts.items(), key=str)))
            dropped = [it.get('name') for it in items if it.get('path') == 'dropped']
            if dropped:
                parts.append('dropped: ' + ', '.join(str(d) for d in dropped))
        return '  |  '.join(parts)

    @staticmethod
    def _warnings(st):
        warnings, banner = [], False
        if st.get('foreign_tester'):
            warnings.append(f'{FOREIGN_TESTER_TEXT} (exit {st.get("process_exit_code")})')
            banner = True
        if st.get('adopted_pid') is not None:
            warnings.append(f'Run {st.get("run")} (pid {st["adopted_pid"]}) was started by an earlier pyCANdash '
                            'that ended without stopping it. Stop works; its exit code is unknown.')
        if st.get('killed'):
            warnings.append(KILLED_TEXT)
        if st.get('status_file_stale'):
            fileState = (st.get('file') or {}).get('state')
            warnings.append(f'The status file still says {fileState}, but the process has exited: '
                            'showing the process state.')
        return warnings, banner

    # -----------------------------------------------------------------------------------------
    # Poll thread
    # -----------------------------------------------------------------------------------------
    def _pollLoop(self):
        lastGood = None
        firstPass = True
        while not self._stopEvent.is_set():
            if firstPass:
                firstPass = False           # Show the status at once, don't wait a poll period
                action = None if self._actions.empty() else self._actions.get()
            else:
                try:
                    action = self._actions.get(timeout=POLL_PERIOD_S)
                except queue.Empty:
                    action = None
            if self._stopEvent.is_set():
                break
            try:
                if action is not None:
                    kind, configName = action
                    if kind == ACTION_START:
                        logger.info(f'dpidLoggerTab: start requested with {configName}')
                        self.controller.start(configName)
                    elif kind == ACTION_STOP:
                        logger.info('dpidLoggerTab: stop requested')
                        self.controller.stop()
                st = self.controller.status()
                st['config_dir'] = self.controller.config_dir
                lastGood = dict(st)
            except Exception as e:
                logger.error(f'dpidLoggerTab: controller call failed: {e}')
                # Still send something so a press never leaves the button stuck grey
                st = dict(lastGood) if lastGood is not None else {'_unreachable': True}
                st['message'] = f'Controller call failed: {e}'
            st['_afterAction'] = action is not None
            try:
                self.statusSignal.emit(st)
            except RuntimeError:
                break                       # Widget already deleted (app closing)
            except Exception as e:
                logger.error(f'dpidLoggerTab: status not shown: {e}')
