import asyncio
from collections import defaultdict
from functools import partial
import time
import arrow
import logging
import os
import zmq
import zmq.asyncio
import subprocess

import sys
logger = logging.getLogger("timelock")
#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)

class Timer(object):
    ''' Timer class

    Parameters
    ----------
    timeout : float
         time out in seconds
    queue : queue
         message queue
    '''
    def __init__(self, timeout, queue, user):
        self._timeout = timeout
        self._queue = queue
        self._user = user
        self._task = asyncio.create_task(self.interrupt())
        
    async def interrupt(self):
        while True:
            logger.debug('interrupt called.')
            await asyncio.sleep(self._timeout)
            self._queue.put_nowait(dict(request=BookKeeper.KEEPALIVE, user=self._user))
        
    def cancel(self):
        self._task.cancel()

class SystemLock(object):

    def _call(self, cmd):
        r = subprocess.run(cmd.split())
        return r.returncode
        
    def lock(self, user='leonie'):
        cmd = f"chage -E 0 {user}"
        logger.info(f"Locking system for user {user}")
        return self._call(cmd)

    def unlock(self, user='leonie'):
        cmd = f"chage -E -1 {user}"
        logger.info(f"Unlocking system for user {user}")
        return self._call(cmd)

    
class SocketListener(object):

    def __init__(self, port, queues):
        self.ctx = zmq.asyncio.Context()
        self.socket = self.ctx.socket(zmq.REP)
        self.socket.bind(f"tcp://*:{port}")
        self._queues = queues
        self._task = asyncio.create_task(self.recv_and_process())
        
    async def recv_and_process(self):
        logger.debug("recv_and_process started...")
        while True:
            message = await self.socket.recv_json() # waits for msg to be ready
            logger.debug(f"Message received: {message}")        
            user = message['user']
            if 'ping' in message.keys():
                return_message = await self.make_request(request="usage", user=user)
            elif 'command' in message.keys() and message['command'] == 'reset_usage':
                return_message = await self.make_request(request="reset_usage", user=user)
            else:
                logger.error(message)
                logger.error("message received:")
                logger.error("Stopped listenening...")
                break
            await self.socket.send_json(return_message)

    async def make_request(self, request, user, payload=None):
        if request == 'usage' or request == 'reset_usage':
            self._queues['lb'].put_nowait(dict(request=request, user=user))
            message = await self._queues['bl'].get()
        # elif request == 'user_enabled':
        #     try:
        #         value = payload['value']
        #     except Exception as e:
        #         logger.info("Received an invalid value for command 'user_enabled'")
        #     else:
        #         if value == "lock" or value == "unlock":
        #             self._queues['lb'].put_nowait(request=payload)
                    
        #         else:
        #             logger.info(f"Unprocessed value for command 'user_enabled' ({value}).")
        else:
            logger.error(f"Unknown request by {user}")
            message = dict(request="unknown")
        return message
    
    def cancel(self):
        self._task.cancel()
        self.socket.close()
        self.ctx.destroy()

        
class BookKeeper:
    REQ_USAGE = 'usage'
    REQ_RESET = 'reset_usage'
    KEEPALIVE = True


    WEEKDAYS = "mon tue wed thu fri sat sun".split()
    NOLOGINMESSAGE = ["",
                      "User-lock due exceeded quotum.",
                      "User-lock due to time window restrictions."]
    
    QUOTUM_EXCEEDED = 1
    OUTSIDE_ACCESS_WINDOW = 2
    USER_ENABLED = 4
    
    def __init__(self, queues, config):
        self.system_lock = SystemLock()
        self._queues = queues
        self.config = config
        self.usage = 0
        self.locked = 0
        self._locked_status = None
        self.current_quotum = 0
        self.user_enabled = True # access control by program. False: no access at all.
        self.compute_time_windows()
        self._tasks = [asyncio.create_task(self.process())]
        
    def compute_current_quotum(self):
        now = arrow.now()
        k = BookKeeper.WEEKDAYS[now.weekday()]
        self.current_quotum = self.config["quotum"][k]
        
    def compute_time_windows(self):
        _unlock = dict()
        for d, w in self.config["unlock"].items():
            k = BookKeeper.WEEKDAYS.index(d)
            s0, s1 = [s.strip() for s in w.split("-")]
            t = [int(i) for i in s0.split(":")]
            v = [t[0]+t[1]/60]
            t = [int(i) for i in s1.split(":")]
            v += [t[0]+t[1]/60]
            _unlock[k] = v
        self.config['_unlock'] = _unlock

    async def process(self):
        previous_time = 0
        while True:
            message = await self._queues['lb'].get()
            request = message['request']
            user = message['user']
            logger.debug("message:", message)
            self.compute_current_quotum()
            try:
                if request == BookKeeper.REQ_USAGE:
                    current_time = time.time()
                    if previous_time == 0:
                        interval = 0
                    else:
                        interval = current_time - previous_time
                    if interval > 60:
                        interval = 0
                    previous_time = current_time
                    self.update_time(interval)
                    reply = self.get_reply_dict()
                    self._queues['bl'].put_nowait(reply)
                elif request == BookKeeper.REQ_RESET:
                    self.update_time(0, reset_usage=True)
                    logger.debug(f"self.usage: {self.usage}")
                    reply = self.get_reply_dict()
                    self._queues['bl'].put_nowait(reply)
                elif request == BookKeeper.KEEPALIVE:
                    self.update_time(0)
                self.check_lock(user)
            except Exception as e:
                logger.error(f"{e.__class__} {e.args}")
                    

    def get_reply_dict(self):
        reply = dict(response="usage",
                     usage = self.usage,
                     quotum = self.current_quotum,
                     locked = self.locked)
        return reply
    
    def get_info_from_file(self):
        now = time.time()
        fn = self.config['filename']
        try:
            with open(fn, 'r') as fp:
                text = fp.readline()
        except FileNotFoundError:
            timestamp_previous = 0
            usage = 0
        else:
            timestamp_previous, usage = [float(s) for s in text.split()]
        return now, timestamp_previous, usage
        
    def update_time(self, interval, reset_usage=False):
        now, timestamp_previous, self.usage = self.get_info_from_file()
        fn = self.config['filename']
        if reset_usage:
            self.usage = 0
        if self.is_new_day(timestamp_previous, now):
            self.usage=0
            # set default policy for this day
            day_of_week = arrow.get(now).weekday()
            self.locked = self.config['initially_locked'][day_of_week]
        if not self.locked:
            self.usage += interval
        with open(fn, 'w') as fp:
            fp.write("%f %f"%(now, self.usage))
        self.locked = 0
        self.locked |= int(self.usage > self.current_quotum) * BookKeeper.QUOTUM_EXCEEDED
        self.locked |= int(self.is_outside_window(now)) * BookKeeper.OUTSIDE_ACCESS_WINDOW
        self.locked |= int(not self.user_enabled) * BookKeeper.USER_ENABLED
        logger.debug(f"System locked: {self.locked}")

    def is_outside_window(self, now):
        t = arrow.get(now)
        try:
            t_limits = self.config["_unlock"][t.weekday()]
        except KeyError:
            t_limits = [0,24]
        hour = t.time().hour
        hour += t.time().minute/60
        return hour < t_limits[0] or hour > t_limits[1] 
    
    def is_new_day(self, timestamp_previous, now):
        t0 = arrow.get(timestamp_previous)
        t1 = arrow.get(now)
        t_delta = t1-t0
        is_new_day = t_delta.seconds > 86400 or t0.weekday() != t1.weekday()
        if is_new_day:
            logger.debug("NEW DAY")
            logger.debug(f"t_delta : {t_delta.seconds}, {t0.weekday()}, {t1.weekday()}")
        return is_new_day
    
    def check_lock(self, user):
        if self.locked != self._locked_status:
            # lock status has changed
            # lock or unlock system
            logger.info(f"Changing lock status. New status : {self.locked}")
            if self.locked:
                r = self.system_lock.lock(user)
            else:
                r = self.system_lock.unlock(user)
            if r != 0:
                logger.error(f"SystemLock return an error ({r})")
    
        self._locked_status = self.locked
                    
    def cancel(self):
        for t in self._tasks:
            t.cancel()

class Config(object):
    def __init__(self, filename):
        self.config = dict(quotum=defaultdict(lambda : 86400),
                           unlock=dict(),
                           initially_locked = defaultdict(lambda: True))
        self.parse(filename)
        self.report(filename)

    def report(self, filename):
        logger.info(f"Reading configuration from {filename}.")
        m = self.config.__repr__()
        logger.debug(m)
        
    def parse(self, filename):
        cmds = dict(quotum=self.read_quotum,
                    unlock=self.read_unlock,
                    locked=partial(self.read_locked_unlocked, True),
                    unlocked=partial(self.read_locked_unlocked, False))
        
        with open(filename, 'r') as fp:
            lines = fp.readlines()
            for line in lines:
                line = line.strip()
                if line.startswith("#") or line=='':
                    continue
                cmd, *args = line.split()
                cmds[cmd.strip()](*args)
                if not line:
                    break
                
    def read_quotum(self, day, quotum):
        if day == 'default':
            self.config["quotum"].default_factory = lambda : int(quotum)
        else:
            self.config["quotum"][day] = int(quotum)

    def read_unlock(self, *args):
        day, period = args
        self.config["unlock"][day] = period
            
    def read_locked_unlocked(self, initially_locked, day):
        self.config["initially_locked"][day] = initially_locked
        
async def coro_main():
    if 0:
        filename = "/var/timelock/timelock.txt"
        config_filename = '/etc/timelockrc'
        if not os.path.exists('/var/timelock'):
            os.mkdir('/var/timelock')
    else:
        filename = "timelock.txt"
        path_nologin = "nologin"
        config_filename = 'timelockrc'

    c = Config(config_filename)
    c.config['filename']=filename
    # queues for sending information from socket_Listener to BookKeeper (lb)
    #                                from BookKeeper to socket_Listener (bl)
    queues = dict(lb = asyncio.queues.Queue(),
                  bl = asyncio.queues.Queue())

    socket_listener = SocketListener(5555, queues)
    
    bookkeeper = BookKeeper(queues, c.config)
    
    # Run this for each user that needs to be monitored. This ensures
    # unlocking when allowed, and user is not logged in (because she
    # is locked out :-)
    timer = Timer(60, queue=queues['lb'], user='leonie')

    while True:
        await asyncio.sleep(60)  # wait to see timer works
        logger.debug("Still running...")
    socket_listener.cancel()  # cancel it
    bookkeeper.cancel()



    
def main():
    asyncio.run(coro_main(), debug=False)
