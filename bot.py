
import tinybot
import re


class CountyBot(tinybot.Bot):

    version = '1.1.0'

    def handle_inline_query(self, data, api):
        query = data.query
        counter = 0

        res = re.match('(.*): ?(-?\d+)', query, re.S | re.M)
        if res:
            query = res.group(1)
            counter = int(res.group(2))

        def create_answer(answer_id, title, keyboard):
            return {
                'type': 'article',
                'id': answer_id,
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

    def handle_callback_query(self, data, api):
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


if __name__ == '__main__':
    tinybot.run(CountyBot, 'County the Bot.')
