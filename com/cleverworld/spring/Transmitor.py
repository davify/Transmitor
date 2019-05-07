from multiprocessing import *
from multiprocessing.managers import BaseManager

from com.cleverworld.spring.transmitor.BusinessListener import *
from com.cleverworld.spring.transmitor.ConnectSyncChannel import *
from com.cleverworld.spring.transmitor.CommandChannel import *
from com.cleverworld.spring.transmitor.Utils import *

class TransmitorProcessManager(BaseManager):
    pass

class ConnectSyncChannelSharedData():
    pass

class BusinessListenerSharedData():
    listeningPort = {}

    def getListeningPort(self, port):
        if port in self.listeningPort.keys():
            data = self.listeningPort[port]
        else:
            data = "None"

        return data

    def getListeningPorts(self):
        output = ""
        for key,value in self.listeningPort.items():
            output += "%s: %s\r\n"%(key, value)
        return output
    def setListeningPort(self, port, value):
        self.listeningPort[port] = value
    def hasListeningPort(self, port):
        return port in self.listeningPort.keys()

def testA(x):
    print("testA1: %s"%x)
    def testB(y):
        print("testB: %s"%y)
        return x + y
    print("testA2: %s"%x)
    return testB



def main():
    print(testA(3)(5))
    # queue for BusinessListener
    queueWithBL = Queue()
    # queue for CSCL
    queueWithCSCL = Queue()

    utils = Utils()



    # register BusinessListenerSharedData in TransmitorProcessManager
    TransmitorProcessManager.register("BusinessListenerSharedData", BusinessListenerSharedData)

    manager = TransmitorProcessManager()
    manager.start()
    # create BusinessListenerSharedData
    blSharedData = manager.BusinessListenerSharedData()


    endForConnectSyncChannel, endForCommandChannel = Pipe()

    utils.info('main', 'starting BusinessListener...')
    businessListener = BusinessListener(blSharedData, queueWithBL, queueWithCSCL, utils)
    businessListener.daemon = True
    businessListener.start()

    utils.info('main', 'starting ConnectSyncChannel...')
    connectSyncChannel = ConnectSyncChannel(endForConnectSyncChannel, queueWithBL, queueWithCSCL, utils)
    connectSyncChannel.daemon = True
    connectSyncChannel.start()

    utils.info('main', 'starting CommandChannel...')
    commandChannel = CommandChannel(blSharedData, endForCommandChannel, queueWithBL, utils)
    commandChannel.daemon = True
    commandChannel.start()

    businessListener.join()
    connectSyncChannel.join()
    commandChannel.join()
    utils.info('main', 'exit.')

if __name__ == '__main__':
    main()