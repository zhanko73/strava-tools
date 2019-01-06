#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import argparse, readline
import requests
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

def tag_string(tag):
    return tag.string.replace('\n','')
def tag_datetime(tag):
    return datetime.strptime(tag.get('datetime'), '%Y-%m-%d %H:%M:%S %Z')


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
    csrf_token = None
    owner_id = None
    feed_cursor = None
    feed_before = None

    def __init__(self, email):
        self.email = email
        self.session = requests.Session()
        self.get = lambda url: self.__process_response(self.__get(url))
        self.post = lambda url, data=None: self.__process_response(self.__post(url, data))
        self.get_store = lambda url: self.__store_response(self.__get(url))
        self.post_store = lambda url,data=None: self.__store_response(self.__post(url, data))

    def __get(self, url):
        return self.session.get(url, headers=StravaScraper.BASE_HEADERS)

    def __post(self, url, data=None):
        csrf_header = {}
        if self.csrf_token: csrf_header[StravaScraper.CSRF_H] = self.csrf_token

        headers = {**StravaScraper.BASE_HEADERS, **csrf_header}
        if data:
            return self.session.post(url, data=data, headers=headers)
        return self.session.post(url, headers=headers)

    def __process_response(self, response):
        response.raise_for_status()
        return response

    def __store_response(self, response):
        self.soup = BeautifulSoup(response.content, 'lxml')
        meta = first(self.soup.select('meta[name="csrf-token"]'))
        if meta:
            self.csrf_token = meta.get('content')
        return response

    def login(self, password):
        self.get_store(StravaScraper.URL_LOGIN)
        utf8 = self.soup.find_all('input',
                             {'name': 'utf8'})[0].get('value').encode('utf-8')
        token = self.soup.find_all('input',
                              {'name': 'authenticity_token'})[0].get('value')
        login_data = {
            'utf8': utf8,
            'authenticity_token': token,
            'plan': "",
            'email': self.email,
            'password': password,
        }

        self.post_store(StravaScraper.URL_SESSION, data=login_data)
        response = self.load_dashboard()
        assert("Log Out" in response.text)
        self.is_authed = True
        profile_a = first(self.soup.select('div.athlete-profile a'))
        if profile_a:
            self.owner_id = profile_a.get('href').split('/')[2]
        else: print('Profile issue')

    def send_kudo(self, activity_id):
        response = self.post(StravaScraper.URL_SEND_KUDO % activity_id)
        try: return response.json()['success'] == 'true'
        except: return False

    def load_page(self):
        with open('page.html', 'r') as file:
            self.soup = BeautifulSoup(file.read(), 'lxml')

    def load_feed(self):
        with open('feed.html', 'r') as file:
            self.soup = BeautifulSoup(file.read(), 'lxml')

    def load_dashboard(self, num=10):
        response = self.get_store(StravaScraper.URL_DASHBOARD % (num+1))
        self.store_feed_params()
        return response

    def load_feed_next(self):
        self.get_store(StravaScraper.URL_DASHBOARD_FEED % (self.owner_id, self.feed_before, self.feed_cursor))
        self.store_feed_params()

    def store_feed_params(self):
        cursor = first(self.soup.select('div.activity.feed-entry.card:last-of-type')).get('data-rank')
        if cursor and self.feed_cursor != cursor:
            #print("New cursor %s" % cursor)
            self.feed_cursor = cursor
        before = first(self.soup.select('div.activity.feed-entry.card:first-of-type')).get('data-updated-at')
        if before and self.feed_before != before:
            #print("New before %s" % before)
            self.feed_before = before

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
                print(e)
                print("Unparsable %s" % activity)


import cmd, getpass, texttables, functools
from sys import stdout
class StravaCLI(cmd.Cmd):

    class dialect(texttables.Dialect):
        header_delimiter = '-'

    prompt = 'strava >> '
    activities = []
    selected_activities = []
    
    def __init__(self, email):
        cmd.Cmd.__init__(self)
        self.scraper = StravaScraper(email)

    def do_EOF(self, line): return True

    def do_sample(self, line):
        self.scraper.load_page()
        self.store_activities()

    def do_login(self, line):
        pwd = getpass.getpass('password:')
        self.scraper.login(pwd)
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
            print('Sending kudo to %s for %s' % (activity['athlete'], activity['title']))
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
    args = parser.parse_args()

    init_readline()
    
    cli = StravaCLI(args.email)
    cli.cmdloop()

if __name__ == '__main__':
    main()
