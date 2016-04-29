import sys
import os
import __main__ as main
from utilkit import datetimeutil, printutil
import json
import click


def parselog(state, log):
    """
    Parse contents of the `log` list, considering the info already in `state`.
    Return new version of `state`.

    Format of `state`:
    {'current_file': 'filename', 'current_line': NN, 'macs': {'<MAC ADDRESS 1>': [
     {'session_start': '<datetime>', 'session_end': '<datetime>', 'ip': '<ip address>'}, {'session_start'...}], '<MAC ADDRESS 2>': [...]},
    'timestamp': <latest timestamp>, 'previous_timestamp': <previous timestamp>,
    'previous_macs': ['<MAC ADDRESS 2>', '<MAC ADDRESS 4>'], 'current_macs': ['<MAC ADDRESS 2>', '<MAC ADDRESS 3>']}
    """
    #timezonestring = '+0100'
    #if datetimeutil.is_dst('Europe/Amsterdam'):
    #    timezonestring = '+0200'

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


def read_state(macfile):
    """
    Get state log from disk and read the MAC address mappings
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

    return state, read_macmappings_file(macfile)


def filter_sessions(state, mac_to_name, macs, allsessions=True, no_headers=False):
    """
    Show (all|latest) sessions for the clients in macs[]
    """
    data = []
    for mac in state['macs']:
        if mac in macs:
            try:
                name = mac_to_name[mac]
            except KeyError:
                name = '-' # (unknown)
            if allsessions:
                for info in state['macs'][mac]:
                    if info['session_end'] == None:
                        info['session_end'] = ''
                    data.append([mac, info['ip'], name, info['session_start'], info['session_end']])
            else:
                info = state['macs'][mac][-1]
                if info['session_end'] == None:
                    info['session_end'] = ''
                data.append([mac, info['ip'], name, info['session_start'], info['session_end']])

    if no_headers:
        return printutil.to_smart_columns(data)
    else:
        headers = ['MAC', 'IP', 'name', 'session start', 'session end']
        return printutil.to_smart_columns(data, headers)


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
    state, mac_to_name = read_state(macfile)

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
    print(printutil.to_smart_columns(data, headers))


@cli.command()
@click.option('--macfile', prompt='Path to file with MAC address mappings')
def current_sessions(macfile):
    """
    Show currently open sessions
    """
    state, mac_to_name = read_state(macfile)

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
    print(printutil.to_smart_columns(data, headers))


@cli.command()
@click.option('--address', prompt='MAC address to show the sessions for')
@click.option('--macfile', prompt='Path to file with MAC address mappings')
@click.option('--all/--latest', prompt='Show all? (Otherwise only the latest session is shown)', default=True)
@click.option('--no-headers', is_flag=True)
def client_sessions(address, macfile, all, no_headers):
    """
    Show all sessions for a certain client
    """
    state, mac_to_name = read_state(macfile)

    print filter_sessions(state, mac_to_name, [address], all, no_headers)


@cli.command()
@click.option('--find', prompt='Text to search for in name/description')
@click.option('--macfile', prompt='Path to file with MAC address mappings')
@click.option('--all/--latest', prompt='Show all? (Otherwise only the latest session is shown)', default=True)
@click.option('--no-headers', is_flag=True)
def search_client_sessions(find, macfile, all, no_headers):
    """
    Search for `find` in the name/description and find the sessions for this client/those clients
    """
    state, mac_to_name = read_state(macfile)

    macs = []
    for mac in state['macs']:
        try:
            if find.lower() in mac_to_name[mac].lower():
                macs.append(mac)
        except KeyError:
            # MAC not found in mapping file, skip
            pass

    print filter_sessions(state, mac_to_name, macs, all, no_headers)


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
