# -*- coding: utf-8 -*-

import cmd, texttables, functools, argparse, readline, sys, os, getpass, datetime
from stravatools.scraper import StravaScraper, NotLogged

from stravatools import __version__
from stravatools._intern.tools import *

class StravaCLI(cmd.Cmd):

    class dialect(texttables.Dialect):
        header_delimiter = '-'

    prompt = 'strava >> '
    activities = []
    selected_activities = []
    
    def __init__(self, scraper):
        cmd.Cmd.__init__(self)
        self.scraper = scraper

    def do_login(self, line):
        '''Login to Strava (www.strava.com)
  You will be asked to provider you username (email) and password
  and eventually store a cookie to keep your strava session open'''
    
        username = input('Username: ')
        password = getpass.getpass('Password:')
        remember = 'n' != input('Remember session (password will not be stored) [Y/n]: ').lower()
        if self.scraper.login(username, password, remember):
            self.store_activities()
        else:
            print('Username or Password incorrect')

    def do_logout(self, line):
        '''Simply clean your cookies session if any was store'''

        self.scraper.logout()
        print('Logged out')

    def do_load(self, line):
        '''Loads activity feed from Strava and store activities
  load [num] (default 20)
    Loads n activties. From latest
  load -next
    Loads next activity from activity feed. Usually this will load the next 30 activities'''

        args = self.parse(line, '-next num:?20')
        if args.next:
            self.scraper.load_feed_next()
        else:
            self.scraper.load_dashboard(int(args.num))
        self.store_activities()

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

        args = self.parse(line, '-a: -t: -k -K')
        predicate = all_predicates([
            self.filter_athlete(args.a),
            self.filter_title(args.t),
            self.filter_kudo(args.k),
            self.filter_kudo(args.K)
        ])
        
        self.selected_activities = list(filter(predicate, self.activities))
        print('Activities %d/%d' % (len(self.selected_activities), len(self.activities)))
        if len(self.selected_activities) > 0:
            data = map(self.activity_for_output, self.selected_activities[::-1])
            headers = ['Kudo', 'time', 'athlete', 'duration' ,'distance' ,'elevation', 'title']
            with texttables.dynamic.DictWriter(sys.stdout, headers, dialect=StravaCLI.dialect) as w:
                w.writeheader()
                w.writerows(data)

    def do_kudo(self, line):
        '''Send kudo to all filtered activities'''

        for activity in filter(self.filter_kudo(False), self.selected_activities):
            print('Kudoing %s for %s .. ' % (activity['athlete'], activity['title']), end='')
            status = self.scraper.send_kudo(activity['id'])
            if status:
                activity['kudo'] = True
                activity['dirty'] = True
                print('Ok')
            else: print('Failed')

    def do_quit(self, line):
        'Nicely quit the shell'
        self.scraper.close()
        print("You're safe to go!")
        return True

    def do_EOF(self, line):
        "Ctrl+D to quit, same as 'quit' command"
        self.scraper.close()
        return True

    def emptyline(self):
        pass

    def onecmd(self, line):
        try:
            return super().onecmd(line)
        except NotLogged:
            print('You need to login first')
            return False

    def activity_for_output(self, activity):
        data = {'Kudo':''}
        data.update(activity)
        if activity['kudo']: data['Kudo'] = u'\u2713'
        if activity['dirty']: data['Kudo'] = '*'
        data['title'] = data['title'][:30]
        return data

    def store_activities(self):
        scraped_activities = list(map(lambda x: x.update({'dirty':False}) or x, self.scraper.activities()))
        new_activities = []
        for activity in scraped_activities:
            stored_activity = find(self.filter_id(activity['id']), self.activities)
            if not stored_activity or stored_activity['dirty']:
                new_activities.append(activity)

        self.activities.extend(new_activities)
        self.activities = sorted(self.activities, reverse=True, key=lambda x: x['datetime'])
        print("Loaded %d activities" % len(new_activities))

    def filter_athlete(self, param):
        return lambda item: contains(param, item['athlete'])
    def filter_title(self, param):
        return lambda item: contains(param, item['title'])
    def filter_kudo(self, sent):
        return lambda item: eq_bool(sent, item['kudo'])
    def filter_id(self, param):
        return lambda item: eq(param, item['id'])

    def parse(self, line, params):
        parser = argparse.ArgumentParser()
        for param in params.split():
            p = param.split(':')
            if len(p) > 1:
                default = p[1].find('?')
                if default >= 0:
                    parser.add_argument(p[0], nargs='?', default=p[1][default+1])    
                else:
                    parser.add_argument(p[0])
            else:
                value = p[0] == p[0].upper() # example: -K => True, -k => False
                parser.add_argument(p[0], action='store_const', const=value)
        args = parser.parse_args(line.split())
        return args



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
    scraper = StravaScraper(cert=args.cert, debug=debug)
    cli = StravaCLI(scraper)
    cli.cmdloop()
