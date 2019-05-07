import socket, threading, time
from com.cleverworld.spring.transmitor.BusinessConnector import *
from com.cleverworld.spring.transmitor import Utils
from multiprocessing import Process, Lock, Queue

class BusinessListener(Process):
    """
    store paired client and terminal side socket with paired Sequence id as key
    for example: {"101" : {clientSocket, terminalSocket}}
    """
    pairedBusiness = {}
    proxyRequestMessage = {}
    isRunning = True
    clientSequence = 100
    terminatorList = {}
    sequenceLock = Lock()

    def __init__(self, blSharedData, queueWithBL, queueWithCSCL, utils):
        super(BusinessListener, self).__init__(name='BusinessListener')
        self.utils = utils
        self.backLog = int(self.utils.get("transmitor")['backLog'])
        self.blSharedData = blSharedData
        self.queueWithBL = queueWithBL
        self.queueWithCSCL = queueWithCSCL
        self.services = self.utils.get('transmitor')['services']
        self.toTerminalPort = self.utils.get('transmitor')['toTerminalPort']

    def run(self):
        # Start services opened for the internet's clients
        for service in self.services:
            self.startClientListener(service)

        # Start service opened for the terminal
        self.startTerminalListener(self.toTerminalPort)
        while self.isRunning:
            data = self.queueWithBL.get()
            cmd, service = data.split(':')
            if cmd == 'startNewBusiness':
                terminatorId, terminalAddr, terminalPort, businessListenerPort = service.split(',')
                # if the client service listener hasn't started then start it via command channel
                if self.blSharedData.getListeningPort(businessListenerPort) == "None":
                    self.services.append(service)
                    self.saveServices()
                    self.startClientListener(service)
            elif cmd == 'FromCSCL':
                terminatorId, status = service.split(',')
                self.terminatorList[terminatorId] = bool(status)

    def saveServices(self):
        self.utils.setSubItem('transmitor', 'services', self.services)
        self.utils.save()

    def closeSocket(self, sock):
        if sock == None:
            return
        try:
            sock.close()
        except socket.error:
            pass

    def setBlockingMode(self, sock, blockingMode):
        try:
            sock.setblocking(blockingMode)
            sock.settimeout(10)
        except socket.error as e:
                self.utils.printExceptMsg('setBlockingMode', "%d"%blockingMode, e)

    def threadClient(self, server, service):
        """Thread to accept connections from clients, """
        self.utils.info('threadClient', 'start. service: ' + service)
        terminatorId, terminalAddr, terminalPort, businessListenerPort = service.split(',')
        isProxyMode = False
        isConnectMode = False
        isSocks = False

        # parse proxy type
        if terminalAddr == "":
            isProxyMode = True
            if terminalPort == "socks":
                isSocks = True

        # accept connections, and ready to pair clients and terminals
        while True:
            try:
                client, address = server.accept()
            except Exception as e:
                self.utils.printExceptMsg("threadClient", "server.accept error, service: %s"%service, e)
                break

            # close the client and stop the service, when the service has marked as None status.
            if self.blSharedData.getListeningPort(businessListenerPort) == "None":
                self.services.pop(self.services.index(service))
                self.saveServices()
                self.closeSocket(server)
                self.closeSocket(client)
                break

            data = None
            if isProxyMode:
                # 1, get clients proxy information
                try:
                    data = client.recv(1024)
                except Exception as e:
                    self.closeSocket(client)
                    continue

                # 2, proc all kinds of exceptions of input parameters
                if data == '':
                    self.closeSocket(client)
                    continue

                try:
                    header = data.decode()
                except Exception as e:
                    self.closeSocket(client)
                    continue

                if header == '':
                    self.closeSocket(client)
                    continue

                # 3, proxy http and https proxy
                if isSocks:
                    terminalAddr, terminalPort = self.procProxySocks(client, data)
                else:
                    isConnectMode = True
                    if header.startswith("CONNECT"):
                        terminalAddr, terminalPort = self.procProxyConnectMode(header)
                        client.sendall("HTTP/1.1 200 Connection Established\r\n\r\n".encode())
                    else:
                        isConnectMode = False
                        terminalAddr, terminalPort, data = self.procProxyNormalMode(header)

                service = "%s,%s,%s,%s"%(terminatorId, terminalAddr, terminalPort, businessListenerPort)
                self.utils.info("threadClient", "isSocks: %d, isConnectMode: %d, service: %s"%(isSocks, isConnectMode, service))
            # close the client when the terminator refer to the service has not registerd.
            try:
                status = self.terminatorList[terminatorId]
            except Exception as e:
                status = False
            if not status:
                self.closeSocket(client)
                continue

            # set the client socket blocking mode to false and send the client coming information to CSCC, and pending to pair state
            self.setBlockingMode(client, False)
            with self.sequenceLock:
                self.clientSequence += 1
                self.pairedBusiness[self.clientSequence] = client
                if isProxyMode:
                    # if is ConnectMode or socks proxy, then pass the data
                    if isSocks:
                        pass
                    elif not isConnectMode:
                        self.proxyRequestMessage[self.clientSequence] = data
                else:
                    if data != None:
                        self.proxyRequestMessage[self.clientSequence] = data

                self.queueWithCSCL.put('FromBusiness:%d,%s' % (self.clientSequence, service))

            self.utils.info('threadClient', 'new client %d coming, isConnectMode:%d, isProxyMode:%d, service: %s, %s'%(self.clientSequence, isConnectMode, isProxyMode, service, time.ctime()))

    def procProxySocks(self, client, data):
        '''
        process socks5 connection
        :return: terminalAddr, terminalPort, data
        '''

        # recv data: b'\x05\x01\x00'
        ver = data[:1]
        cmd = data[1 : 2]
        rsv = data[2 : 3]

        self.utils.debug("procProxySocks", "data: %s, len: %d"%(data, len(data)))
        # reply to the client to accept the client authentication mode
        client.sendall(b'\x05\x00')
        try:
            data = client.recv(1024)
        except Exception as e:
            self.closeSocket(client)
            return

        atyp = data[3 : 4]
        if atyp == b'\x01':
            #atype == 1, means the dstAddr is a 4 bit IPv4 address
            # data = b'\x05\x01\x00\x01\xc0\xa8e\xb7\x00\x16
            addrLen = 4
            dstAddr = data[4 : 4 + addrLen]
            dstPort = data[4 + addrLen:]
            terminalAddr = "%d.%d.%d.%d"%(int.from_bytes(dstAddr[:1], byteorder='big'), int.from_bytes(dstAddr[1:2], byteorder='big'), int.from_bytes(dstAddr[2:3], byteorder='big'), int.from_bytes(dstAddr[3:4], byteorder='big'))
            terminalPort = "%d"%(int.from_bytes(dstPort, byteorder='big'))
        elif atyp == b'\x03':
            # atype == 3, means the first bit after it is the lengt of domain, and then the domain,
            # b'\x05\x01\x00\x03\tlocalhost\x00\x16'
            addrLen = int.from_bytes(data[4 : 5], byteorder='big')
            dstAddr = data[5 : 5 + addrLen]
            dstPort = data[5 + addrLen:]
            terminalAddr = dstAddr.decode()
            terminalPort = "%d"%(int.from_bytes(dstPort, byteorder='big'))
        elif atyp == b'\x06':
            #atype == 6, means the dstAddr is a 16 bit IPv6 address
            addrLen = 16
            dstAddr = data[4 : 4 + addrLen]
            dstPort = data[4 + addrLen:]
            terminalAddr = "%d.%d.%d.%d"%(int.from_bytes(dstAddr[:1], byteorder='big'), int.from_bytes(dstAddr[1:2], byteorder='big'), int.from_bytes(dstAddr[2:3], byteorder='big'), int.from_bytes(dstAddr[3:4], byteorder='big'))
            terminalPort = "%d"%(int.from_bytes(dstPort, byteorder='big'))
        else:
            return

        client.sendall(b'\x05\00\00\01\00\00\00\00\00\00')
        '''没有冒号，表示不带端口号'''
        return terminalAddr, terminalPort

    def procProxyConnectMode(self, header):
        '''
        Proc connect proxy mode, such as https request,

        :return: terminalAddr, terminalPort, data
        '''
        self.utils.debug("procProxyConnectMode", "header: %s" % header)
        indexEnd = header.index("\r")
        key, host, httpVer = header[0: indexEnd].strip().split(" ")

        try:
            indexStart = host.index(":")
            terminalAddr, terminalPort = host.split(":")
        except Exception as e:
            '''没有冒号，表示不带端口号'''
            terminalPort = "80"
            terminalAddr = host
        return terminalAddr, terminalPort

    def procProxyNormalMode(self, header):
        '''
        Proc nomal proxy mode, such as http request,

        :return: terminalAddr, terminalPort, data
        '''

        self.utils.debug("procProxyNormalMode", "header: %s" % header)
        try:
            indexStart = header.index("Host")
            indexEnd = header.index("\r", indexStart)
            host = header[indexStart + 6 : indexEnd].strip()
        except Exception as e:
            try:
                ''' the number 7 in follow code is the length of "http://", means indexStart is the position after it'''
                indexStart = header.index("http://") + 7
                indexEnd = header.index("/", indexStart)
                host = header[indexStart : indexEnd].strip()
            except Exception as e:
                return "", "", ""

        try:
            indexStart = host.index(":")
            terminalAddr, terminalPort = host.split(":")
        except Exception as e:
            '''没有冒号，表示不带端口号'''
            terminalPort = "80"
            terminalAddr = host

        try:
            indexStart = header.index("http://")
        except Exception as e:
            data = header
        else:
            indexEnd = header.index("/", indexStart + 8)
            host = header[indexStart : indexEnd]
            data = header.replace(host, "", 1)
        return terminalAddr, terminalPort, data.encode()

    def threadTerminal(self, server):
        '''
        Service that is opened to the terminal,
        and ready to accept all of the connections from the terminator
        '''
        self.utils.info('threadTerminal', 'start.')
        while True:
            try:
                client, address = server.accept()
                data = client.recv(1024)
                if data == '' or len(data) == 0:
                    self.utils.error("threadTerminal", "recv first pkg is nil")
                    self.closeSocket(client)
                    continue

                self.setBlockingMode(client, False)
            except Exception as e:
                self.utils.printExceptMsg("threadTerminal", "server.accept error ", e)

            try:
                data = data.decode()
                cmd, clientSequence = data.split(':')
            except:
                self.closeSocket(client)
                continue

            try:
                clientSocket = self.pairedBusiness[int(clientSequence)]
            except Exception as err:
                pass

            self.utils.info('threadTerminal', 'new terminal %s coming...'%(clientSequence))

            terminalSocket = client
            self.pairedBusiness[clientSequence] = (clientSocket, terminalSocket)

            requestMessage = None
            try:
                requestMessage = self.proxyRequestMessage[int(clientSequence)]
            except Exception as e:
                pass
            else:
                client.sendall(requestMessage)
            if requestMessage != None:
                del self.proxyRequestMessage[int(clientSequence)]

            businessConnector = BusinessConnector(clientSequence, terminalSocket, clientSocket, self.utils)
            businessConnector.start()

            self.utils.debug("BusinessListener::threadTerminal",
                             "connect create terminal and client pair success, clientSequence %s, begin create tunnel" % clientSequence)

    def startClientListener(self, service):
        """
        :start business
        """
        terminatorId, terminalAddr, terminalPort, businessListenerPort = service.split(',')
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind(('0.0.0.0', int(businessListenerPort)))
            # server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.listen(self.backLog)
        except socket.error as e:
            self.utils.error('startClientListener', e.strerror)
            return

        thread = threading.Thread(target=self.threadClient, args=(server, service), name='threadClient ' + service)
        self.blSharedData.setListeningPort(businessListenerPort, service)
        thread.start()

    def startTerminalListener(self, port):
        '''
        Start service opened for the terminal, 
        used for the terminal to registered into our transmitor
        :param port the default port is 30000
        '''
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind(('0.0.0.0', port))
            # server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.listen(self.backLog)
        except socket.error as e:
            self.utils.error('startTerminalListener', e.strerror)
            return

        thread = threading.Thread(target=self.threadTerminal, args=(server,), name='threadTerminal %d' % port)
        thread.start()
