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
import logging
import os
import telegram
import time
import yaml
from datetime import datetime
from geopy.distance import distance
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

bot = None
config = None
log = None
known_encounters = []
observer = None

class EventHandler(PatternMatchingEventHandler):
    def on_modified(self, event):
        parse_file(event.src_path)

def main():
    global log, observer
    load_config()
    start_bot()
    start_observer()
    log.info('Startup complete')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def load_config():
    global config, log

    dirname = os.path.dirname(__file__)
    config_path = '{}/config.yaml'.format(dirname)
    stream = open(config_path)
    config = yaml.load(stream)

    loglevel = getattr(logging, config['loglevel'].upper())
    log = logging.getLogger('pgo-notify')
    log.setLevel(loglevel)
    logfile_path = '{}/pgo-notify.log'.format(dirname)
    handler = logging.FileHandler(logfile_path, mode='w')
    formatter = logging.Formatter('%(asctime)s %(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.addFilter(logging.Filter('pgo-notify'))

def start_bot():
    global bot, config
    bot = telegram.Bot(token=config['api_token'])

def start_observer():
    global observer
    event_handler = EventHandler(patterns=['*.txt'],
            ignore_directories=True)
    observer = Observer()
    observer.schedule(event_handler, '.')
    observer.start()

def parse_file(src_path):
    global known_encounters, log
    log.debug('Spawns file changed')
    with open(src_path) as f:
        csvf = csv.DictReader(f, delimiter='\t')
        for row in csvf:
            if (float(row['Time']) + float(row['Time2Hidden']) > time.time() and
                    row['encounterID'] not in known_encounters):
                log.debug('New encounter: ', row['encounterID'])
                known_encounters.append(row['encounterID'])
                check_encounter(row)

def check_encounter(encounter):
    global config
    for spot in config['spots']:
        dist = distance((float(spot['latitude']),float(spot['longitude'])),
                (float(encounter['lat']), float(encounter['lng'])))
        if dist < float(config['max_distance']):
            log.debug('Encounter near ', spot['name'])
            send_message(spot['chat_id'], encounter)

def send_message(chat_id, encounter):
    global bot
    disappears_at = datetime.fromtimestamp(int(encounter['Time']) +
            int(encounter['Time2Hidden']))
    text = "*{} found*\ndisappears at: {}".format(encounter['Name'],
            disappears_at.strftime('%H:%M:%S'))
    bot.sendMessage(chat_id=chat_id, text=text, parse_mode='Markdown')
    bot.sendLocation(chat_id=chat_id, latitude=encounter['lat'],
            longitude=encounter['lng'], disable_notification=True)

if __name__ == '__main__':
    main()
