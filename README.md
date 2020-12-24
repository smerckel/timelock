# Timelock

## Synopsis
Timelock is a small application intended for linux (but may be portable to other platforms) to limit the time a specific user can use the device. The intended audience is parents who want to control the amount of time a child spends using a computer.

The application is based on a server-client model. The server, run as root, does the accounting by keeping track how many seconds of use have been consumed, and when this exceeds a pre-defined quotum, it locks the child's user account. A client, that is started when the child logs on into a graphical session, "pings" the server at 30 second intervals, upon which the server updates the accounting.

## Background

My daughter, currently 10 years old, finds it difficult to honour parental requests to shutdown the computer when she is playing games or browsing the internet. Whereas enforcing this often upsets her, so that the situation ends up in a battle between her and her parents, she seems to be content with the computer becoming unusable after a while, if she knows in advance how much time she has left. Using a cooking alarm clock, and using ssh to shut down a computer remotely, is a method that works, but is difficult to sustain its practice for a longer period of time. I was unsuccessful in finding a solution to this problem on the internet that worked for me, so I decided to have a go at it to program one on my own. I publish it as open source in the hope that it may serve other parents in the same situation.

Note that I acknowledge that the solution I came up with can be circumvented by the child, if (s)he is techsavvy enough. In my situation I don't expect a security breach any time soon, however. In fact, I would applaud it if my daughter found out (on her own) how to break the system. I think.

## Implementation

The application is written in Python3 (3.7+), and comes with an independent gnome-shell extension to display in the top panel the amount of time left. If an other windowm manager than Gnome is used, then this part does is not functional, but the application itself is. (Probably, as some minor modifications are required, see below).

### Server-side
The server application is run from a systemd service at boot time. Its key tasks are:
- reading the configuration file with information on daily quota and time windows during which the device can be used
- listening for incoming pings, or requests by a client, returning appropriate information
- keeping track of how much time has been consumed and lock/unlock the login account of the child.

Requests from a client can be in the form of a ping (so the server knowns that the computer is being used), or request to reset the consumed time. Other requests that are currently not implemented could be to extend todays quotum, or to lock/unlock an account unconditionally. When a client makes a request, the server returns information on current consumed time.

If the bookkeeping part of the server determines that an account must be locked or unlocked, it issues a shell command to make that happen. Effectively this boils down to running the commands chage -E 0 <username> or chage -E -1 <username> to lock or unlock the account, respectively.

### Client-side
The client is run as a systemd service in user-space, which allows it to be started and killed just after a graphical session is started or closed, respectively. When run, the client enters an infinite loop, where it pings the server and sleeps for 30 seconds. If it receives word of the server that time's up, then the client invokes the screen saver. In this way, programs are not killed in an appropriate manner. The lock command issued by the server, does not prevent the to lock back in again, because the graphical session is still running. But, in 30 seconds, the screen will be locked again. Effectively, this makes the computer unattractive to continue using it, but it allows the child to save work, or close programs, or put the computer to sleep.

### Gnome-extension
A simple gnome extension is added, which shows the amount of time left (in minutes) in the top panel. (If a game is being played in full-screen mode, then, well that is too bad.) The gnome-extension effectively reads the output of a small client script that returns the time left, and prints that in the top panel.

## Installation

1. First clone this repository.

2. For now, the user account info is hard-coded in the source, and needs manual modification in timelock/timelock.py and timelock/timelock_user.py.

3. Install the python part by issueing in the root of the repository: 

`$ python3 setup.py build && sudo python3 setup.py install`

Installing as root is not strictly necessary. It is however required that the server is run as root, because of the system command `chage`.

4. Write a configuration file (default location is /root, but can be set in timelock/timelock.py).

5. Test the server application by running `timelock`

6. Log in using the account of the child, and test the client timelock_user. This should be done in a Gnome-session. Also test the command `timeleft` which should echo the number of minutes left. Close the programs again by issueing control-C.

7. When this all works, copy the systemd service files, located in the directory `data` to their respective locations:
`timelock.service -> /etc/systemd/system`
and
`timelock-user.service -> /etc/systemd/user`

8. Start the services:
as root `# systemctl enable timelock && systemctl start timelock`
and using the child's account in a Gnome-session `$ systemctl enable timelock-user` and log out. Next time the child logs in, timelock-user is activated automatically.

9 Activate the extension. Log in using the child's account. Copy the directory add-script-output@example.com in the directory `shell_extension` to `$HOME/.local/share/gnome-shell/extensions/`. Then use gnome-tweaks to enable the extension.

## Configuration file

An example configuration file looks like

```#Enter commands as one in quotum or unlock, and arguments
#lines starting with a # are comments

# set default quotum
quotum default 300
# set a different one for Friday's
quotum fri 10800
# and Saturdays
quotum sat 60
# Specify a time window for Monday and Tuesday:
unlock mon 15:00-18:30
unlock tue 15:00-21:30
# The days below are commented out, and access is granted any time of the day
#unlock wed 15:00-18:30
#unlock thu 14:00-18:30
#unlock fri 14:00-18:30
#unlock sat 8:00-18:30
#unlock sun 8:00-18:30

# These commands are not yet implemented
#locked mon
#locked tue
#unlocked wed
#locked thu
#locked fri
#unlocked sat 
#unlocked sun```







