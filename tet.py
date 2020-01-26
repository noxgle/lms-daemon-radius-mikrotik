import threading
import time
import sys


class deamonMT(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.setDaemon(True)

    def run(self):
        while True:
            time.sleep(10)
            sys.exit()




MT=deamonMT()
MT.start()
while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        break
    print MT.is_alive()
    if MT.is_alive() is False:
        MT = deamonMT()
        MT.start()

