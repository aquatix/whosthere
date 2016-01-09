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


def parselog(state, log):
    """
    Parse contents of the `log` list, considering the info already in `state`.
    Return new version of `state`.

    Format of `state`:
    {'<MAC ADDRESS 1>': [{'session_start': '<datetime>', 'session_end': '<datetime>', 'ip': '<ip address>'}, {'session_start'...}], '<MAC ADDRESS 2>': [...]}
    """
    timezonestring = '+0100'
    if is_dst('Europe/Amsterdam'):
        timezonestring = '+0200'

    for line in log:
        #print line
        parts = line.split(' = ')
        mac_address = parts[1].strip()
        if not mac_address in state:
            state[mac_address] = []
        dt_info = parts[0].split(' ')
        #datetime = load_datetime(timestamp + timezonestring, "%d-%m-%Y %H:%M:%S%z")
        datetime = load_datetime(dt_info[0] + ' ' + dt_info[1] + timezonestring, "%Y-%m-%d %H:%M:%S%z")

        try:
            latest_entry = state[mac_address][-1]
        except IndexError:
            latest_entry = {'session_start': datetime, 'session_end': None, 'ip': dt_info[2]}
            state[mac_address].append(latest_entry)

        if latest_entry['session_end']:
            # Previous entry was end of a session, create new session
            latest_entry = {'session_start': datetime, 'session_end': None, 'ip': dt_info[2]}
            state[mac_address].append(latest_entry)

        state[mac_address][-1] = latest_entry

    return state


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
    state = {}
    logfiles = os.listdir(logdir)
    logfiles.sort()
    #print logfiles
    for filename in logfiles:
        #print filename[-4:]
        #print filename[0:len(prefix)]
        if filename[-4:] == '.log' and filename[0:len(prefix)] == prefix:
            with open(filename) as f:
                content = f.readlines()
                content = [x.strip('\n') for x in content]
                state = parselog(state, content)
                print state
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
