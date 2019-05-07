import socket, threading
import subprocess
from com.cleverworld.spring.transmitor import Utils
from multiprocessing import Process, Queue
import time

class ConnectSyncChannel(Process):
    isRunning = True
    terminatorList = {}

    def __init__(self, endForConnectSyncChannel, queueWithBL, queueWithCSCL, utils):
        super(ConnectSyncChannel, self).__init__(name='ConnectSyncChannel')
        self.utils = utils
        self.backLog = int(self.utils.get("transmitor")['backLog'])
        self.endForConnectSyncChannel = endForConnectSyncChannel
        self.queueWithBL = queueWithBL
        self.queueWithCSCL = queueWithCSCL
        self.port = self.utils.get('connector')['port']

    def getTerminatorById(self, terminatorId):
        try:
            client = self.terminatorList.get(terminatorId)
        except Exception as e:
            client = None
        return client

    def run(self):
        threadConnector = threading.Thread(target=self.threadConnector, args=(self.port,), name='ConnectSyncChannel %s' % self.port)
        threadConnector.start()

        threadForCommandChannel = threading.Thread(target=self.threadForCommandChannel, args=(), name='threadForCommandChannel')
        threadForCommandChannel.start()

        while self.isRunning:
            data = self.queueWithCSCL.get()
            cmd, param = data.split(':')
            if cmd == 'FromBusiness':
                clientSequence, terminatorId, terminalAddr, terminalPort, businessListenerPort = param.split(',')
                client = self.getTerminatorById(terminatorId)
                if client != None:
                    try:
                        client.sendall(('FromCSCL:%s,%s,%s,%s;' % (clientSequence, terminalAddr, terminalPort, businessListenerPort)).encode())
                    except Exception as e:
                        pass
                else:
                    self.queueWithBL.put('FromCSCL:%s,False' % terminatorId)

    def registerTerminator(self, terminatorId, client):
        self.terminatorList[terminatorId] = client
        self.queueWithBL.put('FromCSCL:%s,True' % terminatorId)

    def unregisterTerminator(self, terminatorId, client):
        self.terminatorList[terminatorId] = None
        self.queueWithBL.put('FromCSCL:%s,False' % terminatorId)
        try:
            client.close()
        except socket.error:
            pass

    def threadTerminator(self, client, port):
        """first msg flag, we use it to decide the client properties"""
        firstMsg = True
        terminatorId = -1
        while True:
            try:
                data = client.recv(1024)
                data = data.decode()
                index = data.index(":")
                cmd = data[:index]
                data = data[index + 1:]
                if firstMsg:
                    if cmd == 'Terminator':
                        self.registerTerminator(data, client)
                        self.utils.info('ConnectSyncChannel', 'new terminator coming, terminalId:%s, %s' % (data, time.ctime()))
                    firstMsg = False
                else:
                    self.endForConnectSyncChannel.send(data)

            except Exception as e:
                self.unregisterTerminator(terminatorId, client)
                self.utils.printExceptMsg('ConnectSyncChannel', "terminatorId:%s "%terminatorId, e)
                break

    def threadForCommandChannel(self):
        '''
        thread for receive CommandChannel pipe message
        :return:
        '''
        while True:
            cmd = self.endForConnectSyncChannel.recv()
            if cmd == "getTerminatorList":
                output = ""
                for key in self.terminatorList:
                    output += key + "\r\n"
                self.endForConnectSyncChannel.send(output)
            elif cmd.startswith("getTerminatorById"):
                cmd, id = cmd.split(":")
                terminal = self.getTerminatorById(id)
                if terminal == None:
                    self.endForConnectSyncChannel.send("False")
                else:
                    self.endForConnectSyncChannel.send("True")
            elif cmd.startswith("execCmd"):
                cmd, terminalId, shellCommand = cmd.split(":")

                terminal = self.getTerminatorById(terminalId)
                if terminal == None:
                    self.endForConnectSyncChannel.send("cmd failed, no terminal %d found in ConnectSyncChannel"%terminalId)
                else:
                    terminal.sendall(("FromCC:%s;" % shellCommand).encode())

    def threadConnector(self, port):
        """
        :start business
        """
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(('0.0.0.0', int(port)))
            # server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.listen(self.backLog)
        except socket.error as e:
            self.utils.error('threadConnector', e.strerror)

        while self.isRunning:
            client, address = server.accept()
            threadTerminator = threading.Thread(target=self.threadTerminator, args=(client, port), name='ConnectSyncChannel terminal %d' % port)
            threadTerminator.start()