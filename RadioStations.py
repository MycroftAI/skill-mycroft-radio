# Copyright 2021 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import requests

def sort_on_vpc(k):
    return k['votes_plus_clicks']

class RadioStations:
    def __init__(self):
        self.stations = []
        self.index = 0
        self.blacklist = [
                "icecast",
                ]
        self.media_verbs = ['play', 'listen', 'radio']
        self.search_limit = 1000
        self.last_search_terms = ''


    def find_mime_type(self, url: str) -> str:
        """Determine the mime type of a file at the given url.
        Args:
            url: remote url to check
        Returns:
            Mime type - defaults to 'audio/mpeg'
        """
        mime = 'audio/mpeg'
        response = requests.Session().head(url, allow_redirects=True)
        if 200 <= response.status_code < 300:
            mime = response.headers['content-type']
        return mime


    def clean_sentence(self, sentence):
        sa = sentence.split(" ")
        vrb = sa[0].lower()
        if vrb in self.media_verbs:
            sentence = sentence[len(vrb):]

        sentence = " " + sentence + " "
        sentence = sentence.replace(" the ","")
        sentence = sentence.replace(" music ","")
        sentence = sentence.replace(" station ","")
        sentence = sentence.replace(" channel ","")
        sentence = sentence.strip()
        return sentence


    def get_media_confidence(self, sentence):
        self.last_search_terms = self.clean_sentence(sentence)
        search_terms = sentence.replace(" ", "+")     # url encode it :-)
        stations = search(search_terms, self.search_limit)
        url = ''
        stream_uri = ''
        station_name = ''
        if len(stations) > 0:
            station_name = stations[0].get('name'.replace("\n"," "), "")
            url = stations[0].get('url_resolved','')
            stream_uri = url

        confidence = 0
        if url != '':
            confidence = 100

        return {'confidence':confidence, 'stream_uri':stream_uri, 'srch_terms':self.last_search_terms, 'station_name':station_name}


    def domain_is_unique(self, stream_uri, stations):
        return True


    def blacklisted(self, stream_uri):
        for bl in self.blacklist:
            if bl in stream_uri:
                return True
        return False


    def _search(self, srch_term, limit):
        uri = "https://nl1.api.radio-browser.info/json/stations/search?hidebroken=true&limit=%s&name=" % (limit,)
        query = srch_term.replace(" ", "+")
        uri += query
        res = requests.get(uri)
        if res:
            return res.json()

        return []


    def search(self, sentence, limit):
        unique_stations = {}
        self.last_search_terms = self.clean_sentence(sentence)
        stations = self._search(self.last_search_terms, limit)

        # whack dupes, favor .aac streams
        for station in stations:
            station_name = station.get('name', '')
            station_name = station_name.replace("\n"," ")
            stream_uri = station.get('url_resolved','')
            if stream_uri != '' and not self.blacklisted(stream_uri):
                if station_name in unique_stations:
                    if not unique_stations[station_name]['url_resolved'].endswith('.aac'):
                        unique_stations[station_name] = station
                else:
                    if self.domain_is_unique(stream_uri, stations):
                        unique_stations[station_name] = station

        res = []
        for station in unique_stations:
            votes_plus_clicks = 0
            votes_plus_clicks += int( unique_stations[station].get('votes', 0) )
            votes_plus_clicks += int( unique_stations[station].get('clickcount', 0) )
            unique_stations[station]['votes_plus_clicks'] = votes_plus_clicks

            res.append( unique_stations[station] )

        res.sort(key=sort_on_vpc, reverse=True)

        return res


    def get_stations(self, utterance):
        self.stations = self.search(utterance, self.search_limit)
        self.index = 0


    def get_station_count(self):
        return len(self.stations)


    def get_station_index(self):
        return self.index


    def get_current_station(self):
        if len(self.stations) > 0:
            return self.stations[self.index]
        return None


    def get_next_station(self):
        if self.index == len(self.stations):
            self.index = 0
        else:
            self.index += 1
        return self.get_current_station()


    def get_previous_station(self):
        if self.index == 0:
            self.index = len(self.stations) - 1
        else:
            self.index -= 1
        return self.get_current_station()




