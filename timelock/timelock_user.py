import zmq
import time
import signal
import sys
import dbus
from hashlib import md5
import getpass

import logging
logger = logging.getLogger("timelock_user")
#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.ERROR)



DEBUG = False
PORT = 5555


class ScreenSaver(object):
    def __init__(self):
        self.init()

    def init(self):
        t0 = time.time()
        while True:
            try:
                self.start_interface()
            except dbus.exceptions.DBusException:
                time.sleep(0.5)
            else:
                break
            if time.time()-t0 > 30:
                # We didn't manage to connect. Giving up.
                logging.error("Could not connect to ScreenSaver. Giving up permanently.")
                sys.exit(-1)
                
        
    def start_interface(self):
        self.interface=dbus.Interface(dbus.SessionBus().get_object("org.gnome.ScreenSaver",
                                                                   "/org/gnome/ScreenSaver"),
                                      dbus_interface = "org.gnome.ScreenSaver")
    def unlock(self):
        self.interface.SetActive(False)
        
    def lock(self):
        self.interface.Lock()

    def toggle(self):
        status=self.interface.GetActive()
        if status:
            self.unlock()
        else:
            self.lock()

    @property
    def is_locked(self):
        return self.interface.GetActive()


class Client(object):
    
    def __init__(self, port, user, sleep_time=60, host='localhost'):
        signal.signal(signal.SIGTERM, self.signal_handler)
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.REQ)
        self.socket.connect(f"tcp://{host}:{port}")
        self.screensaver=ScreenSaver()
        self.mtype_ping = dict(ping='ping', user=user)
        self.mtype_reset = dict(command='reset_usage', user=user)
        self.sleep_time = sleep_time
        
    def signal_handler(self, signum, frame):
        logging.info("Shutting down timelock_user")
        sys.exit(0)

    def send_and_receive(self, mtype='ping'):
        if mtype == 'ping':
            self.socket.send_json(self.mtype_ping)
        elif mtype == 'reset':
            self.socket.send_json(self.mtype_reset)
        else:
            raise ValueError(f"mtype {mtype} not inmplemented")
        logger.debug(f"Message type sent: {mtype}")
        message = self.socket.recv_json()
        logger.debug(message)
        return message
    
    def run(self):
        while True:
            logger.debug(f"ScreenSaver is locked: {self.screensaver.is_locked}")
            # if screen is locked, we should not be sending anymore packets...
            if not self.screensaver.is_locked:
                message = self.send_and_receive()
                if message['locked']:
                    if not self.screensaver.is_locked:
                        if DEBUG:
                            logger.debug("locking screen")
                        else:
                            self.screensaver.lock()
            time.sleep(self.sleep_time)


#     #dbus-send --type=method_call --dest=org.gnome.ScreenSaver /org/gnome/ScreenSaver org.gnome.ScreenSaver.Lock


class Password(object):
    PASSWORD = b'\\bAe\x1a\xc9[\xd1\x1bR\x9as\xfe\xf7\xc0{'

    def get_password(self):
        ans = getpass.getpass("Password : ")
        h = md5(ans.encode("utf-8"))
        return h.digest() == Password.PASSWORD
    
def main():
    logger.setLevel(logging.WARNING)
    client = Client(PORT, 'leonie', sleep_time=60)
    client.run()

def timeleft():
    logger.setLevel(logging.WARNING)
    client = Client(PORT, 'leonie')
    m = client.send_and_receive()
    quotum = m['quotum']
    usage = m['usage']
    remaining = max(0, quotum - usage)
    print(f"Time left : {int(remaining/60):0d} minutes")
    return 0

def timelock_reset():
    logger.setLevel(logging.WARNING)
    if len(sys.argv)==2:
        host = sys.argv[1]
    else:
        host = 'localhost'
    pwd = Password()
    client = Client(PORT, 'leonie', host=host)
    if pwd.get_password():
        m = client.send_and_receive(mtype='reset')
    else:
        print("Access denied.")
    
