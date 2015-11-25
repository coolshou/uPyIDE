'''
Created on 6 de nov. de 2015

@author: martin
'''

from pyqode.qt import QtWidgets, QtCore

import time
import serial
import threading
import pyte

class Terminal(QtWidgets.QWidget):
    '''
    classdocs
    '''
    def __init__(self, parent):
        '''
        Constructor
        '''
        super(self.__class__, self).__init__(parent)
        self.setFont(QtWidgets.QFont('Monospace', 10))
        self.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.setStyleSheet("background-color : black; color : #cccccc;");
        self._workers = []
        self._serial = None
        self._thread = None
        self._stream = pyte.Stream()
        self._vt = pyte.Screen(80, 24)
        self._stream.attach(self._vt)
        self._workers.append(self._processText)

    def resizeEvent(self, event):
        charSize = self.textRect(' ').size()
        lines = int(event.size().height() / charSize.height())
        columns = int(event.size().width() / charSize.width())
        self._vt.resize(lines, columns)
        self._vt.reset()
    
    def focusNextPrevChild(self, n):
        return False
    
    def close(self):
        if self._serial:
            self._serial.close()
        if self._thread and self._thread.isAlive():
            self._thread.join()
            self._thread = None

    def open(self, port, speed):
        '''
            Open _serial 'port' as speed 'speed'
        '''
        if self._serial is serial.Serial:
            self._serial.close()
        try:
            self._serial = serial.Serial(port, speed, timeout=0.5)
            self._startThread()
        except serial.SerialException as e:
            print(e)
    
    def remoteExec(self, cmd, interceptor=None):
        if interceptor:
            self._workers.append(interceptor)
        cmd_b =  cmd if isinstance(cmd, bytes) else bytes(cmd, encoding='utf8')
        # write command
        for i in range(0, len(cmd_b), 256):
            self._serial.write(cmd_b[i:min(i + 256, len(cmd_b))])
            time.sleep(0.01)
    
    def _startThread(self):
        if self._thread and self._thread.isAlive():
            self._thread.join()
            self._thread = None
        self._thread = threading.Thread(target=self._readThread)
        self._thread.setDaemon(1)
        self._thread.start()
        
    def _readThread(self):
        while self._serial.isOpen():
            text = self._serial.read(self._serial.inWaiting() or 1)
            if text:
                self._workers = [w for w in self._workers if not w(text)]
    
    def _processText(self, text):
        self._stream.feed(text.decode(errors='ignore'))
        self.update()
        return False

    def paintEvent(self, event):
        p = QtWidgets.QPainter()
        p.begin(self)
        pal = self.palette()
        p.fillRect(QtCore.QRect(QtCore.QPoint(), self.size()),
                   pal.color(pal.Background))
        textSize = self.textRect(' ' * self._vt.size[1]).size()
        bound = QtCore.QRect(QtCore.QPoint(), textSize)
        flags = QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom
        for line in self._vt.display:
            p.drawText(bound, flags, line)
            bound.translate(0, bound.height())
        p.fillRect(self.cursorRect(), pal.color(pal.Foreground))
        p.end()

    def textRect(self, text):
        textSize = QtWidgets.QFontMetrics(self.font()).size(0, text)
        return QtCore.QRect(QtCore.QPoint(), textSize)
        
    def cursorRect(self):
        r = self.textRect(' ')
        r.moveTopLeft(QtCore.QPoint(0, 0) + 
                      QtCore.QPoint(self._vt.cursor.x * r.width(),
                                    self._vt.cursor.y * r.height()))
        return r
    
    def keyPressEvent(self, event):
        if self._serial and self._serial.isOpen():
            try:
                text = {
                    QtCore.Qt.Key_Tab: lambda x: b"\t",
                    QtCore.Qt.Key_Backspace: lambda x: b"\x7f",
                    QtCore.Qt.Key_Up: lambda x: b"\033[A",
                    QtCore.Qt.Key_Down: lambda x: b"\033[B",
                    QtCore.Qt.Key_Left: lambda x: b"\033[D",
                    QtCore.Qt.Key_Right: lambda x: b"\033[C",
                }[event.key()](event.key())
            except KeyError:
                text = bytes(event.text(), 'utf-8')
            if text:
                self._serial.write(text)
            event.accept()