# encoding: utf-8

from multiprocessing import Queue
import threading
import time

exitFlag = 0


class myThread(threading.Thread):
    def __init__(self, threadID, name, q):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.inputs= [name]
        self.q = q

    def run(self):
        print("Starting " + self.name)
        while True:
            self.process_data(self.inputs[0], self.q)
            time.sleep(1)
        print("Exiting " + self.name)


    def process_data(self, threadName, q):
            print("%s processing" % (threadName))
        #     queueLock.acquire()
        #     if not workQueue.empty():
        #         data = q.get()
        #         queueLock.release()
        #         print("%s processing %s" % (threadName, data))
            # else:
            #     queueLock.release()


threadList = ["Thread-1", "Thread-2", "Thread-3", "Thread-4", "Thread-5", "Thread-6"]
nameList = ["One", "Two", "Three", "Four", "Five"]
queueLock = threading.Lock()
workQueue = Queue(10)
threads = []
threadID = 1

# 创建新线程
for tName in threadList:
    thread = myThread(threadID, tName, workQueue)
    thread.start()
    threads.append(thread)
    threadID += 1
    time.sleep(1)

# 填充队列
queueLock.acquire()
for word in nameList:
    workQueue.put(word)
queueLock.release()

# 等待队列清空
while not workQueue.empty():
    pass

# 通知线程是时候退出
exitFlag = 1

# 等待所有线程完成
for t in threads:
    t.join()
print
"Exiting Main Thread"