import select
from queue import Queue
from com.cleverworld.spring.transmitor import Utils
from threading import *

class BusinessConnector(Thread):
    """
    store paired client and terminal side socket with paired Sequence id as key
    for example: {"101" : {clientSocket, terminalSocket}}
    """

    def __init__(self, clientSequence, terminalSocket, clientSocket, utils):
        super(BusinessConnector, self).__init__(name='BusinessConnector: %s' % clientSequence)
        self.utils = utils
        self.utils.info('CommandExecutor', 'init')
        self.clientSequence = clientSequence

        self.inputs = []
        self.outputs = []
        self.messageQueues = {}

        if terminalSocket != None:
            self.inputs.append(terminalSocket)
        if clientSocket != None:
            self.inputs.append(clientSocket)

        self.terminalSocket = terminalSocket
        self.clientSocket = clientSocket

        self.messageQueues[terminalSocket.fileno()] = Queue()
        self.messageQueues[clientSocket.fileno()] = Queue()

    def run(self):
        while self.inputs:
            try:
                if self.terminalSocket.fileno() == -1 or self.clientSocket.fileno() == -1:
                    break

                readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs)
            except Exception as e:
                for i in self.inputs:
                    if(i.fileno() == -1):
                        self.inputs.remove(i)

                        if i == self.terminalSocket:
                            self.utils.error("BusinessConnector::run", "terminalSocket fd is -1")
                        else:
                            self.utils.error("BusinessConnector::run", "clientSocket fd is -1")

                self.utils.printExceptMsg("BusinessConnector::run", "select event error, clientSequence:%s"%(self.clientSequence), e)
                # self.closeSock("select event error")
            else:
                for sock in readable:
                    try:
                        data = sock.recv(1024)
                        if len(data) == 0:
                            self.closeSock("recv data length is zero")
                            return
                    except Exception as err:
                        self.closeSock(self.utils.getExceptMsg(err))
                        return

                    if sock.fileno() == self.terminalSocket.fileno():
                        destSock = self.clientSocket
                    else:
                        destSock = self.terminalSocket
                    self.messageQueues[destSock.fileno()].put(data)
                    if destSock not in self.outputs:
                        self.outputs.append(destSock)

                for sock in writable:
                    messageQueue = self.messageQueues.get(sock.fileno())
                    if messageQueue is not None:
                        if not messageQueue.empty():
                            data = messageQueue.get_nowait()
                            sock.sendall(data)
                            if messageQueue.empty():
                                self.outputs.remove(sock)

    def closeSock(self, extraMsg):
        """
        :param sock: socket to close
        :param queue: message queue of the socket
        :param inputs: inputs set
        :param outputs: outputs set
        :return: null
        """
        try:
            self.terminalSocket.close()
        except Exception as e:
            pass

        try:
            self.clientSocket.close()
        except Exception as e:
            pass

        self.utils.debug("BusinessConnector", "Channel %s has Closed, %s"%(self.clientSequence, extraMsg))