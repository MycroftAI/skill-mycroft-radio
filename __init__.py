# Copyright 2018 Mycroft AI Inc.
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
# TODO 
#   play <station name> should find if provided
#   add to favorites and play favorite
import subprocess, requests, time
from typing import Tuple
from mycroft import intent_handler, AdaptIntent
from mycroft.audio import wait_while_speaking
from mycroft.messagebus import Message
from mycroft.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel
from .RadioStations import RadioStations

# Minimum confidence levels
CONF_EXACT_MATCH = 0.9
CONF_LIKELY_MATCH = 0.7
CONF_GENERIC_MATCH = 0.6

"""
MIA - RestartRadio.intent
"""

class RadioFreeMycroftSkill(CommonPlaySkill):
    """simple streaming radio skill"""
    def __init__(self):
        super().__init__(name="RfmSkill")
        self.rs = RadioStations()
        self.now_playing = None
        self.current_station = None
        self.station_name = 'RFM'
        self.img_pth = ''
        self.stream_uri = ''
        self.fg_color = 'white'
        self.bg_color = 'black'


    def initialize(self):
        time.sleep(1)
        self.platform = self.config_core["enclosure"].get("platform", "unknown")
        self.register_gui_handlers()


    def register_gui_handlers(self):
        """Register handlers for events to or from the GUI."""
        self.bus.on('mycroft.audio.service.pause', self.handle_audioservice_status_change)
        self.bus.on('mycroft.audio.service.resume', self.handle_audioservice_status_change)
        self.bus.on('mycroft.audio.queue_end', self.handle_media_finished)
        self.gui.register_handler('cps.gui.pause', self.handle_gui_status_change)
        self.gui.register_handler('cps.gui.play', self.handle_gui_status_change)
        self.gui.register_handler('cps.gui.restart', self.handle_gui_restart)


    def handle_audioservice_status_change(self, message):
        """Handle changes in playback status from the Audioservice.
        Eg when someone verbally asks to pause.
        """
        if not self.now_playing:
            return

        command = message.msg_type.split('.')[-1]
        if command == "resume":
            new_status = "Playing"
        elif command == "pause":
            new_status = "Paused"
        self.gui['status'] = new_status


    def handle_media_finished(self, _):
        """Handle media playback finishing."""
        self.log.warning("RadioMediaFinished! should never get here!")
        if self.now_playing:
            self.gui.release()
            self.now_playing = False


    def _show_gui_page(self, page):
        qml_page = f"{page}_scalable.qml"
        self.gui.show_page(qml_page, override_idle=True)


    def handle_gui_status_change(self, message):
        """Handle play and pause status changes from the GUI.
        This notifies the audioservice. The GUI state only changes once the
        audioservice emits the relevant messages to say the state has changed.
        """
        if not self.now_playing:
            return

        command = message.msg_type.split('.')[-1]
        if command == "play":
            self.log.info("Audio resumed by GUI.")
            self.bus.emit(Message('mycroft.audio.service.resume'))
        elif command == "pause":
            self.log.info("Audio paused by GUI.")
            self.bus.emit(Message('mycroft.audio.service.pause'))


    def handle_gui_restart(self, _):
        """Handle restart button press."""
        self.restart_playback(None)


    def update_radio_theme(self, status):
        self.gui['theme'] = dict(fgColor=self.fg_color, bgColor=self.bg_color)

        self.img_pth = "/opt/mycroft/skills/skill-rfm.mycroftai/ui/images/radio.jpg"
        if self.fg_color == 'white':
            self.img_pth = "/opt/mycroft/skills/skill-rfm.mycroftai/ui/images/radio4.jpg"

        channel_info = "%s/%s" % (self.rs.index, len(self.rs.stations))
        station_name = self.current_station.get('name','').replace("\n","")
        self.gui['media'] = {
                "image": self.img_pth,
                "artist": " NOW STREAMING: " + station_name,
                "track": 'Track',
                "album": self.rs.last_search_terms, 
                "skill": self.skill_id,
                "current_station_info": channel_info,
                "streaming": True
        }
        self.gui['status'] = status
        self._show_gui_page('AudioPlayer')


    def setup_for_play(self, utterance):
        self.rs.get_stations(utterance)
        self.current_station = self.rs.get_current_station()


    def handle_play_request(self):
        """play the current station if there is one"""
        if self.current_station is None:
            self.log.error("Can't find any matching stations for = %s" % (self.rs.last_search_terms,))
            self.speak("Can not find any %s stations" % (self.rs.last_search_terms,))
            return

        stream_uri = self.current_station.get('url_resolved', '')
        station_name = self.current_station.get('name','').replace('\n','')

        mime = self.rs.find_mime_type(stream_uri)

        self.CPS_play((stream_uri, mime))

        self.now_playing = 'Now Playing'
        self.update_radio_theme('Playing')

        # cast to str for json serialization
        self.CPS_send_status(
            image=self.img_pth,
            artist=station_name
        )

    ## Intents 
    @intent_handler("HelpRadio.intent")
    def handle_radio_help(self, _):
        with self.activity():
            self.speak("Mycroft radio allows you to stream music and other content from a variety of free sources.")
            self.speak("If you ask me to play a specific type of music, like play Jazz, or play rock, I work very well.")
            self.speak("Play artist works Oh Kay for some artists but radio stations are not really artist specific.")
            self.speak("Next station and next channel or previous station and previous channel will select a different channel or station.")
            self.speak("You can also say change radio to change the radio Theme.")
            self.speak("For the graphical you eye.")


    @intent_handler("ChangeRadio.intent")
    def handle_change_radio(self, _):
        """change ui theme"""
        with self.activity():
            self.log.error("change_radio request, now playing = %s" % (self.now_playing,))
            if self.fg_color == 'white':
                self.fg_color = 'black'
                self.bg_color = 'white'
            else:
                self.fg_color = 'white'
                self.bg_color = 'black'

            if self.now_playing:
                self.gui.release()
                self.update_radio_theme('Playing')


    # @intent_handler(AdaptIntent('').require('Show').require("Radio"))

    @intent_handler("ShowRadio.intent")
    def handle_show_radio(self, _):
        with self.activity():
            if self.now_playing is not None:
                self._show_gui_page("AudioPlayer")
            else:
                self.speak_dialog("no.radio.playing")


    @intent_handler("NextStation.intent")
    def handle_next_station(self, message):
        with self.activity():
            exit_flag = False
            ctr = 0
            while not exit_flag and ctr < self.rs.get_station_count():
                new_current_station = self.rs.get_next_station()
                self.current_station = new_current_station
                self.stream_uri = self.current_station.get('url_resolved','')
                self.station_name = self.current_station.get('name', '')
                self.station_name = self.station_name.replace("\n"," ")

                try:
                    self.handle_play_request()
                    exit_flag = True
                except:
                    self.log.error("Caught Exception")

                ctr += 1


    @intent_handler("PreviousStation.intent")
    def handle_previous_station(self, message):
        with self.activity():
            exit_flag = False
            ctr = 0
            while not exit_flag and ctr < self.rs.get_station_count():
                new_current_station = self.rs.get_previous_station()
                self.current_station = new_current_station
                self.stream_uri = self.current_station.get('url_resolved','')
                self.station_name = self.current_station.get('name', '')
                self.station_name = self.station_name.replace("\n"," ")

                try:
                    self.handle_play_request()
                    exit_flag = True
                except:
                    self.log.error("Caught Exception")

                ctr += 1


    @intent_handler("NextChannel.intent")
    def handle_next_channel(self, message):
        with self.activity():
            self.rs.get_next_channel()
            self.handle_next_station(message)


    @intent_handler("PreviousChannel.intent")
    def handle_previous_channel(self, message):
        with self.activity():
            self.rs.get_previous_channel()
            self.handle_previous_station(message)


    @intent_handler("ListenToRadio.intent")
    def handle_padacious_intent(self, message):
        with self.activity():
            self.log.error("LISTEN")
            if message.data:
                self.setup_for_play( message.data.get('utterance', '') )
                self.handle_play_request()


    def play_current(self):
        exit_flag = False
        ctr = 0
        while not exit_flag and ctr < self.rs.get_station_count():
            new_current_station = self.rs.get_next_station()
            self.current_station = new_current_station
            self.stream_uri = self.current_station.get('url_resolved','')
            self.station_name = self.current_station.get('name', '')
            self.station_name = self.station_name.replace("\n"," ")

            try:
                self.handle_play_request()
                exit_flag = True
            except:
                self.log.error("Caught Exception")

            ctr += 1

        if not exit_flag:
            self.log.error("of %s stations, none work!" % (self.rs.get_station_count(),))


    @intent_handler("PlayRadio.intent")
    def handle_play_intent(self, message):
        with self.activity():
            self.log.error("PLAY")
            if message.data:
                self.setup_for_play( message.data.get('utterance', '') )
                self.play_current()



    @intent_handler("TurnOnRadio.intent")
    def handle_turnon_intent(self, message):
        if self.current_station is None:
            self.setup_for_play( self.rs.get_next_channel() )
        self.play_current()


    @intent_handler("StopRadio.intent")
    def handle_stop_radio(self, _):
        with self.activity():
            self.log.error("STOP")
            self.stop()


    @intent_handler("TurnOffRadio.intent")
    def handle_turnoff_intent(self, message):
        self.handle_stop_radio(message)


    ## Common query stuff
    def CPS_match_query_phrase(self, phrase: str) -> Tuple[str, float, dict]:
        """Respond to Common Play Service query requests.
        Args:
            phrase: utterance request to parse
        Returns:
            Tuple(Name of station, confidence, Station information)
        """
        # Translate match confidence levels to CPSMatchLevels
        self.log.error("CPS Match Request")
        self.setup_for_play( phrase )

        match_level = 0.0
        if self.current_station:
            match_level = CPSMatchLevel.EXACT

        return self.station_name, match_level, {'name':self.station_name, 'uri':self.stream_uri}


    def CPS_start(self, _, data):
        """Handle request from Common Play System to start playback."""
        self.log.error("XXXXXX !!!!!!!!!!!!! CPS START data=%s" % (data,))
        self.handle_play_request()


    def stop(self) -> bool:
        """Respond to system stop commands."""
        if self.now_playing is None:
            return False
        self.now_playing = None
        self.CPS_send_status()
        self.gui.release()
        self.CPS_release_output_focus()
        return True


def create_skill():
    return RadioFreeMycroftSkill()

