#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests, http, time, traceback, sys, re, os, pathlib, json

from bs4 import BeautifulSoup
from datetime import datetime
from pprint import pprint

from stravatools import __version__
from stravatools._intern.tools import *

class StravaScraper(object):
    USER_AGENT = "stravatools/%s" % __version__
    BASE_HEADERS = {'User-Agent': USER_AGENT}
    CSRF_H = 'x-csrf-token'
    
    SESSION_COOKIE='_strava4_session'

    BASE_URL = "https://www.strava.com"
    URL_LOGIN = "%s/login" % BASE_URL
    URL_SESSION = "%s/session" % BASE_URL
    URL_DASHBOARD = "%s/dashboard/following/%%d" % BASE_URL
    URL_DASHBOARD_FEED = "%s/dashboard/feed?feed_type=following&athlete_id=%%s&before=%%s&cursor=%%s" % BASE_URL
    URL_SEND_KUDO = "%s/feed/activity/%%s/kudo" % BASE_URL

    soup = None
    response = None
    csrf_token = None
    feed_cursor = None
    feed_before = None

    def __init__(self, cert=None, debug=0):
        self.config = ScraperConfig()
        self.debug = debug
        self.cert = cert
        self.session = self.__create_session()
        self.get = lambda url, logged=True, allow_redirects=True: self.__store_response(self.__get(url, logged, allow_redirects))
        self.post = lambda url, data=None, logged=True, allow_redirects=True: self.__store_response(self.__post(url, data, logged, allow_redirects))
        self.greeting()

    def __create_session(self):
        session = requests.Session()
        cookies = http.cookiejar.MozillaCookieJar(str(self.config.cookies_path))
        try: cookies.load()
        except OSError: pass
        session.cookies = cookies
        return session

    def __get(self, url, logged=True, allow_redirects=True):
        self.__debug_request(url)
        response = self.session.get(url, headers=StravaScraper.BASE_HEADERS, verify=self.cert, allow_redirects=allow_redirects)
        self.__debug_response(response)
        self.__check_response(response, logged)
        return response

    def __post(self, url, data=None, logged=True, allow_redirects=True):
        self.__debug_request(url)
        csrf_header = {}
        if self.csrf_token: csrf_header[StravaScraper.CSRF_H] = self.csrf_token

        headers = {**StravaScraper.BASE_HEADERS, **csrf_header}
        if data:
            response = self.session.post(url, data=data, headers=headers, verify=self.cert, allow_redirects=allow_redirects)
        else:
            response = self.session.post(url, headers=headers, verify=self.cert, allow_redirects=allow_redirects)
        self.__debug_response(response)
        self.__check_response(response, logged)
        return response

    def __check_response(self, response, logged=False):
        response.raise_for_status()
        if logged and "class='logged-out" in response.text:
            raise NotLogged()
        return response

    def __debug_request(self, url):
        if self.debug > 0:
            print('>>> GET %s' % url)

    def __debug_response(self, response):
        if self.debug > 0:
            print('<<< Status %d' % response.status_code)
            print('<<< Headers')
            pprint(response.headers)
            if self.debug > 1 and 'Content-Type' in response.headers:
                print('<<< Body')
                if response.headers['Content-Type'] == 'text/html':
                    print(response.text)
                elif response.headers['Content-Type'] == 'application/json':
                    pprint(json.loads(response.text))
                else:
                    print(response.text)


    def __store_response(self, response):
        self.response = response
        self.soup = BeautifulSoup(response.text, 'lxml')
        meta = first(self.soup.select('meta[name="csrf-token"]'))
        if meta:
            self.csrf_token = meta.get('content')
        return response

    def __print_traceback(self):
        if self.debug > 0: traceback.print_exc(file=sys.stdout)

    def close(self):
        self.config.save()
        self.session.cookies.save()
        
    def login(self, email, password, remember_me=True):
        self.get(StravaScraper.URL_LOGIN, logged=False, allow_redirects=False)
        if self.response.status_code == 302:
            self.greeting()
            return True

        soup = BeautifulSoup(self.response.content, 'lxml')
        utf8 = soup.find_all('input',
                             {'name': 'utf8'})[0].get('value').encode('utf-8')
        token = soup.find_all('input',
                              {'name': 'authenticity_token'})[0].get('value')
        login_data = {
            'utf8': utf8,
            'authenticity_token': token,
            'plan': "",
            'email': email,
            'password': password
        }
        if remember_me:
            login_data['remember_me'] = 'on'

        self.post(StravaScraper.URL_SESSION, login_data, logged=False, allow_redirects=False)
        if self.response.status_code == 302 and self.response.headers['Location'] == StravaScraper.URL_LOGIN:
            return False

        self.load_dashboard()
        try:
            assert("Log Out" in self.response.text)
            profile = first(self.soup.select('div.athlete-profile'))
            self.config['owner_id'] = first(profile.select('a'), self.tag_get('href', lambda x:x.split('/')[-1]))
            self.config['owner_name'] = first(profile.select('div.athlete-name'), self.tag_string())
            self.greeting()
        except Exception as e:
            print('/!\\ Profile information cannot be retrieved, some features are disabled')
            self.__print_traceback()
        return True

    def logout(self):
        self.session.cookies.clear()

    def greeting(self):
        if self.config['owner_id']:
            print('Welcome %s' % self.config['owner_name'])

    def send_kudo(self, activity_id):
        try:
            response = self.post(StravaScraper.URL_SEND_KUDO % activity_id)
            return response.json()['success'] == 'true'
        except Exception as e:
            self.__print_traceback()
            return False

    def load_page(self, path='page.html'):
        with open(path, 'r') as file:
            self.soup = BeautifulSoup(file.read(), 'lxml')

    def load_dashboard(self, num=30):
        self.get(StravaScraper.URL_DASHBOARD % (num+1))
        self.__store_feed_params()

    def load_feed_next(self):
        self.get(StravaScraper.URL_DASHBOARD_FEED % (self.config['owner_id'], self.feed_before, self.feed_cursor))
        self.__store_feed_params()

    def __store_feed_params(self):
        remove_UTC = lambda x:x.replace(' UTC','')

        cards = list(self.soup.select('div.activity.feed-entry.card'))
        ranks = list(each(cards, self.tag_get('data-rank')))
        updated = list(each(cards, self.tag_get('data-updated-at')))
        datetimesUTC = list(each(self.soup.select('div.activity.feed-entry.card time time'), self.tag_get('datetime')))
        datetimes = list(map(remove_UTC, datetimesUTC))
        entries = list(zip(ranks, updated, datetimes))
        if len(entries) > 0:
            self.feed_cursor = sorted(entries, key=lambda data:data[0])[0][0]
            self.feed_before = sorted(entries, key=lambda data:data[2])[0][1]

    def activities(self):
        for activity in self.soup.select('div.activity'):
            try:
                entry = {
                    'athlete': first(activity.select('a.entry-owner'), self.tag_string()),
                    'time': first(activity.select('time time'), self.tag_string()),
                    'datetime': first(activity.select('time time'), self.tag_get('datetime', self.parse_datetime)),
                    'title': first(activity.select('h3 a'), self.tag_string()),
                    'id': first(activity.select('h3 a'), self.tag_get('href', lambda x: x.split('/')[-1])),
                    'distance': self.__extract_stat(activity, r'\s*Distance\s*(.+)\s'),
                    'duration': self.__extract_stat(activity, r'\s*Time\s*(.+)\s'),
                    'elevation':self.__extract_stat(activity, r'\s*Elevation Gain\s*(.+)\s'),
                    'kudo': first(activity.select('div.entry-footer div.media-actions button.js-add-kudo')) is None
                }
                yield entry
            except Exception as e:
                print("Unparsable %s" % activity)
                self.__print_traceback()

    # Utility functions
    def tag_string(self, mapper=lambda x:x):
        return lambda tag: mapper(tag.string.replace('\n',''))
    def tag_get(self, attr, mapper=lambda x:x):
        return lambda tag: mapper(tag.get(attr))
    def parse_datetime(self, value):
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S %Z')

    def __extract_stat(self, activity, pattern):
        for stat in activity.select('div.media-body ul.list-stats .stat'):
            m = re.search(pattern, stat.text)
            if m: return m.group(1)
        return ''

class NotLogged(Exception):
    pass

class ScraperConfig(object):
    CONFIG_DIR = '/'.join( (str(pathlib.Path.home()), '.strava-tools'))
    USER = 'user.json'
    COOKIES = 'cookies.txt'

    def __init__(self, config_path=None):
        self.basepath = pathlib.Path(config_path if config_path else ScraperConfig.CONFIG_DIR)
        self.basepath.mkdir(parents=True, exist_ok=True)
        self.user = self.__load(ScraperConfig.USER)
        self.cookies_path = self.basepath / ScraperConfig.COOKIES

    def __getitem__(self, key):
        if key in self.user: return self.user[key]
        return None

    def __setitem__(self, key, value):
        self.user[key] = value

    def __load(self, filename):
        path = self.basepath / filename
        if path.exists():
            with path.open() as file:
                return json.loads(file.read())
        return {}

    def __save(self, data, filname):
        with (self.basepath / filname).open('w') as file:
            file.write(json.dumps(data))

    def save(self):
        self.__save(self.user, ScraperConfig.USER)
