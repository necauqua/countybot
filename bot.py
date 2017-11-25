
import argparse
import json
import requests
import re

from http.server import BaseHTTPRequestHandler, HTTPStatus, HTTPServer

VERSION = '1.0.0'
NAME = 'CountyBot'

FULL_NAME = NAME + '/' + VERSION
ALLOWED_UPDATES = ['inline_query', 'callback_query']


def receive_update(api, update):
    if 'inline_query' in update:
        data = update.inline_query
        query = data.query
        counter = 0

        res = re.match('(.*): ?(-?\d+)', query, re.S | re.M)
        if res:
            query = res.group(1)
            counter = int(res.group(2))

        def create_answer(id, title, keyboard):
            return {
                'type': 'article',
                'id': id,
                'title': title,
                'description': '%s: %s' % (query, counter),
                'input_message_content': {
                    'message_text': '%s: *%s*' % (query, counter),
                    'parse_mode': 'markdown'
                },
                'reply_markup': {
                    'inline_keyboard': keyboard
                }
            }

        api.answerInlineQuery(
            inline_query_id=data['id'],
            results=[
                create_answer('basic', 'Add a counter', [
                    [
                        {'text': '+', 'callback_data': '%s: *%s*|@all' % (query, counter + 1)},
                        {'text': '-', 'callback_data': '%s: *%s*|@all' % (query, counter - 1)}
                    ]
                ]),
                create_answer('personal', 'Add a personal counter', [
                    [
                        {'text': '+', 'callback_data': '%s: *%s*|%s' % (query, counter + 1, data['from'].id)},
                        {'text': '-', 'callback_data': '%s: *%s*|%s' % (query, counter - 1, data['from'].id)}
                    ]
                ])
            ]
        )
    elif 'callback_query' in update:
        data = update.callback_query

        parts = data.data.rsplit('|')
        new_text = ''.join(parts[:-1])
        restrict = parts[-1]

        if restrict == '@all' or data['from'].id == int(restrict):
            res = re.match('(.*): \*(-?\d+)\*', new_text, re.S | re.M)
            if res:
                query = res.group(1)
                counter = int(res.group(2))

                api.editMessageText(
                    inline_message_id=data.inline_message_id,
                    text='%s: *%s*' % (query, counter),
                    parse_mode='markdown',
                    reply_markup={
                        'inline_keyboard': [
                            [
                                {'text': '+', 'callback_data': '%s: *%s*|%s' % (query, counter + 1, restrict)},
                                {'text': '-', 'callback_data': '%s: *%s*|%s' % (query, counter - 1, restrict)}
                            ]
                        ]
                    }
                )
        api.answerCallbackQuery(callback_query_id=data.id)


def main():
    parser = argparse.ArgumentParser(description='County the Bot.')
    subparsers = parser.add_subparsers(
        metavar='type{longpoll, webhook, set_webhook}', dest='type',
        help='Type of action. Longpoll - uses long polling, obviously. Webhook - uses webhook that was previously set '
             'by set_webhook. It is recommended to call the program with arguments \'TYPE -h\' for type-specific help.'
    )

    longpoll_parser = subparsers.add_parser('longpoll',
                                            description='This mode uses the Long Poll technique to receive updates.')
    longpoll_parser.add_argument('token', help='The token of given bot')

    def ranged_int(mn, mx):
        def checker(x):
            value = int(x)
            if value < mn:
                raise argparse.ArgumentTypeError('%s is less than %s!' % (value, mn))
            if value > mx:
                raise argparse.ArgumentTypeError('%s is more than %s!' % (value, mx))
            return value
        return checker

    longpoll_parser.add_argument('-t', '--timeout', type=ranged_int(0, 600), default=30,
                                 help='Timeout for the long polls in seconds. Integer in range [0, 600]. '
                                      'Defaults to 30')

    webhook_parser = subparsers.add_parser('webhook', description='This mode uses the webhook technique to receive the '
                                                                  'updates. Before usage, webhook must be set via '
                                                                  '\'set_webhook\' mode. It does not require bot token '
                                                                  'because is it stored in webhook link')

    webhook_parser.add_argument('port', metavar='port', type=ranged_int(0, 65535),
                                help='Port at which the bot will listen to requests.')

    set_webhook_parser = subparsers.add_parser('set_webhook', description='This mode is used to set the webhook url '
                                                                          'for the given bot.')
    set_webhook_parser.add_argument('token', help='Token of the bot that the webhook should be bound with.')
    set_webhook_parser.add_argument('url', help='URL of the webhook.')

    args = parser.parse_args()

    if args.type is None:
        parser.parse_args(['-h'])
    elif args.type == 'longpoll':
        launch_longpoll(args.token, args.timeout)
    elif args.type == 'set_webhook':
        set_webhook(args.token, args.url)
    elif args.type == 'webhook':
        launch_webhook(args.port)


def launch_longpoll(token, timeout):
    api = TelegramAPI(token)

    print('Started longpoll loop with timeout of %s seconds' % timeout)

    try:
        last = 0
        while True:
            res = api.getUpdates(offset=last + 1, allowed_updates=ALLOWED_UPDATES, timeout=timeout)
            if 'ok' in res and res.ok:
                for update in res.result:
                    receive_update(api, update)
                    last = update.update_id
    except KeyboardInterrupt:
        print('Ended longpoll loop...')


def set_webhook(token, url):
    with TelegramAPI(token) as api:
        api.setWebhook(url='%s/%s' % (url, token), allowed_updates=ALLOWED_UPDATES)


def launch_webhook(port):
    api = None

    class PostRequestHandler(BaseHTTPRequestHandler):

        def do_POST(self):
            nonlocal api
            self.send_response_only(HTTPStatus.OK)
            self.send_header('Server', FULL_NAME)
            self.send_header('Date', self.date_time_string())
            self.end_headers()

            if not api:
                api = TelegramAPI(self.path[1:])  # token is stored in Telegram webhook link for security

            data = json.loads(str(self.rfile.read(int(self.headers.get('Content-Length', 0))), encoding='utf-8'))

            receive_update(api, DynamicDictObject.wrap(data))

    server = HTTPServer(('', port), PostRequestHandler)
    print('Started webhook server listening for updates at port:', port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Closing webhook server...')
    server.server_close()
    if api:
        api.close_api()


def TelegramAPI(token):
    return JsonRequestAPI(FULL_NAME, 'https://api.telegram.org/bot{token}/{method}', token)


class JsonRequestAPI:
    """
    The simplest web-request API you could possibly make.
    (Well, it can be simpler but less flexible if you remove submethods)
    """

    def __init__(self, name, link_pattern, token, predef_args=None):
        self.link_pattern, self.token, self.predef_args = link_pattern, token, predef_args or {}
        self.session = requests.Session()
        self.session.headers['User-Agent'] = name
        self.session.headers['Accept'] = 'application/json'

    def send_request(self, method, **kwargs):
        kwargs.update(self.predef_args)
        link = self.link_pattern.format(token=self.token, method=method)
        return DynamicDictObject.wrap(self.session.post(link, json=kwargs).json())

    def close_api(self):
        self.session.close()

    class Submethod:

        def __init__(self, api, method):
            self.api, self.method = api, method

        def __call__(self, **kwargs):
            return self.api.send_request(self.method, **kwargs)

        def __getattr__(self, item):
            return JsonRequestAPI.Submethod(self.api, self.method + '.' + item)

    def __getattr__(self, item):
        return JsonRequestAPI.Submethod(self, item)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()


class DynamicDictObject:
    """A recursive view of dict/list structure with getattr's and such"""

    @staticmethod
    def wrap(obj):
        if not isinstance(obj, (dict, list)):
            return obj
        return DynamicDictObject(obj)

    def __init__(self, peer):
        self.__peer = peer

    def __getattr__(self, item):
        return DynamicDictObject.wrap(self.__peer.get(item))

    def __getitem__(self, item):
        return DynamicDictObject.wrap(self.__peer.get(item))

    def __contains__(self, item):
        if isinstance(self.__peer, dict):
            return item in self.__peer

    def __iter__(self):
        return map(DynamicDictObject.wrap, self.__peer.__iter__())

    def __repr__(self):
        return repr(self.__peer)


if __name__ == '__main__':
    main()
