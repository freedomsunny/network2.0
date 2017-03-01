# encoding=UTF-8
import logging
import os
import threading
import traceback
import datetime
from time import sleep
from config import *


class LogExceptionHelp(object):
    errorInfos = []
    errorLock = threading.RLock()
    inited = False
    fileName = ''
    logDir = log_path
    logger = None

    @classmethod
    def init(cls, module_name=None):
        if not cls.inited:
            cls.logDir = log_path
            if not os.path.isdir(cls.logDir):
                os.mkdir(cls.logDir)
            if not module_name:
                cls.fileName = str(datetime.date.today()) + '_error'
            else:
                cls.fileName = str(datetime.date.today()) + '_%s' % module_name
            cls.logConfig()
            task = threading.Thread(target=cls.__writeLog__)
            task.setDaemon(True)
            task.start()
            cls.inited = True

    @classmethod
    def logConfig(cls):
        filePath = "%s/%s.log" % (cls.logDir, cls.fileName)
        logging.basicConfig(level=logging.ERROR,
                            format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                            datefmt='%a, %d %b %Y %H:%M:%S',
                            filename=filePath,
                            filemode='a')
        cls.logger = logging.getLogger('root.err')

    @classmethod
    def logMsg(cls, msg):
        if not cls.inited:
            cls.init()
        cls.__addLog__(msg)

    @classmethod
    def logException(cls, msg):
        if not cls.inited:
            cls.init()
        # exstr = traceback.format_exc()
        # total = "%s\n%s" % (msg,exstr)
        total = "%s" % (msg)
        cls.__addLog__(total)

    @classmethod
    def __addLog__(cls, msgStr):
        cls.errorLock.acquire()
        cls.errorInfos.append(msgStr)
        cls.errorLock.release()

    @classmethod
    def __writeLog__(cls):
        checkCount = 50
        while True:
            if len(cls.errorInfos) <= 0:
                if checkCount <= 0:
                    if cls.fileName != str(datetime.date.today()) + '_error':
                        cls.fileName = str(datetime.date.today()) + '_error'
                        cls.logConfig()
                else:
                    checkCount -= 1
                sleep(5)
            else:
                cls.errorLock.acquire()
                msg = cls.errorInfos.pop(0)
                cls.errorLock.release()
                cls.logger.error(msg)
                print("write log ")


if __name__ == "__main__":
    LogExceptionHelp.logException('huangyingjuntest22222')
