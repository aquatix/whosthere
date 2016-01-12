import sys
import os
import __main__ as main
from datetime import datetime, timedelta
import json
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


def to_even_columns(data, headers=None):
    """
    Nicely format the 2-dimensional list into evenly spaced columns
    """
    result = ''
    col_width = max(len(word) for row in data for word in row) + 2  # padding
    if headers:
        header_width = max(len(word) for row in headers for word in row) + 2
        if header_width > col_width:
            col_width = header_width

        result += "".join(word.ljust(col_width) for word in headers) + "\n"
        result += '-' * col_width * len(headers) + "\n"

    for row in data:
        result += "".join(word.ljust(col_width) for word in row) + "\n"
    return result


def to_smart_columns(data, headers=None, padding=2):
    """
    Nicely format the 2-dimensional list into columns
    """
    result = ''
    col_widths = []
    for row in data:
        col_counter = 0
        for word in row:
            try:
                col_widths[col_counter] = max(len(word), col_widths[col_counter])
            except IndexError:
                col_widths.append(len(word))
            col_counter += 1

    if headers:
        col_counter = 0
        for word in headers:
            try:
                col_widths[col_counter] = max(len(word), col_widths[col_counter])
            except IndexError:
                col_widths.append(len(word))
            col_counter += 1

    # Add padding
    col_widths = [width + padding for width in col_widths]
    total_width = sum(col_widths)

    if headers:
        col_counter = 0
        for word in headers:
            result += "".join(word.ljust(col_widths[col_counter]))
            col_counter += 1
        result += "\n"
        result += '-' * total_width + "\n"

    for row in data:
        col_counter = 0
        for word in row:
            result += "".join(word.ljust(col_widths[col_counter]))
            col_counter += 1
        result += "\n"
    return result


def parselog(state, log):
    """
    Parse contents of the `log` list, considering the info already in `state`.
    Return new version of `state`.

    Format of `state`:
    {'current_file': 'filename', 'current_line': NN, 'macs': {'<MAC ADDRESS 1>': [{'session_start': '<datetime>', 'session_end': '<datetime>', 'ip': '<ip address>'}, {'session_start'...}], '<MAC ADDRESS 2>': [...]},
    'timestamp': <latest timestamp>, 'previous_timestamp': <previous timestamp>, 'previous_macs': ['<MAC ADDRESS 2>', '<MAC ADDRESS 4>'], 'current_macs': ['<MAC ADDRESS 2>', '<MAC ADDRESS 3>']}
    """
    timezonestring = '+0100'
    if is_dst('Europe/Amsterdam'):
        timezonestring = '+0200'

    should_seek = False
    if state['current_line'] > 0:
        should_seek = True

    current_line = 0
    for line in log:
        current_line += 1
        if should_seek and current_line <= state['current_line']:
            # We should seek until we found where we ended last time, skip this one
            continue

        parts = line.split(' = ')
        mac_address = parts[1].strip()
        if not mac_address in state['macs']:
            state['macs'][mac_address] = []
        dt_info = parts[0].split(' ')
        #timestamp = load_datetime(timestamp + timezonestring, "%d-%m-%Y %H:%M:%S%z")
        #timestamp = load_datetime(dt_info[0] + ' ' + dt_info[1] + timezonestring, "%Y-%m-%d %H:%M:%S%z")
        timestamp = dt_info[0] + ' ' + dt_info[1]
        if timestamp != state['timestamp']:
            # New series of log entries, we might need to close some sessions:
            for gone_mac_address in state['previous_macs']:
                #print(state['previous_timestamp'] + ' Ending session for ' + gone_mac_address)
                state['macs'][gone_mac_address][-1]['session_end'] = state['previous_timestamp']

            # Update session to current series
            state['previous_macs'] = list(state['current_macs'])
            state['current_macs'] = []
            state['previous_timestamp'] = state['timestamp']
            state['timestamp'] = timestamp

        try:
            latest_entry = state['macs'][mac_address][-1]
        except IndexError:
            # Start new session, apparently this MAC address is new to the list
            latest_entry = {'session_start': timestamp, 'session_end': None, 'ip': dt_info[2]}
            state['macs'][mac_address].append(latest_entry)

        if latest_entry['session_end']:
            # Previous entry was end of a session, create new session
            latest_entry = {'session_start': timestamp, 'session_end': None, 'ip': dt_info[2]}
            state['macs'][mac_address].append(latest_entry)

        state['macs'][mac_address][-1] = latest_entry
        state['current_macs'].append(mac_address)
        try:
            state['previous_macs'].remove(mac_address)
        except ValueError:
            # MAC wasn't found in previous list
            pass

    state['current_line'] = current_line
    return state


def read_macmappings_file(macfile):
    """
    Read and parse MAC address to readable name mappings
    """
    with open(macfile, 'r') as f:
        mappings = f.readlines()
        mappings = [x.strip('\n') for x in mappings]

    names = {}

    for line in mappings:
        parts = line.split('=')#
        names[parts[0]] = parts[1]
    return names


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
def parselogs(logdir, prefix):
    """
    Parse the whosthere logs
    """
    state = {'current_file': None, 'current_line': 0, 'macs': {},
             'timestamp': None, 'previous_timestamp': None, 'previous_macs': [], 'current_macs': []}

    if os.path.isfile('state.json') and os.path.isfile('session.json'):
        # Load saved state from storage
        with open('state.json', 'r') as f:
            state = json.load(f)

    should_seek = False
    if state['current_file']:
        # We should seek until we found the one we ended last time
        should_seek = True

    # Get all filenames in the logdir
    logfiles = os.listdir(logdir)
    # Make sure the files are ordered by the dates in their names
    logfiles.sort()
    for filename in logfiles:
        if filename[-4:] == '.log' and filename[0:len(prefix)] == prefix:
            if should_seek and state['current_file'] != filename:
                # We should seek until we found the one we ended last time, skip this one
                continue
            with open(os.path.join(logdir, filename)) as f:
                content = f.readlines()
                content = [x.strip('\n') for x in content]
                state['current_file'] = filename
                if should_seek == False:
                    # It's a fresh file, start at the top
                    state['current_line'] = 0
                elif should_seek and state['current_file'] == filename:
                    # We're done skipping files
                    should_seek = False
                parselog(state, content)

    # Save our state
    with open('state.json', 'w') as f:
        f.write(json.dumps(state))


@cli.command()
@click.option('--macfile', prompt='Path to file with MAC address mappings')
def last_sessions(macfile):
    """
    Show latest sessions for all known clients
    """
    if os.path.isfile('state.json'):
        # Load saved state from storage
        with open('state.json', 'r') as f:
            state = json.load(f)
    else:
        print("No state saved to disk (state.json), so can't extract info")
        sys.exit(1)

    if not os.path.isfile(macfile):
        print('File with MAC address mappings not found: ' + macfile)
        sys.exit(1)

    mac_to_name = read_macmappings_file(macfile)

    data = []
    for mac in state['macs']:
        try:
            name = mac_to_name[mac]
        except KeyError:
            name = '-' # (unknown)
        info = state['macs'][mac][-1]
        if info['session_end'] == None:
            info['session_end'] = ''
        data.append([mac, info['ip'], name, info['session_start'], info['session_end']])

    headers = ['MAC', 'IP', 'name', 'session start', 'session end']
    print(to_smart_columns(data, headers))


@cli.command()
@click.option('--macfile', prompt='Path to file with MAC address mappings')
def current_sessions(macfile):
    """
    Show currently open sessions
    """
    if os.path.isfile('state.json'):
        # Load saved state from storage
        with open('state.json', 'r') as f:
            state = json.load(f)
    else:
        print("No state saved to disk (state.json), so can't extract info")
        sys.exit(1)

    if not os.path.isfile(macfile):
        print('File with MAC address mappings not found: ' + macfile)
        sys.exit(1)

    mac_to_name = read_macmappings_file(macfile)

    data = []
    for mac in state['macs']:
        try:
            name = mac_to_name[mac]
        except KeyError:
            name = '-' # (unknown)
        info = state['macs'][mac][-1]
        if info['session_end'] == None:
            data.append([mac, info['ip'], name, info['session_start']])

    headers = ['MAC', 'IP', 'name', 'session start']
    print(to_smart_columns(data, headers))


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
