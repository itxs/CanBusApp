from gs_usb.gs_usb import GsUsb
from gs_usb.gs_usb_frame import GsUsbFrame
from gs_usb.constants import *
from PyQt5 import QtWidgets
from PyQt5.QtGui import QRegExpValidator, QIntValidator
from PyQt5.QtCore import QRegExp, QObject, QThread, pyqtSignal, pyqtSlot
import sys
GS_USB_NONE_ECHO_ID = 0xFFFFFFFF

class CANWorker(QObject):
    newFrame = pyqtSignal(float,int,str)
    running = False

    def __init__(self, baudrate):
        super().__init__()
        devs = GsUsb.scan()
        if len(devs) == 0:
            print("Can not find gs_usb device")
            return

        self.dev = devs[0]

        if not self.dev.set_bitrate(baudrate):
            print("Can not set bitrate for gs_usb")
            return

        self.dev.start(GS_CAN_MODE_NORMAL|GS_CAN_MODE_HW_TIMESTAMP)
        self.running = True

    def run(self):
        while self.running:
            frame = GsUsbFrame()
            if self.dev.read(frame, 1):
                if frame.echo_id == GS_USB_NONE_ECHO_ID:
                    data_hex = ' '.join(f'{byte:02x}' for byte in frame.data[:frame.can_dlc])
                    self.newFrame.emit(frame.timestamp, frame.can_id, data_hex)
        self.dev.stop()

    def stop(self):
        self.running = False

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
        if (canId != 0):
            self.btRemove = QtWidgets.QPushButton(self, text="Remove")
            self.btRemove.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
            self.btRemove.clicked.connect(self.btRemoveAction)
            self.logTitle.setText(f'CAN ID: {hex(canId).upper().replace('0X','0x')}')
        else:
            self.logTitle.setText('All frames')
        self.verticalLayout.addWidget(self.logTitle)
        self.verticalLayout.addWidget(self.msgList)
        if (canId != 0):
            self.verticalLayout.addWidget(self.btRemove)
        self.prevTime = 0.0

    def addData(self, timestamp, data):
        if self.msgList is not None:
            if (self.prevTime == 0):
                self.msgList.addItem('{:.3f}s  {}'.format(timestamp, data))
            else:
                self.msgList.addItem('{:.3f}s  {}  +{:.2f}ms'.format(timestamp, data, (timestamp - self.prevTime) * 1000))
            self.prevTime = timestamp
            self.msgList.scrollToBottom()
            if (self.msgList.count() > 200):
                self.msgList.takeItem(0)

    def btRemoveAction(self):
        self.msgList = None
        self.deleteLater()

class MainWindow(QtWidgets.QMainWindow):
    worker = None

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAN Message Logger")
        self.setGeometry(100, 100, 800, 600)
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
        self.addLog('')

    def closeEvent(self, event):
        self.stopRx()

    @pyqtSlot(float, int, str)
    def updateListWidget(self, timestamp, canId, data):
        if canId != 0 and canId in self.canLogs.keys():
            self.canLogs[canId].addData(timestamp, data)
        else:
            self.canLogs[0].addData(timestamp, 'ID 0x{:X}: [{}]'.format(canId, data))
            if self.cbAutoAdd.isChecked():
                self.addLog(hex(canId))

    def addLog(self, id):
        try:
            canIdTxt = id
            if canIdTxt == '':
                canIdTxt = '0'
            canId = int(canIdTxt, 16)
            if canId not in self.canLogs.keys():
                canLog = CanMsgLog(self, canId)
                self.logsLayout.addWidget(canLog)
                self.canLogs[canId] = canLog
                canLog.destroyed.connect(lambda: self.canLogs.pop(canId))
        except:
            return

    def startRx(self):
        if (self.btStartRx.text() == "Start"):
            self.btStartRx.setText("Stop")
            self.readThread = QThread()
            self.worker = CANWorker(int(self.leBaudrate.text()))
            self.worker.moveToThread(self.readThread)
            self.worker.newFrame.connect(self.updateListWidget)
            self.readThread.started.connect(self.worker.run)
            self.readThread.start()
        else:
            self.btStartRx.setText("Start")
            self.stopRx()

    def stopRx(self):
        if self.worker is not None:
            self.worker.stop()
            self.readThread.exit()


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
