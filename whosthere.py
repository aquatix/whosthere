import sys
import os
import __main__ as main
from datetime import datetime, timedelta
import pytz
from pytz.tzinfo import StaticTzInfo
from time import mktime
import click


def is_dst(zonename):
    tz = pytz.timezone(zonename)
    now = pytz.utc.localize(datetime.utcnow())
    return now.astimezone(tz).dst() != timedelta(0)


class OffsetTime(StaticTzInfo):
    """
    A dumb timezone based on offset such as +0530, -0600, etc.
    """
    def __init__(self, offset):
        hours = int(offset[:3])
        minutes = int(offset[0] + offset[3:])
        self._utcoffset = timedelta(hours=hours, minutes=minutes)


def load_datetime(value, dt_format):
    """
    Create timezone-aware datetime object
    """
    if dt_format.endswith('%z'):
        dt_format = dt_format[:-2]
        offset = value[-5:]
        value = value[:-5]
        if offset != offset.replace(':', ''):
            # strip : from HHMM if needed (isoformat() adds it between HH and MM)
            offset = '+' + offset.replace(':', '')
            value = value[:-1]
        return OffsetTime(offset).localize(datetime.strptime(value, dt_format))

    return datetime.strptime(value, dt_format)


def parselog(state, session, log):
    """
    Parse contents of the `log` list, considering the info already in `state`.
    Return new version of `state`.

    Format of `state`:
    {'<MAC ADDRESS 1>': [{'session_start': '<datetime>', 'session_end': '<datetime>', 'ip': '<ip address>'}, {'session_start'...}], '<MAC ADDRESS 2>': [...]}

    Format of `session`:
    {'timestamp': <latest timestamp>, 'previous_timestamp': <previous timestamp>, 'previous': ['<MAC ADDRESS 2>', '<MAC ADDRESS 4>'], 'current': ['<MAC ADDRESS 2>', '<MAC ADDRESS 3>']}
    """
    timezonestring = '+0100'
    if is_dst('Europe/Amsterdam'):
        timezonestring = '+0200'

    current_line = 0
    for line in log:
        current_line += 1
        #print line
        parts = line.split(' = ')
        mac_address = parts[1].strip()
        if not mac_address in state:
            state[mac_address] = []
        dt_info = parts[0].split(' ')
        #timestamp = load_datetime(timestamp + timezonestring, "%d-%m-%Y %H:%M:%S%z")
        timestamp = load_datetime(dt_info[0] + ' ' + dt_info[1] + timezonestring, "%Y-%m-%d %H:%M:%S%z")
        if timestamp != session['timestamp']:
            # New series of log entries, we might need to close some sessions:
            for mac_address in session['previous']:
                state[mac_address][-1]['session_end'] = session['previous_timestamp']

            # Update session to current series
            session['previous'] = list(session['current'])
            session['current'] = []
            session['previous_timestamp'] = session['timestamp']
            session['timestamp'] = timestamp

        try:
            latest_entry = state[mac_address][-1]
        except IndexError:
            # Start new session, apparently this MAC address is new to the list
            latest_entry = {'session_start': timestamp, 'session_end': None, 'ip': dt_info[2]}
            state[mac_address].append(latest_entry)

        if latest_entry['session_end']:
            # Previous entry was end of a session, create new session
            latest_entry = {'session_start': timestamp, 'session_end': None, 'ip': dt_info[2]}
            state[mac_address].append(latest_entry)

        state[mac_address][-1] = latest_entry

    state['current_line'] = current_line
    return state, session


## Main program
@click.group()
def cli():
    """
    whosthere
    """
    pass


@cli.command()
@click.option('--logdir', prompt='Path to the logfiles directory', help='')
@click.option('--prefix', prompt='Logfile prefix', help='Prefix of the log files, before the date')
@click.option('--macfile', prompt='Path to file with MAC address mappings')
def parselogs(logdir, prefix, macfile):
    """
    Parse the whosthere logs
    """
    state = {'current_file': '', 'current_line': 0}
    session = {'timestamp': None, 'previous_timestamp': None, 'previous': [], 'current': []}
    # Get all filenames in the logdir
    logfiles = os.listdir(logdir)
    # Make sure the files are ordered by the dates in their names
    logfiles.sort()
    for filename in logfiles:
        if filename[-4:] == '.log' and filename[0:len(prefix)] == prefix:
            with open(os.path.join(logdir, filename)) as f:
                content = f.readlines()
                content = [x.strip('\n') for x in content]
                state['current_file'] = filename
                #state, session = parselog(state, session, content)
                parselog(state, session, content)
                print state
                print state['current_file']
                print session
            #print 'wooh'


if not hasattr(main, '__file__'):
    """
    Running in interactive mode in the Python shell
    """
    print("whosthere running interactively in Python shell")

elif __name__ == '__main__':
    """
    whosthere is ran standalone, rock and roll
    """
    cli()
