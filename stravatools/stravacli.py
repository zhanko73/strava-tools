#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cmd, texttables, functools, argparse, readline, sys, os, getpass
from stravascraper import StravaScraper

from _intern.tools import *

class StravaCLI(cmd.Cmd):

    class dialect(texttables.Dialect):
        header_delimiter = '-'

    prompt = 'strava >> '
    activities = []
    selected_activities = []
    
    def __init__(self, scraper):
        cmd.Cmd.__init__(self)
        self.scraper = scraper

    def do_EOF(self, line):
        self.scraper.close()
        return True

    def do_sample(self, line):
        self.scraper.load_page()
        self.store_activities()

    def do_login(self, line):
        username = input('Username: ')
        password = getpass.getpass('Password:')
        if self.scraper.login(username, password):
            self.store_activities()
        else:
            print('Username or Password incorrect')

    def do_logout(self, line):
        self.scraper.logout()
        print('Logged out')

    def do_load(self, line):
        args = self.parse(line, '-next num:?10')
        if args.next:
            self.scraper.load_feed_next()
        else:
            self.scraper.load_dashboard(int(args.num))
        self.store_activities()

    def emptyline(self):
        pass

    def do_activities(self, line):
        args = self.parse(line, '-a: -t: -k')
        predicate = functools.reduce(lambda a,b: lambda item: a(item) and b(item), [
            self.filter_athlete(args.a),
            self.filter_title(args.t),
            self.filter_kudo(args.k)
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
        for activity in filter(self.filter_kudo(False), self.selected_activities):
            print('Kudoing %s for %s .. ' % (activity['athlete'], activity['title']), end='')
            status = self.scraper.send_kudo(activity['id'])
            if status:
                activity['kudo'] = True
                activity['dirty'] = True
                print('Ok')
            else: print('Failed')

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
        return lambda item: param.lower() in item['athlete'].lower() if param else self.true_predicate
    def filter_title(self, param):
        return lambda item: param.lower() in item['title'].lower() if param else self.true_predicate
    def filter_kudo(self, sent):
        return lambda item: item['kudo'] == sent if sent != None else self.true_predicate
    def filter_id(self, activity_id):
        return lambda item: item['id'] == activity_id if activity_id else self.true_predicate

    # utility functions
    def true_predicate(self, x): return true

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
                parser.add_argument(p[0], action='store_const', const=True)
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
    parser.add_argument("--debug", action='store_true', default=False, help="Debug mode")
    args = parser.parse_args()

    init_readline()
    scraper = StravaScraper(cert=args.cert, debug=args.debug)
    cli = StravaCLI(scraper)
    cli.cmdloop()
