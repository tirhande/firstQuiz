import os
import socket
import sys
import time

from PyQt5 import uic
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


form = resource_path('QuizClient.ui')
form_class = uic.loadUiType(form)[0]


class connectQuizServer(QThread):
    sig_msg = pyqtSignal(str)
    sig_err = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)

        self.HOST = ''
        self.PORT = 0
        self.msg = ''
        self.tmpSocket = ''

    def setInfo(self, host, port):
        self.HOST = host
        self.PORT = port

    def sendMsg(self, sock, msg):
        try:
            sock.send(msg.encode())
        except Exception as e:
            print('sendMsg: ' + e)
            pass

    def rcvMsg(self, sock):
        while True:
            try:
                data = sock.recv(1024)
                if not data:
                    break

                self.sig_msg.emit(data.decode())
                print(data.decode())
            except:
                pass

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            self.tmpSocket = sock
            try:
                sock.connect((self.HOST, self.PORT))
                if self.msg != '':
                    msg = self.msg
                    self.sendMsg(sock, msg)
                    self.msg = ''

                while True:
                    try:
                        data = sock.recv(1024)
                        if not data:
                            break

                        self.sig_msg.emit(data.decode())
                        print(data.decode())
                    except Exception as e:
                        pass
            except Exception as e:
                self.sig_err.emit(str(e))
                print('connect exception')

    def stop(self):
        if self.isRunning():
            self.sendMsg(self.tmpSocket, '/quit')
            self.tmpSocket = ''
            self.terminate()


class clientWindow(QMainWindow, form_class):
    isMe = False

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setFixedSize(490, 570)
        self.username = ''
        self.quizSvr = connectQuizServer(self)
        self.quizSvr.sig_msg.connect(self.incomingChat)
        self.quizSvr.sig_err.connect(self.errorChat)

        self.pb_connect.clicked.connect(self.runQuizSvr)
        self.pb_tbClear.clicked.connect(self.clearText)
        self.le_inputText.returnPressed.connect(self.sendMsg)
        self.lbl_question.setStyleSheet('color: red')

    def sendMsg(self):
        if self.quizSvr.isRunning():
            self.quizSvr.sendMsg(self.quizSvr.tmpSocket, self.le_inputText.text())
            self.le_inputText.clear()

            if self.lbl_question.text() != '' and self.isMe:
                self.isMe = False
                self.le_inputText.setEnabled(False)

    def runQuizSvr(self):
        host = self.le_hostip.text()
        port = int(self.le_hostport.text())
        self.username = self.le_username.text()
        if host and port:
            if self.username:
                if self.quizSvr.isRunning():
                    self.quizSvr.msg = '/quit'
                    try:
                        self.quizSvr.stop()
                    except Exception as e:
                        self.quizSvr.terminate()
                        pass
                    print('????????? ?????????????????????.')
                    self.incomingChat('????????? ?????????????????????.\n')
                    self.lbl_question.setText('')
                    self.le_inputText.setEnabled(True)
                    self.le_hostip.setEnabled(True)
                    self.le_hostport.setEnabled(True)
                    self.le_username.setEnabled(True)
                    self.pb_connect.setText('??????')
                else:
                    self.quizSvr.setInfo(host, port)
                    self.quizSvr.msg = self.username
                    self.quizSvr.start()
                    self.le_hostip.setEnabled(False)
                    self.le_hostport.setEnabled(False)
                    self.le_username.setEnabled(False)
                    self.pb_connect.setText('?????? ??????')

            else:
                self.tb_content.append('????????? ??????????????????.')
                print('????????? ??????????????????.')
        else:
            self.tb_content.append('IP??? ????????? ??????????????????.')

    def clearText(self):
        self.tb_content.clear()

    @pyqtSlot(str)
    def incomingChat(self, msg):
        text = ''
        if msg.find('*Q:') != -1:
            self.lbl_question.setText(msg.replace('*Q:', ''))
            if msg.replace('*Q:', '') != '':
                self.le_inputText.setEnabled(False)
        elif msg.find('*?????????:') != -1:
            presenter = msg.replace('*?????????:', '')
            text = '???????????? ??????(?????? ??????)??? ???????????? ????????? ??????????????????. (?????????: ' + presenter + ')'
            if presenter != self.username:
                self.le_inputText.setEnabled(False)
            else:
                self.le_inputText.setEnabled(True)
        elif msg.find('*/next:') != -1:
            if msg.replace('*/next:', '') != self.username:
                self.isMe = False
                self.le_inputText.setEnabled(False)
            else:
                self.isMe = True
                self.le_inputText.setEnabled(True)
        elif msg.find('*/reset:') != -1:
            self.le_inputText.setEnabled(True)
        elif msg.find('*/') != -1:
            text = msg.replace('*/', '')
            # ???????????? ?????? ??????
            if text.find('?????????') != -1 or text.find('???????????????') != -1 or text.find('?????? ??????') != -1:
                self.le_inputText.setEnabled(True)
        else:
            text = msg
        # elif msg.find('######## ?????? ?????? ########') != -1:
        #     text = msg
        # else:
        #     text = time.strftime('%H:%M:%S', time.localtime(time.time())) + '  ' + msg

        if text:
            self.tb_content.append(text)

    @pyqtSlot(str)
    def errorChat(self, errmsg):
        self.tb_content.append(errmsg)
        self.le_hostip.setEnabled(True)
        self.le_hostport.setEnabled(True)
        self.le_username.setEnabled(True)
        self.pb_connect.setText('??????')


if __name__ == "__main__":
    # QApplication : ??????????????? ?????????????????? ?????????
    app = QApplication(sys.argv)
    # WindowClass??? ???????????? ??????
    myWindow = clientWindow()
    # ???????????? ????????? ???????????? ??????
    myWindow.show()
    # ??????????????? ?????????????????? ???????????????(??????????????? ???????????????) ??????
    app.exec_()
