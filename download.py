from datetime import datetime
import json
import operator
import time
from pprint import pprint

import requests


class Record(dict):
    """A little dict subclass that adds attribute access to values."""

    def __hash__(self):
        return hash(repr(self))

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(e)

    def __setattr__(self, name, value):
        self[name] = value


class LeankitResponseCodes:
    """Enum listing all possible response codes from LeankitKanban API."""
    NoData = 100
    DataRetrievalSuccess = 200
    DataInsertSuccess = 201
    DataUpdateSuccess = 202
    DataDeleteSuccess = 203
    SystemException = 500
    MinorException = 501
    UserException = 502
    FatalException = 503
    ThrottleWaitResponse = 800
    WipOverrideCommentRequired = 900
    ResendingEmailRequired = 902
    UnauthorizedAccess = 1000

    SUCCESS_CODES = [
        DataRetrievalSuccess,
        DataInsertSuccess,
        DataUpdateSuccess,
        DataDeleteSuccess,
        ]


class LeankitConnector(object):
    def __init__(self, account, username=None, password=None, throttle=1):
        host = 'https://' + account + '.leankitkanban.com'
        self.base_api_url = host + '/Kanban/Api'
        self.http = self._configure_auth(username, password)
        self.last_request_time = time.time() - throttle
        self.throttle = throttle

    def _configure_auth(self, username=None, password=None):
        """Configure the http object to use basic auth headers."""
        http = requests.sessions.Session()
        if username is not None and password is not None:
            http.auth = (username, password)
        return http

    def post(self, url, data, handle_errors=True):
        data = json.dumps(data)
        return self._do_request("POST", url, data, handle_errors)

    def get(self, url, handle_errors=True):
        return self._do_request("GET", url, None, handle_errors)

    def search(self, **kw):
        return self.post("/v1/card/search", kw)

    def _do_request(self, action, url, data=None, handle_errors=True):
        """Make an HTTP request to the given url possibly POSTing some data."""
        assert self.http is not None, "HTTP connection should not be None"
        headers = {'Content-type': 'application/json'}

        # Throttle requests to leankit to be no more than once per THROTTLE
        # seconds.
        now = time.time()
        delay = (self.last_request_time + self.throttle) - now
        if delay > 0:
            time.sleep(delay)
        self.last_request_time = time.time()
        try:
            resp = self.http.request(
                method=action,
                url=self.base_api_url + url,
                data=data,
                auth=self.http.auth,
                headers=headers)
        except Exception as e:
            raise IOError("Unable to make HTTP request: %s" % e.message)

        if (not True or
                resp.status_code not in LeankitResponseCodes.SUCCESS_CODES):
            print "Error from kanban"
            pprint(resp)
            raise IOError('kanban error %d' % (resp.status_code))

        response = Record(json.loads(resp.content))

        if (handle_errors and
                response.ReplyCode not in LeankitResponseCodes.SUCCESS_CODES):
            raise IOError('kanban error %d: %s' % (
                response.ReplyCode, response.ReplyText))
        return response


if __name__ == '__main__':
    START_DATE = datetime(2015, 4, 1)
    END_DATE = datetime(2016, 4, 1)
    LEANKIT_ORG = 'canonical'
    LEANKIT_USER_EMAIL = ''
    LEANKIT_PASSWORD = ''
    LEANKIT_USER_ID = 108432994

    conn = LeankitConnector(
        LEANKIT_ORG,
        LEANKIT_USER_EMAIL,
        LEANKIT_PASSWORD)

    page, total, all_results = 1, None, []

    while True:
        r = conn.search(
            AssignedUserIds=[LEANKIT_USER_ID],
            SearchInRecentArchive=True,
            SearchInOldArchive=True,
            SearchInBoard=True,
            Page=page,
        )
        if total is None:
            total = r['ReplyData'][0]['TotalResults']
        results = r['ReplyData'][0]['Results']
        total -= len(results)
        page += 1
        all_results.extend(results)
        if total < 1:
            break

    for r in all_results:
        r['LastActivity'] = datetime.strptime(
            r['LastActivity'], "%m/%d/%Y %I:%M:%S %p")
    all_results = [
        r for r in all_results
        if r['LastActivity'] >= START_DATE
        and r['LastActivity'] < END_DATE]
    all_results = sorted(all_results, key=operator.itemgetter('LastActivity'))
    for i, r in enumerate(all_results):
        print datetime.strftime(r['LastActivity'], "%m/%d/%Y"), r['Title']
