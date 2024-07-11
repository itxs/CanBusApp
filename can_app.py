from gs_usb.gs_usb import GsUsb
from gs_usb.gs_usb_frame import GsUsbFrame
from gs_usb.constants import *
from PyQt5 import QtWidgets
from PyQt5.QtGui import QRegExpValidator, QIntValidator, QIcon, QFont
from PyQt5.QtCore import QRegExp, QObject, QThread, pyqtSignal, pyqtSlot
from pathlib import Path
import sys, os, time

GS_USB_NONE_ECHO_ID = 0xFFFFFFFF

class CANWorker(QObject):
    newFrame = pyqtSignal(float,int,str)
    disconnected = pyqtSignal()
    running = False
    dev = None
    startTime = 0.0

    def __init__(self, baudrate):
        super().__init__()
        devs = GsUsb.scan()
        if len(devs) == 0:
            raise Exception("USB2CAN device not found!")

        self.dev = devs[0]

        if self.dev is not None:
            if self.dev.set_bitrate(baudrate):
                self.dev.stop()
                self.dev.start(GS_CAN_MODE_NORMAL|GS_CAN_MODE_HW_TIMESTAMP)
                self.running = True

    def run(self):
        self.startTime = 0.0
        try:
            while self.running:
                if self.dev is not None:
                    frame = GsUsbFrame()
                    if self.dev.read(frame, 1):
                        if frame.echo_id == GS_USB_NONE_ECHO_ID:
                            data = ' '.join(f'{byte:02X}' for byte in frame.data[:frame.can_dlc])
                            if (self.startTime == 0.0):
                                self.startTime = frame.timestamp
                            self.newFrame.emit(frame.timestamp - self.startTime, frame.can_id, data)
        except:
            self.disconnected.emit()
        if self.dev is not None:
            self.dev.stop()

    def stop(self):
        self.running = False

    def hasDev(self):
        return self.dev is not None

class CanMsgLog(QtWidgets.QWidget):
    prevTime = 0.0
    def __init__(self, parent, canId):
        super().__init__(parent)
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.setLayout(self.verticalLayout)
        self.logTitle = QtWidgets.QLabel(self)
        self.msgList = QtWidgets.QListWidget(self)
        self.msgList.setSelectionMode(QtWidgets.QListWidget.SingleSelection)
        self.msgList.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.msgList.setFont(QFont("Consolas", 9))
        self.btClear = QtWidgets.QPushButton(self, text="Clear")
        self.btClear.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
        self.btClear.clicked.connect(self.btClearAction)
        self.btClear.setMinimumWidth(30)
        if (canId >= 0):
            self.btRemove = QtWidgets.QPushButton(self, text="Remove")
            self.btRemove.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
            self.btRemove.clicked.connect(self.btRemoveAction)
            self.btRemove.setMinimumWidth(30)
            self.logTitle.setText(f'CAN ID: {hex(canId).upper().replace('0X','0x')}')
        else:
            self.logTitle.setText('All frames')
        self.verticalLayout.addWidget(self.logTitle)
        self.verticalLayout.addWidget(self.msgList)
        self.ctrlLayout = QtWidgets.QHBoxLayout()
        self.verticalLayout.addLayout(self.ctrlLayout)
        self.ctrlLayout.addWidget(self.btClear)
        if (canId >= 0):
            self.ctrlLayout.addWidget(self.btRemove)
        self.prevTime = 0.0

    def addData(self, timestamp, data):
        if self.msgList is not None:
            #if (self.prevTime == 0):
            #    self.msgList.addItem('{} {} {:.2f}s'.format(' '.rjust(8),data, timestamp))
            #else:
            dt = timestamp - self.prevTime
            if timestamp == 0:
                dt = 8
            if dt < 0.9:
                dt = dt * 1000 # In milliseconds
                if dt < 0.9:
                    dt = dt * 1000 # In microseconds
                    dtStr = "+{:.0f}us".format(dt)
                else:
                    dtStr = "+{:.1f}ms".format(dt)
            else:
                dtStr = "+{:.2f}s".format(dt)
            self.msgList.addItem('{} {} {:.2f}s'.format(dtStr.rjust(8), data, timestamp))
            self.prevTime = timestamp
            if (self.msgList.count() > 200):
                self.msgList.takeItem(0)
            self.msgList.scrollToBottom()

    def btRemoveAction(self):
        self.msgList = None
        self.deleteLater()

    def btClearAction(self):
        self.prevTime = 0
        if self.msgList is not None:
            self.msgList.clear()

    def setInitialTime(self, time):
        self.prevTime = time

class MainWindow(QtWidgets.QMainWindow):
    worker = None
    icon = None

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAN Message Logger")
        self.setGeometry(100, 100, 800, 600)

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            path = Path(sys._MEIPASS) # type: ignore
        else:
            path = Path(__file__).parent
        self.icon = QIcon(str(Path.cwd() / path / "CAN_Logo.png"))

        self.setWindowIcon(self.icon)
        self.widget = QtWidgets.QWidget()
        self.windowLayout = QtWidgets.QVBoxLayout(self.widget)
        self.setCentralWidget(self.widget)
        self.btStartRx = QtWidgets.QPushButton(self, text="Start")
        self.btStartRx.clicked.connect(self.startRx)
        self.btAdd = QtWidgets.QPushButton(self, text="Add ID")
        self.btAdd.clicked.connect(lambda: self.addLog(self.leCanId.text()))
        self.cbAutoAdd = QtWidgets.QCheckBox("Auto add new CAN IDs", self)
        self.lBaudrate = QtWidgets.QLabel("Baudrate:", self)
        self.leBaudrate = QtWidgets.QLineEdit(self)
        self.leBaudrate.setMaximumWidth(60)
        self.leBaudrate.setValidator(QIntValidator(1, 1000000))
        self.leBaudrate.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
        self.leBaudrate.setText('500000')
        self.lCanId = QtWidgets.QLabel("CAN ID:", self)
        self.leCanId = QtWidgets.QLineEdit(self)
        self.leCanId.setMaximumWidth(60)
        self.leCanId.setValidator(QRegExpValidator(QRegExp("[0-9A-Fa-f]*")))
        self.leCanId.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
        self.controlsLayout = QtWidgets.QHBoxLayout()
        self.controlsLayout.addWidget(self.btStartRx)
        self.controlsLayout.addWidget(self.cbAutoAdd)
        self.controlsLayout.addSpacerItem(QtWidgets.QSpacerItem(20, 1, QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed))
        self.controlsLayout.addWidget(self.lCanId)
        self.controlsLayout.addWidget(self.leCanId)
        self.controlsLayout.addWidget(self.btAdd)
        self.controlsLayout.addSpacerItem(QtWidgets.QSpacerItem(20, 1, QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed))
        self.controlsLayout.addWidget(self.lBaudrate)
        self.controlsLayout.addWidget(self.leBaudrate)
        self.controlsLayout.addSpacerItem(QtWidgets.QSpacerItem(1, 1, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum))
        self.logsLayout = QtWidgets.QHBoxLayout()
        self.logsLayout.addSpacerItem(QtWidgets.QSpacerItem(1, 1, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding))
        self.windowLayout.addLayout(self.logsLayout)
        self.windowLayout.addLayout(self.controlsLayout)
        self.canLogs = dict()
        self.canIds = dict()
        self.addLog()

    def closeEvent(self, event):
        self.stopRx()

    @pyqtSlot(float, int, str)
    def updateListWidget(self, timestamp, canId, data):
        if canId in self.canLogs.keys():
            self.canLogs[canId].addData(timestamp, f'[{data}]')
        else:
            self.canLogs[-1].addData(timestamp, 'ID=0x{:X}: [{}]'.format(canId, data))
            if self.cbAutoAdd.isChecked():
                self.addLog(hex(canId))

    def addLog(self, id = ''):
        try:
            canIdTxt = id
            if canIdTxt == '':
                canId = -1
            else:
                canId = int(canIdTxt, 16)
            if canId not in self.canLogs.keys():
                canLog = CanMsgLog(self, canId)
                self.logsLayout.addWidget(canLog)
                self.canLogs[canId] = canLog
                canLog.destroyed.connect(lambda: self.canLogs.pop(canId))
        except:
            return

    def errDevNotFound(self, message):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        if self.icon is not None:
            msg.setWindowIcon(self.icon)
        msg.setText(message)
        msg.setWindowTitle("USB2CAN error")
        msg.exec_()

    def startRx(self):
        if (self.btStartRx.text() == "Start"):
            try:
                self.worker = CANWorker(int(self.leBaudrate.text()))
                if self.worker.hasDev():
                    self.readThread = QThread()
                    self.worker.moveToThread(self.readThread)
                    self.worker.newFrame.connect(self.updateListWidget)
                    self.worker.disconnected.connect(self.disconnected)
                    self.readThread.started.connect(self.worker.run)
                    self.readThread.start()
                    self.btStartRx.setText("Stop")
                    for canLog in self.canLogs.values():
                        canLog.setInitialTime(0)
            except Exception as e:
                self.stopRx()
                self.errDevNotFound(str(e))
        else:
            self.stopRx()

    def disconnected(self):
        self.stopRx()
        self.errDevNotFound("USB2CAN device has been disconnected!")

    def stopRx(self):
        self.btStartRx.setText("Start")
        if self.worker is not None:
            self.worker.stop()
            self.readThread.exit()


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
