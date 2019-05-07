import socket, threading, time

import subprocess
from com.cleverworld.spring.transmitor import Utils
from multiprocessing import Process,Queue

# cmd is in root state,
STATE_ROOT = 0

# cmd is in host state
STATE_HOST = 1

# cmd is in terminal state
STATE_TERMINATOR = 2

# cmd is ready to exit
STATE_EXIT = -1

class CommandChannel(Process):
    """doc string for Command Channel"""
    isRunning = True

    def __init__(self, blSharedData, endForCommandChannel, queueWithBL, utils):
        super(CommandChannel, self).__init__()
        self.utils = utils
        self.queueWithBL = queueWithBL
        self.blSharedData = blSharedData
        self.endForCommandChannel = endForCommandChannel
        self.port = self.utils.get('command')['port']
        self.backLog = self.utils.get("transmitor")['backLog']
        self.utils.info("CommandChannel", 'init CommandChannel')
        self.msgQueue = Queue()

    def run(self):
        self.utils.info("CommandChannel", 'begin running...')
        """
                :start business
                """

        threadTerminalMsg = threading.Thread(target=self.threadTerminalMsg, name="threadTerminal")
        threadTerminalMsg.start()

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind(('0.0.0.0', self.port))
            # server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.listen(self.backLog)
        except socket.error as e:
            self.utils.error('startClientListener', e.strerror)

        while self.isRunning:
            client, address = server.accept()
            thread = threading.Thread(target=self.threadCommand, args=(client, address), name='threadCommand %s:%d'%(address[0], address[1]))
            thread.start()

    def closeSocket(self, sock):
        try:
            sock.close()
        except Exception as e:
            pass

    def threadCommand(self, client, address):
        """first mesg flag, we use it to decide the client properties"""

        # state start in STATE_ROOT
        self.utils.info("CommandChannel", "Command Channel Opened by %s:%d"%(address[0], address[1]))
        state = STATE_ROOT
        lastCmd = ""
        currentTID = -1

        client.sendall(("\r\n$%d:"%state).encode())

        while self.isRunning:
            try:
                cmd = client.recv(1024)
            except Exception as e:
                return

            cmd = cmd.strip()

            if cmd == b"\r\n" or cmd == b"\xff\xf1" or cmd == b"":
                continue

            try:
                cmd = cmd.decode()
            except Exception as e:
                self.utils.error("CommandChannel", e)
                client.sendall(("\r\n$%d:"%state).encode())
                continue

            if cmd == '[A':
                cmd = lastCmd

            lastCmd = cmd

            if cmd == "state":
                client.sendall(("%d\r\n$%d:"%(state, state)).encode())
                continue

            if state == STATE_HOST:
                state = self.procStateHost(client, cmd)
            elif state == STATE_TERMINATOR:
                state, currentTID = self.procStateTerminal(client, cmd, currentTID)
            else:
                state = self.procStateRoot(client, cmd)
                if state == STATE_EXIT:
                    self.closeSocket(client)
                    return

            try:
                client.sendall(("\r\n$%d:"%state).encode())
            except Exception as e:
                pass

    def procStateRoot(self, client, cmd):
        if cmd == "host":
            return STATE_HOST
        elif cmd == "terminator":
            return STATE_TERMINATOR
        elif cmd == "exit":
            return STATE_EXIT
        return STATE_ROOT

    def procStateHost(self, client, cmd):

        # 1, service management: add, remove, print services
        if cmd == "exit":
            return STATE_ROOT
        elif cmd.startswith("print"):
            output = self.blSharedData.getListeningPorts()
            if not output == "":
                client.sendall(output.encode())
            return STATE_HOST
        elif cmd.startswith("add"):
            cmd = cmd[4:]
            try:
                terminatorId, terminalAddr, terminalPort, businessListenerPort = cmd.split(',')
            except Exception as e:
                msg = self.utils.getExceptMsg(e)
                client.sendall(msg.encode())
                return STATE_HOST


            self.queueWithBL.put("startNewBusiness:%s"%cmd)
            return STATE_HOST
        elif cmd.startswith("remove"):
            cmd = cmd[7:]
            self.blSharedData.setListeningPort(cmd, "None")
            self.mockClient(cmd)
            return STATE_HOST
        elif cmd.startswith("cmd"):
            # 2, service hosts shell control via shell command
            cmd = cmd[4:]
            cmd = cmd.split(" ")
            try:
                output = subprocess.check_output(cmd)
                client.sendall(output)
            except Exception as e:
                client.sendall(self.getExceptMsg(e).encode())
                self.utils.error("CommandChannel", "execute cmd \"%s\" error, description:%s"%(cmd, e.strerror))
        return STATE_HOST

    def procStateTerminal(self, client, cmd, currentTID):
        if cmd == "exit":
            return STATE_ROOT, currentTID
        elif cmd.startswith("print"):
            self.endForCommandChannel.send("getTerminatorList")
            output = self.getTerminalMsg(client)
            if not output == "":
                client.sendall(output.encode())
            return STATE_TERMINATOR, currentTID
        elif cmd.startswith("select"):
            cmd = cmd[7:]
            self.endForCommandChannel.send("getTerminatorById:%s"%cmd)
            result = self.getTerminalMsg(client)
            if result == "True":
                currentTID = cmd
            else:
                currentTID = -1
            return STATE_TERMINATOR, currentTID
        elif cmd.startswith("cmd"):
            # 2, service hosts shell control via shell command
            cmd = cmd[4:]

            self.endForCommandChannel.send("getTerminatorById:%s"%currentTID)
            result = self.getTerminalMsg(client)
            if result == "False":
                client.sendall("cmd failed, no terminator %s found"%currentTID)
            else:
                self.endForCommandChannel.send("execCmd:%s:%s"%(currentTID, cmd))
                result = self.getTerminalMsg(client)
                client.sendall(result.encode())
        return STATE_TERMINATOR, currentTID

        '''
        2, terminator hosts control via shell command
        '''

    def threadTerminalMsg(self):
        while True:
            result = self.endForCommandChannel.recv()
            self.msgQueue.put(result)

    def getTerminalMsg(self, client):
        while not client._closed:
            if self.msgQueue.empty():
                time.sleep(1)
                continue
            return self.msgQueue.get()

    def mockClient(self, port):
        cmdSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            cmdSocket.connect(("127.0.0.1", int(port)))
        except Exception as e:
            self.utils.error("mock connect to %s error"%port)
