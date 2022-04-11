import configparser
import socketserver
import threading
import time
import random
import requests
import xmltodict
import json
import re
from threading import Thread
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

global checkResult, wordDef

config = configparser.ConfigParser()
config.read('config.ini')

HOST = config['QUIZ']['HOST']
PORT = int(config['QUIZ']['PORT'])
AUTHKEY = config['QUIZ']['AUTHKEY']

lock = threading.Lock()  # syncronized 동기화 진행하는 스레드 생성


def checkCorrectWord(word):
    tmpReq = reqCorrectWord(word)
    tmpReq.start()
    tmpReq.join()
    global checkResult
    return checkResult['channel']


def check_english(word):
    is_english = re.compile('[-a-zA-Z]')
    temp = is_english.findall(word)
    if len(temp) > 0:
        return False
    else:
        return True


def SplitChoSung(word):
    """
    한글 단어를 입력받아서 초성/중성/종성을 구분하여 리턴해줍니다.
    """
    ####################################
    # 초성 리스트. 00 ~ 18
    CHOSUNG_LIST = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    # 중성 리스트. 00 ~ 20
    JUNGSUNG_LIST = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
    # 종성 리스트. 00 ~ 27 + 1(1개 없음)
    JONGSUNG_LIST = [' ', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    ####################################
    r_lst = []
    for w in list(word.strip()):
        if '가' <= w <= '힣':
            ch1 = (ord(w) - ord('가')) // 588
            ch2 = ((ord(w) - ord('가')) - (588 * ch1)) // 28
            ch3 = (ord(w) - ord('가')) - (588 * ch1) - 28 * ch2
            r_lst.append(CHOSUNG_LIST[ch1])
            # r_lst.append([CHOSUNG_LIST[ch1], JUNGSUNG_LIST[ch2], JONGSUNG_LIST[ch3]])
        else:
            r_lst.append(w)
            # r_lst.append([w])
    return r_lst


class UserManager:
    def __init__(self):
        self.users = {}  # 사용자의 등록 정보를 담을 사전 {사용자 이름:(소켓,주소),...}
        self.userList = []
        self.playUser = 0
        self.presenter = ''
        self.isQuest = False  # 문제 출제 여부
        self.playQuiz = False  # 퀴즈 시작 여부

    def addUser(self, username, conn, addr):  # 사용자 ID를 self.users에 추가하는 함수
        if username in self.users:  # 이미 등록된 사용자라면
            conn.send('이미 있는 이름입니다.\n'.encode())
            return None
        # 새로운 사용자를 등록함
        lock.acquire()  # 스레드 동기화를 막기위한 락
        self.users[username] = (conn, addr)
        self.userList.append(username)
        lock.release()  # 업데이트 후 락 해제
        self.sendMessageToAll('[' + username + ']님이 입장했습니다. (현재 참여자 수 [' + str(len(self.users)) + '명])')
        time.sleep(0.1)
        self.sendMessageToAll('참여인원 [' + ','.join(self.users) + ']')
        time.sleep(0.1)
        print('[' + username + ']님이 입장했습니다. (퀴즈 참여자 수 [' + str(len(self.users)) + '명]')
        return username

    def removeUser(self, username):  # 사용자를 제거하는 함수
        if username not in self.users:
            return
        continueFlag = 0
        try:
            if self.playQuiz and not self.isQuest and self.userList[0] == username:
                self.playQuiz = False
                continueFlag = 1
            elif self.playQuiz and self.isQuest and self.userList[self.playUser] == username:
                continueFlag = 2
        except:
            pass

        lock.acquire()
        del self.users[username]
        self.userList.remove(username)
        lock.release()

        self.sendMessageToAll('[' + username + ']님이 퇴장했습니다. (퀴즈 참여자 수 [' + str(len(self.users)) + '명])')
        time.sleep(0.1)

        if len(self.users) > 1:
            if continueFlag == 1:
                self.startQuiz()
            elif continueFlag == 2:
                self.nextPlayer()

        print('[' + username + ']님이 퇴장했습니다. (퀴즈 참여자 수 [' + str(len(self.users)) + '명]')

    def messageHandler(self, username, msg):  # 전송한 msg를 처리하는 부분
        print(msg)
        if msg.find('*/') != -1 or msg.find('*Q') != -1:
            self.sendMessageToAll(msg)
            return

        if msg[0] != '/':  # 보낸 메세지의 첫문자가 '/'가 아니면
            self.sendMessageToAll(username + ': ' + msg)
            return
        # if msg.strip() == '/?': # 보낸 메세지가 '/?'이면
        # self.removeUser(username)

        # if msg.strip() == '/인원': # 보낸 메세지가 '/인원'이면
        #     self.sendMessageToAll('총 인원 : %d명' %(len(self.users)))
        #     self.sendMessageJoinMember()
        if msg.strip() == '/시작':
            self.sendMessageToAll(username + ': ' + msg)
            time.sleep(0.1)
            if len(self.users) > 1:
                if not self.playQuiz:
                    print('퀴즈를 시작합니다.')
                    self.startQuiz()
            else:
                self.sendMessageToAll('*/2명 이상이 있어야 시작할수 있습니다.')
                time.sleep(0.1)
            return -1
        elif msg.strip() == '/포기':
            self.sendMessageToAll(username + ': ' + msg)
            time.sleep(0.1)
            if self.playQuiz or self.isQuest:
                return -2
            else:
                return -1
        elif msg.strip() == '/quit' or msg.strip() == '/퇴근':  # 보낸 메세지가 'quit'이면
            self.removeUser(username)
            return -3

    def startQuiz(self):
        if not self.playQuiz:
            while True:
                random.shuffle(self.userList)
                pickuser = self.userList[0]
                if pickuser != self.presenter:
                    self.presenter = pickuser
                    break
            msg = '*출제자:' + self.presenter
            self.playQuiz = True
            self.sendMessageToAll(msg)
            time.sleep(0.1)

    def endQuiz(self):
        self.playQuiz = False
        self.playUser = 0
        self.isQuest = False
        self.presenter = []

    def nextPlayer(self):
        if self.playQuiz:
            self.playUser += 1
            if self.playUser + 1 > len(self.userList):
                self.playUser = 0
            msg = '다음 차례: ' + self.userList[self.playUser]
            self.sendMessageToAll(msg)
            time.sleep(0.1)
            msg = '*/next:' + self.userList[self.playUser]
            self.sendMessageToAll(msg)
            time.sleep(0.1)

    def sendMessageToPer(self, username, msg):
        pass

    def sendMessageToAll(self, msg):
        for conn, addr in self.users.values():
            conn.send(msg.encode())


class WordManager:
    def __init__(self):
        self.QuestionWord = ''
        self.words = []

    def isExistWord(self, word):
        # 1=정답, 2=이미있는단어, 3=틀림, 4=초성불가
        result = 0
        # 초성 체크
        checkWord = ''.join(SplitChoSung(word))
        if checkWord == word:
            print('초성은 안됨')
            result = 5
            return result

        # item.sense.definition

        # 기존에 사용한 단어인지 체크
        try:
            self.words.index(word)
            result = 2
            print('몽총이 몽총이 🤭🤭')
        except ValueError:
            answerWord = checkWord
            if self.QuestionWord == answerWord:
                # 사전에 있는 단어인지 체크
                tmpResult = checkCorrectWord(word)
                if int(tmpResult['total']) > 0:
                    result = 1
                    print('정답입니다아아아~~~~~')
                    self.words.append(word)
                    global wordDef
                    if int(tmpResult['total']) > 1:
                        wordDef = '    (' + tmpResult['item'][0]['sense']['definition'] + ')'
                    else:
                        wordDef = '    (' + tmpResult['item']['sense']['definition'] + ')'
                else:
                    result = 4
                    print('사전에 없는 단어~ 몽총이 🤭')
            else:
                result = 3
                print('틀렸습니다. 공부하세요!')
        return result


class reqCorrectWord(Thread):
    def __init__(self, word):
        super().__init__()
        self.headers = {
            'Cache-Control': 'no-cache'
        }
        self.baseurl = 'https://stdict.korean.go.kr/api/search.do'
        self.key = AUTHKEY
        self.word = word

    def run(self):
        with requests.Session() as s:
            try:
                s.headers = self.headers

                param = {'key': self.key, 'q': self.word}

                response = s.get(self.baseurl, params=param, verify=False)
                if response.status_code == 200:
                    global checkResult
                    tmpDict = xmltodict.parse(response.text)
                    tmpJson = json.dumps(tmpDict)  # '{"e": {"a": ["text", "text"]}}'
                    checkResult = json.loads(tmpJson)
            except Exception as e:
                pass


class MyTcpHandler(socketserver.BaseRequestHandler):
    userman = UserManager()
    wordMgr = WordManager()

    def handle(self):  # 클라이언트가 접속시 클라이언트 주소 출력
        username = self.registerUsername()
        print('[' + username + '] 연결됨 (' + self.client_address[0] + ')')
        try:
            msg = self.request.recv(1024)
            while msg:

                tmpMsg = msg.decode()
                print(username + ': ' + tmpMsg)
                tmpCheck = self.userman.messageHandler(username, tmpMsg)
                if tmpCheck == -1:
                    msg = self.request.recv(1024)
                    continue
                elif tmpCheck == -2:
                    # 포기
                    self.userman.messageHandler(username, '*/' + username + '님이 게임을 포기하셨습니다.')
                    time.sleep(0.1)
                    self.userman.messageHandler(username, '*Q:')
                    time.sleep(0.1)
                    self.endGame(username)
                    msg = self.request.recv(1024)
                    continue
                elif tmpCheck == -3:
                    self.request.close()
                    break

                if not self.userman.playQuiz and not self.userman.isQuest:
                    pass
                else:
                    # 문제 출제
                    if not self.userman.isQuest and username == self.userman.presenter:
                        # tmpMsg
                        if len(tmpMsg) < 4:
                            if check_english(tmpMsg) and tmpMsg.isalpha():
                                checkWord = ''.join(SplitChoSung(tmpMsg))
                                print('checkword' + checkWord)
                                self.wordMgr.QuestionWord = checkWord
                                self.userman.isQuest = True
                                # 문제 출제 진행
                                msg = '*Q:' + checkWord
                                self.userman.messageHandler(username, msg)
                                time.sleep(0.1)
                                msg = '*/##### 퀴즈를 시작합니다 ##### (초성 : ' + checkWord + ')'
                                self.userman.messageHandler(username, msg)
                                time.sleep(0.1)
                                self.userman.nextPlayer()
                            else:
                                # 한글만 사용해주세요
                                # 띄어쓰기나 숫자는 불가능
                                msg = '*/영어, 숫자, 띄어쓰기는 불가합니다. 한글만 사용해주세요.'
                                self.userman.messageHandler(username, msg)
                                time.sleep(0.1)
                        else:
                            msg = '*/3글자 이하로만 출제 가능합니다.'
                            self.userman.messageHandler(username, msg)
                            time.sleep(0.1)

                    elif tmpCheck is None:
                        responseTxt = ''
                        # 답이 맞는지 체크 (result ==> 1=정답, 2=이미있는단어, 3=틀림, 4=초성불가)
                        result = self.wordMgr.isExistWord(tmpMsg)
                        if result == 1:
                            responseTxt = '정답입니다아아아~~~~~'
                        elif result == 2:
                            responseTxt = '몽총이 몽총이 🤭🤭'
                        elif result == 3:
                            responseTxt = '틀렸습니다. 공부하세요!'
                        elif result == 4:
                            responseTxt = '사전에 없는 단어~ 몽총이 🤭'
                        else:
                            responseTxt = '초성 불가!'

                        self.userman.messageHandler(username, '*/' + responseTxt)
                        time.sleep(0.1)
                        if result == 1:
                            global wordDef
                            self.userman.messageHandler(username, '*/' + wordDef)
                            time.sleep(0.1)
                            self.userman.nextPlayer()
                msg = self.request.recv(1024)

        except Exception as e:
            # print(e)
            pass

        print('[' + username + '] 접속종료 (' + self.client_address[0] + ')')
        # print('[%s] 접속종료' % self.client_address[0])
        self.userman.removeUser(username)
        if len(self.userman.users) < 2:
            self.endGame(username)

    def registerUsername(self):
        while True:
            self.request.send('****** 명령어 ******\n/시작 ==> 퀴즈 시작하기\n/포기 ==> 퀴즈 포기\n/퇴근 ==> 연결 끊기'.encode())
            time.sleep(0.1)
            tmpStr = '*Q:' + self.wordMgr.QuestionWord
            self.request.send(tmpStr.encode())
            # self.request.send('이름을 입력해주세요.'.encode())
            username = self.request.recv(1024)
            username = username.decode().strip()
            if self.userman.addUser(username, self.request, self.client_address):
                return username

    def endGame(self, username):
        self.userman.endQuiz()
        self.wordMgr.QuestionWord = ''
        self.wordMgr.words.clear()
        self.userman.messageHandler(username, '*/reset:')
        time.sleep(0.1)
        if len(self.userman.users) < 2:
            self.userman.messageHandler(username, '*/최소 참여 인원이 충족되지 않아 게임이 종료되었습니다.')
        else:
            self.userman.messageHandler(username, '*/게임이 종료되었습니다. 꼴찌 : ' + username)
        time.sleep(0.1)
        print('end')


class ChatingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


def runServer():
    print('퀴즈를 끝내려면 Ctrl-C를 누르세요.')

    try:
        server = ChatingServer((HOST, PORT), MyTcpHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print('######## 퀴즈 서버를 종료합니다. ########')
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    runServer()


