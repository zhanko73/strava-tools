#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import argparse, readline
import requests
import os
import time
import sys
from datetime import datetime
from pprint import pprint


VERSION = '0.1.0'

# Utility functions

def true_predicate():
    return lambda x: True

def find(predicate, iterable):
    for i in filter(predicate, iterable):
        return i
    return None

def first(xs, mapper=lambda x:x):
    if len(xs) > 0: return mapper(xs[0])
def each(xs, mapper=lambda x:x):
    for x in xs:
        yield mapper(x)

def tag_string(tag):
    return tag.string.replace('\n','')
def tag_get(attr):
    return lambda tag: tag.get(attr)
def tag_datetime(tag):
    return datetime.strptime(tag.get('datetime'), '%Y-%m-%d %H:%M:%S %Z')
def unix2string(value, all=False):
    fmt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(float(value))))
    if all:
        return '(%s -> %s)' % (value, fmt)
    return fmt


class StravaScraper(object):
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/User-Agent
    USER_AGENT = "stravalib-scraper/%s" % VERSION
    BASE_HEADERS = {'User-Agent': USER_AGENT}
    CSRF_H = 'x-csrf-token'

    BASE_URL = "https://www.strava.com"
    URL_LOGIN = "%s/login" % BASE_URL
    URL_SESSION = "%s/session" % BASE_URL
    URL_DASHBOARD = "%s/dashboard/following/%%d" % BASE_URL
    URL_DASHBOARD_FEED = "%s/dashboard/feed?feed_type=following&athlete_id=%%s&before=%%s&cursor=%%s" % BASE_URL
    URL_SEND_KUDO = "%s/feed/activity/%%s/kudo" % BASE_URL


    is_authed = False

    soup = None
    response = None
    csrf_token = None
    owner_id = None
    feed_cursor = None
    feed_before = None

    def __init__(self, email, cert=None, debug=False):
        self.debug = debug
        self.cert = cert
        self.email = email
        self.session = requests.Session()
        self.get = lambda url: self.__process_response(self.__get(url))
        self.post = lambda url, data=None: self.__process_response(self.__post(url, data))
        self.get_store = lambda url: self.__store_response(self.__get(url))
        self.post_store = lambda url,data=None: self.__store_response(self.__post(url, data))

    def __get(self, url):
        return self.session.get(url, headers=StravaScraper.BASE_HEADERS, verify=self.cert)

    def __post(self, url, data=None):
        csrf_header = {}
        if self.csrf_token: csrf_header[StravaScraper.CSRF_H] = self.csrf_token

        headers = {**StravaScraper.BASE_HEADERS, **csrf_header}
        if data:
            return self.session.post(url, data=data, headers=headers, verify=self.cert)
        return self.session.post(url, headers=headers, verify=self.cert)

    def __process_response(self, response):
        response.raise_for_status()
        return response

    def __store_response(self, response):
        self.response = response
        self.soup = BeautifulSoup(response.text, 'lxml')
        meta = first(self.soup.select('meta[name="csrf-token"]'))
        if meta:
            self.csrf_token = meta.get('content')
        return response

    def login(self, password):
        self.get_store(StravaScraper.URL_LOGIN)
        soup = BeautifulSoup(self.response.content, 'lxml')
        utf8 = soup.find_all('input',
                             {'name': 'utf8'})[0].get('value').encode('utf-8')
        token = soup.find_all('input',
                              {'name': 'authenticity_token'})[0].get('value')
        login_data = {
            'utf8': utf8,
            'authenticity_token': token,
            'plan': "",
            'email': self.email,
            'password': password,
        }

        self.post_store(StravaScraper.URL_SESSION, data=login_data)
        self.load_dashboard()
        assert("Log Out" in self.response.text)
        self.is_authed = True
        try:
            profile = first(self.soup.select('div.athlete-profile'))
            self.owner_id = first(profile.select('a'), lambda x: x.get('href').split('/')[-1])
            athlete_name = first(profile.select('div.athlete-name'), tag_string)
            print('Welcome %s' % athlete_name)
        except:
            print('/!\\ Profile information cannot be retrieved, some features are disabled')

    def send_kudo(self, activity_id):
        try:
            response = self.post(StravaScraper.URL_SEND_KUDO % activity_id)
            return response.json()['success'] == 'true'
        except: return False

    def load_page(self):
        with open('page.html', 'r') as file:
            self.soup = BeautifulSoup(file.read(), 'lxml')

    def load_feed(self):
        with open('feed.html', 'r') as file:
            self.soup = BeautifulSoup(file.read(), 'lxml')

    def load_dashboard(self, num=10):
        self.get_store(StravaScraper.URL_DASHBOARD % (num+1))
        self.store_feed_params()

    def load_feed_next(self):
        self.get_store(StravaScraper.URL_DASHBOARD_FEED % (self.owner_id, self.feed_before, self.feed_cursor))
        self.store_feed_params()

    def store_feed_params(self):
        remove_UTC = lambda x:x.replace(' UTC','')

        cards = list(self.soup.select('div.activity.feed-entry.card'))
        ranks = list(each(cards, tag_get('data-rank')))
        updated = list(each(cards, tag_get('data-updated-at')))
        datetimesUTC = list(each(self.soup.select('div.activity.feed-entry.card time time'), tag_get('datetime')))
        datetimes = list(map(remove_UTC, datetimesUTC))
        entries = list(zip(ranks, updated, datetimes))
        if len(entries) > 0:
            self.feed_cursor = sorted(entries, key=lambda data:data[0])[0][0]
            self.feed_before = sorted(entries, key=lambda data:data[2])[0][1]
            if self.debug:
                print('Entries')
                pprint(list(each(entries, lambda data: list(map(unix2string, (data[0], data[1]))) + [data[2]] )))
                print("New cursor %s" % unix2string(self.feed_cursor, True))
                print("New before %s" % unix2string(self.feed_before, True))

    def activities(self):
        for activity in self.soup.select('div.activity'):
            try:
                entry = {
                    'athlete': first(activity.select('a.entry-owner'), tag_string),
                    'time': first(activity.select('time time'), tag_string),
                    'datetime': first(activity.select('time time'), tag_datetime),
                    'title': first(activity.select('h3 a'), tag_string),
                    'id': first(activity.select('h3 a'), lambda x: x.get('href').split('/')[-1]),
                    'kudo': first(activity.select('div.entry-footer div.media-actions button.js-add-kudo')) is None
                }
                yield entry
            except Exception as e:
                #with open('/tmp/soup.html', 'w') as file: file.write(self.soup.text)
                #with open('/tmp/content.html', 'w') as file: file.write(self.content)
                import traceback
                print("Unparsable %s" % activity)
                traceback.print_exc(file=sys.stdout)


import cmd, getpass, texttables, functools
from sys import stdout
class StravaCLI(cmd.Cmd):

    class dialect(texttables.Dialect):
        header_delimiter = '-'

    prompt = 'strava >> '
    activities = []
    selected_activities = []
    
    def __init__(self, scraper):
        cmd.Cmd.__init__(self)
        self.scraper = scraper

    def do_EOF(self, line): return True

    def do_sample(self, line):
        self.scraper.load_page()
        self.store_activities()

    def do_login(self, line):
        if 'STRAVA_PWD' in os.environ:
            self.scraper.login(os.environ['STRAVA_PWD'])
        else:
            self.scraper.login(getpass.getpass('password:'))
        self.store_activities()

    def do_load(self, line):
        args = self.parse(line, '-next num:?10')
        if args.next:
            self.scraper.load_feed_next()
        else:
            self.scraper.load_dashboard(int(args.num))
        self.store_activities()

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
            data = map(self.activity_for_output, self.selected_activities)
            with texttables.dynamic.DictWriter(stdout, ['Kudo', 'time', 'athlete', 'title'], dialect=StravaCLI.dialect) as w:
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
        return lambda item: param in item['athlete'].lower() if param else true_predicate()
    def filter_title(self, param):
        return lambda item: param in item['title'].lower() if param else true_predicate()
    def filter_kudo(self, sent):
        return lambda item: item['kudo'] == sent if sent != None else true_predicate()
    def filter_id(self, activity_id):
        return lambda item: item['id'] == activity_id if activity_id else true_predicate()

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
    parser.add_argument("email", help="Strava Username")
    parser.add_argument("--cert", help="Cert file")
    parser.add_argument("--debug", action='store_true', default=False, help="Debug mode")
    args = parser.parse_args()

    init_readline()
    scraper = StravaScraper(args.email, cert=args.cert, debug=args.debug)
    cli = StravaCLI(scraper)
    cli.cmdloop()

if __name__ == '__main__':
    main()
