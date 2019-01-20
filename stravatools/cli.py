# -*- coding: utf-8 -*-

import cmd, texttables, functools, argparse, readline, sys, os, getpass, datetime
from stravatools.client import Client
from stravatools.scraper import StravaScraper, NotLogged, WrongAuth
from pprint import pprint

from stravatools import __version__
from stravatools._intern.tools import *


class StravaCLI(cmd.Cmd):

    class dialect(texttables.Dialect):
        header_delimiter = '-'

    prompt = 'strava >> '
    
    def __init__(self, client):
        cmd.Cmd.__init__(self)
        self.client = client
        self.greeting()

    def do_load_page(self, line):
        (new, total) = self.client.load_page(line)
        print('Loaded %d activities' % new)

    def do_login(self, line):
        '''Login to Strava (www.strava.com)
  You will be asked to provider you username (email) and password
  and eventually store a cookie to keep your strava session open'''
    
        username = input('Username: ')
        password = getpass.getpass('Password:')
        remember = 'n' != input('Remember session (password will not be stored) [Y/n]: ').lower()
        try:
            self.client.login(username, password, remember)
            self.greeting()
        except WrongAuth:
            print('Username or Password incorrect')

    def do_logout(self, line):
        '''Simply clean your cookies session if any was store'''

        self.client.logout()
        print('Logged out')

    def do_load(self, line):
        '''Loads activity feed from Strava and store activities
  load [num] (default 20)
    Loads n activties. From latest
  load -next
    Loads next activity from activity feed. Usually this will load the next 30 activities
  load -all
    Loads all available activities from activity feed.'''

        args = self.parse(line, '-all -next num:?20')
        if args.all:
            (new, total) = self.client.load_activity_feed(num=100)
            s = new
            while new > 0:
                (new, total) = self.client.load_activity_feed(next = True)
                s = s + new
            new = s
        else:
            (new, total) = self.client.load_activity_feed(next = args.next, num = int(args.num))
        print('Loaded %d activities' % new)
    def do_activities(self, line):
        '''Dispaly loaded activity and let to filter them
  activities
    Display all activities
  activities -a <pattern>
    Filter and display activities that pattern match the athlete name
  activities -t <pattern>
    Filter and display activities that pattern match the title name
  activities -K
    Filter and display activities you have already sent a kudo
  activities -k
    Filter and display activities you haven't sent a kudo

  <pattern> [-]<string> ('-' negate)'''

        args = self.parse(line, '-a: -k -K')
        predicate = all_predicates([
            self.filter_athlete(args.a),
            self.filter_kudo(args.k),
            self.filter_kudo(args.K)
        ])
        
        self.client.select_activities(predicate)

        print('Activities %d/%d' % (len(self.client.selected_activities), len(self.client.activities)))
        if len(self.client.selected_activities) > 0:
            mapper = {
                'Kudo': lambda a: '*' if a.dirty else u'\u2713' if a.kudoed else '',
                'Time': lambda a: datetime.datetime.strftime(a.datetime, '%Y-%m-%d %H:%M:%S %Z'),
                'Athlete': lambda a: a.athlete.name,
                'Sport': lambda a: a.sport.name,
                'Duration': lambda a: a.sport.duration.for_human(),
                'Distance': lambda a: a.sport.distance.for_human(),
                'Elevation': lambda a: a.sport.elevation.for_human(),
                'Velocity': lambda a: a.sport.velocity().for_human(),
                'Title': lambda a: a.title,
            }

            make_entry = lambda activity: map(lambda kv: (kv[0], kv[1](activity)), mapper.items())
            data = list(map(dict, map(make_entry, self.client.selected_activities[::-1])))
            with texttables.dynamic.DictWriter(sys.stdout, list(mapper.keys()), dialect=StravaCLI.dialect) as w:
                w.writeheader()
                w.writerows(data)

    def do_kudo(self, line):
        '''Send kudo to all filtered activities'''

        for activity in filter(self.filter_kudo(False), self.client.selected_activities):
            print('Kudoing %s for %s .. ' % (activity.athlete.name, activity.title), end='')
            if activity.send_kudo(): print('Ok')
            else: print('Failed')

    def do_quit(self, line):
        'Nicely quit the shell'
        self.client.close()
        print("You're safe to go!")
        return True

    def do_EOF(self, line):
        "Ctrl+D to quit, same as 'quit' command"
        self.client.close()
        return True

    def greeting(self):
        if self.client.get_owner():
            print('Welcome %s' % self.client.get_owner().name)

    def emptyline(self):
        pass

    def onecmd(self, line):
        try:
            return super().onecmd(line)
        except NotLogged:
            print('You need to login first')
            return False

    def filter_athlete(self, param):
        return lambda activity: contains(param, activity.athlete.name)
    def filter_kudo(self, sent):
        return lambda activity: eq_bool(sent, activity.kudoed)
    
    def parse(self, line, params):
        parser = argparse.ArgumentParser()
        for param in params.split():
            p = param.split(':')
            if len(p) > 1:
                # param need a parameter
                default = p[1].find('?')
                if default >= 0:
                    parser.add_argument(p[0], nargs='?', default=p[1][default+1:])    
                else:
                    parser.add_argument(p[0])
            else:
                if len(param) == 2 and param[0] == '-': # example -k or -K
                    value = param == param.upper() # example: -K => True, -k => False
                    parser.add_argument(param, action='store_const', const=value)
                elif param[0] == '-': # example -next
                    parser.add_argument(param, action='store_const', const=True)
        return parser.parse_args(line.split())

def init_readline():
    import atexit, os
    histfile = os.path.join(os.path.expanduser("~"), ".strava_history")
    try:
        readline.read_history_file(histfile)
        h_len = readline.get_current_history_length()
    except FileNotFoundError:
        open(histfile, 'wb').close()
        h_len = 0
    atexit.register(save_history, h_len, histfile)


def save_history(prev_h_len, histfile):
    new_h_len = readline.get_current_history_length()
    readline.set_history_length(1000)
    readline.append_history_file(new_h_len - prev_h_len, histfile)

def main():
    parser = argparse.ArgumentParser("Strava CLI")
    parser.add_argument("--cert", help="Cert file")
    parser.add_argument("--debug", action='store_const', const=1, default=0, help="Debug mode")
    parser.add_argument("--debug-verbose", action='store_const', const=2, default=0, help="Verbose debug mode")
    args = parser.parse_args()

    print('Strava Shell %s' % (__version__))

    debug = args.debug + args.debug_verbose
    if debug > 0:
        print(args)
    init_readline()
    cli = StravaCLI(Client(cert=args.cert, debug=debug))
    cli.cmdloop()
