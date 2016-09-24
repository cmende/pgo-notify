# Copyright 2016 Christoph Mende
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import csv
import json
import logging
import os
import telegram
import time
import yaml
from datetime import datetime
from geopy.distance import distance
from http.server import HTTPServer, BaseHTTPRequestHandler

bot = None
config = {}
log = None
pokemon = None

class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['content-length'])
        body = self.rfile.read(length)
        parse_json(body)
        self.send_response(200)
        self.end_headers()

def main():
    global log
    load_config()
    load_i18n()
    start_bot()
    start_httpd()

def load_config():
    global config, log

    dirname = os.path.dirname(__file__)
    config_path = '{}/config.yaml'.format(dirname)
    stream = open(config_path)
    config_yaml = yaml.load(stream)

    config['api_token'] = config_yaml['api_token']
    config['lang'] = config_yaml.get('lang', 'en')
    config['loglevel'] = config_yaml.get('loglevel', 'WARNING')
    config['max_distance'] = float(config_yaml.get('max_distance', '2.5'))
    config['server_address'] = config_yaml.get('server_address', 'localhost')
    config['server_port'] = int(config_yaml.get('server_port', '4000'))
    config['spots'] = config_yaml.get('spots', [])

    loglevel = getattr(logging, config['loglevel'].upper())
    log = logging.getLogger('pgo-notify')
    log.setLevel(loglevel)
    logfile_path = '{}/pgo-notify.log'.format(dirname)
    handler = logging.FileHandler(logfile_path, mode='w')
    formatter = logging.Formatter('%(asctime)s %(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.addFilter(logging.Filter('pgo-notify'))

def load_i18n():
    global pokemon
    dirname = os.path.dirname(os.path.realpath(__file__))
    i18nfile_path = '{}/i18n/pokemon.{}.json'.format(dirname, config['lang'])
    with open(i18nfile_path) as f:
        pokemon = json.load(f)

def start_bot():
    global bot, config
    bot = telegram.Bot(token=config['api_token'])

def start_httpd():
    server_address = (config['server_address'], config['server_port'])
    httpd = HTTPServer(server_address, RequestHandler)
    httpd.serve_forever()

def parse_json(body):
    message = json.loads(body.decode('utf-8'))
    if message['type'] == 'pokemon':
        check_encounter(message['message'])

def check_encounter(encounter):
    global config
    for spot in config['spots']:
        dist = distance((float(spot['latitude']),float(spot['longitude'])),
                (float(encounter['latitude']), float(encounter['longitude'])))
        if dist.km < config['max_distance']:
            log.debug('Encounter near %s', spot['name'])
            send_message(spot['chat_id'], encounter)

def send_message(chat_id, encounter):
    global bot
    pokemon_name = pokemon[str(encounter['pokemon_id'])]
    disappears_at = datetime.fromtimestamp(encounter['disappear_time'])
    text = "*{} found*\ndisappears at: {}".format(pokemon_name,
            disappears_at.strftime('%H:%M:%S'))
    if 'respawn_info' in encounter:
        text = "{}\n{}".format(text, encounter['respawn_info'])
    bot.sendMessage(chat_id=chat_id, text=text, parse_mode='Markdown')
    bot.sendLocation(chat_id=chat_id, latitude=encounter['latitude'],
            longitude=encounter['longitude'], disable_notification=True)

if __name__ == '__main__':
    main()
