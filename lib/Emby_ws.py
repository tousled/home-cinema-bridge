#
# Thanks for websocket-client library.
#
# Copyright 2018 Hiroki Ohtani.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import threading
from websocket import WebSocketApp
import logging
import json
from .Emby_http import EmbyHttp
from home_cinema_bridge.media_servers.emby.playback_command_handler import (
    EmbyPlaybackCommandHandler,
)
from home_cinema_bridge.media_servers.emby.session_events import (
    build_playback_intent_from_session,
    describe_session_playback_source,
    find_monitored_session,
)
from home_cinema_bridge.playback.dispatch import (
    PlaybackIntentDispatcher,
    bridge_playback_is_active,
)
from home_cinema_bridge.playback.application import PlaybackApplicationService
from home_cinema_bridge.playback.intent import PlaybackOrigin


class XnoppoWs(threading.Thread):
    emby_state=''
    stop_websocket = False
    ws_config=None
    ws_user_info=None
    EmbySession=None
    MonitoredState=''
    config_file=''
    ws_lang=None
    wsock=None

    def stop(self):
        print('ws stop')
        self.stop_websocket=True;
        self.ws.close()
        exit
    def __init__(self):

        self.emby_state='Init'
        self.playback_application_service = None
        self.playback_command_handler = None
        threading.Thread.__init__(self)
        logging.info('Ws:Fin init\n')

    def set_lang(self,lang):
        self.ws_lang=lang
        self.EmbySession.lang=lang

    def reload_config(self):
        if self.ws_config["DebugLevel"]>0: print('Recargando Configuracion')
        with open(self.config_file, 'r') as f:
                config = json.load(f)
        f.close
        ## new options default config values
        default = config.get("Autoscript", False)
        config["Autoscript"]=default
        default = config.get("enable_all_libraries", False)
        config["enable_all_libraries"]=default
        default = config.get("TV_model", "")
        config["TV_model"]=default
        default = config.get("TV_SOURCES", [])
        config["TV_SOURCES"] = default
        default = config.get("AV_model", "")
        config["AV_model"]=default
        default = config.get("AV_SOURCES", [])
        config["AV_SOURCES"] = default
        default = config.get("AV_Port", 23)
        config["AV_Port"]=default
        default = config.get("TV_script_init", "")
        config["TV_script_init"]=default
        default = config.get("TV_script_end", "")
        config["TV_script_end"]=default
        default = config.get("av_delay_hdmi", 0)
        config["av_delay_hdmi"]=default
        default = config.get("language","es-ES")
        config["language"]=default
        default = config.get("default_nfs",False)
        config["default_nfs"]=default
        default = config.get("wait_nfs",False)
        config["wait_nfs"]=default
        default = config.get("refresh_time",5)
        config["refresh_time"]=default
        default = config.get("check_beta",False)
        config["check_beta"]=default
        default = config.get("smbtrick",False)
        config["smbtrick"]=default
        default = config.get("TV_MAC", "")
        config["TV_MAC"] = default

        ##
        self.ws_config=config
        self.EmbySession.config=config
        return(config)

    def _play(self, data):
        self.playback_command_handler.handle_play(data)

    def _general_commands(self,data):
        self.playback_command_handler.handle_general_command(data)

    def _check_state(self, data, sessions):
        if self.ws_config["MonitoredDevice"]:
            item_data = None
            item_data_list = None

            if sessions:
                if self.ws_config.get("DebugLevel", 0) > 1:
                    print(f"Ws:Checking sessions for monitored device | sessions={len(data)}")

                item_data = find_monitored_session(
                    data,
                    self.ws_config["MonitoredDevice"],
                )
                try:
                    now_playing = item_data.get("NowPlayingItem") if item_data else None
                    if now_playing:
                        item_data_list = self.EmbySession.get_item_info(
                            item_data["UserId"],
                            now_playing["Id"]
                        )

                        if self.ws_config.get("DebugLevel", 0) > 0:
                            print(
                                "Ws:Monitored item detected | "
                                f"device={item_data.get('DeviceName')} | "
                                f"title={now_playing.get('Name')} | "
                                f"type={now_playing.get('Type')} | "
                                f"container={now_playing.get('Container')}"
                            )
                except Exception as e:
                    if self.ws_config.get("DebugLevel", 0) > 0:
                        print(f"Ws:Could not load monitored item details: {e}")
            else:
                item_data = self.EmbySession.get_session_user_info(
                    data["UserId"],
                    self.ws_config["MonitoredDevice"]
                )

            try:
                if item_data["NowPlayingItem"]:
                    if self.MonitoredState == '':
                        if self.ws_config["DebugLevel"] > 0:
                            print(item_data["DeviceName"])
                        if self.ws_config["DebugLevel"] > 0:
                            print(item_data["NowPlayingItem"]["Name"])
                        if self.ws_config["DebugLevel"] > 0:
                            print(item_data["NowPlayingItem"]["Container"])

                        self.MonitoredState = item_data["NowPlayingItem"]["Name"]
                        itemtype = item_data["NowPlayingItem"]["Type"]
                        item_name = item_data["NowPlayingItem"]["Name"]

                        if itemtype == "Episode":
                            item_lib_id = item_data["NowPlayingItem"]["Path"]
                        elif itemtype == "Movie":
                            item_lib_id = item_data["NowPlayingItem"]["Path"]
                        else:
                            item_lib_id = item_data["NowPlayingItem"].get("Path", "")

                        views_list = self.ws_config["Libraries"]
                        LibraryName = ""
                        encontrado = False

                        if self.ws_config["enable_all_libraries"]:
                            LibraryName = "All Libraries Enabled"
                            encontrado = True
                        else:
                            for view in views_list:
                                view_data = {}
                                if view["Active"] == True:
                                    view_data["Name"] = view["Name"]
                                    view_data["Id"] = view["Id"]
                                    encontrado = self.EmbySession.is_item_in_library2(
                                        view["Id"],
                                        item_lib_id
                                    )
                                    if encontrado:
                                        LibraryName = view_data["Name"]
                                        break

                        if encontrado:
                            if self.ws_config["DebugLevel"] > 0:
                                print("LIBRARY NAME: " + LibraryName)

                            logging.debug(
                                'El item %s es de la libreria %s',
                                item_name,
                                LibraryName
                            )

                            if sessions:
                                userdata = item_data_list["UserData"]
                            else:
                                userdatalist = data["UserDataList"]
                                userdata = userdatalist[0]

                            playback_source = describe_session_playback_source(
                                item_data,
                                item_info=item_data_list,
                                item_user_data=userdata,
                            )
                            logging.info(
                                "Emby monitored playback source | "
                                "item_id=%s | name=%s | item_type=%s | "
                                "item_container=%s | item_video_type=%s | "
                                "media_source_id=%s | media_source_container=%s | "
                                "media_source_video_type=%s | "
                                "session_position_present=%s | "
                                "session_position_ticks=%s | "
                                "saved_position_ticks=%s | played=%s | "
                                "play_count=%s | played_percentage=%s | "
                                "audio_stream_index=%s | subtitle_stream_index=%s",
                                playback_source["item_id"],
                                playback_source["item_name"],
                                playback_source["item_type"],
                                playback_source["item_container"],
                                playback_source["item_video_type"],
                                playback_source["media_source_id"],
                                playback_source["media_source_container"],
                                playback_source["media_source_video_type"],
                                playback_source["session_position_ticks_present"],
                                playback_source["session_position_ticks"],
                                playback_source["saved_position_ticks"],
                                playback_source["played"],
                                playback_source["play_count"],
                                playback_source["playback_percentage"],
                                playback_source["audio_stream_index"],
                                playback_source["subtitle_stream_index"],
                            )
                            playback_intent = build_playback_intent_from_session(
                                item_data,
                                monitored_device_id=self.ws_config["MonitoredDevice"],
                                item_user_data=userdata,
                            )
                            if self.ws_config.get("DebugLevel", 0) > 0:
                                print(
                                    "Ws:Preparing playback handoff | "
                                    f"item_id={playback_intent.media_item_id} | "
                                    f"device={playback_intent.source_device_name} | "
                                    f"start_seconds={playback_intent.start_position_seconds} | "
                                    f"audio={playback_intent.selected_audio_track_id} | "
                                    f"subtitle={playback_intent.selected_subtitle_track_id}"
                                )

                            self._playback_intent_dispatcher().dispatch(
                                playback_intent,
                                origin=PlaybackOrigin.OBSERVED_TV_CLIENT,
                            )
                            return 0
                        else:
                            if self.ws_config["DebugLevel"] > 0:
                                print('El item no es de ninguna libreria activa: ' + item_name)
                            logging.debug(
                                'El item %s no es de ninguna libreria activa',
                                item_name
                            )

                    elif item_data["NowPlayingItem"]["Name"] == self.MonitoredState:
                        if self.ws_config["DebugLevel"] > 0:
                            print('Continue Playing')
                        if self.ws_config["DebugLevel"] > 0:
                            print(item_data["DeviceName"])
                        if self.ws_config["DebugLevel"] > 0:
                            print(self.MonitoredState)
                        if self.ws_config["DebugLevel"] > 0:
                            print(item_data["NowPlayingItem"]["Name"])

                    else:
                        if self.ws_config["DebugLevel"] > 0:
                            print('Change Playing')
                        if self.ws_config["DebugLevel"] > 0:
                            print(item_data["DeviceName"])
                        if self.ws_config["DebugLevel"] > 0:
                            print(self.MonitoredState)
                        if self.ws_config["DebugLevel"] > 0:
                            print(item_data["NowPlayingItem"]["Name"])

            except:
                if self.MonitoredState != '':
                    if bridge_playback_is_active(self.EmbySession.playstate):
                        logging.info(
                            "Keeping monitored state during bridge playback | "
                            "monitored_state=%s | playstate=%s",
                            self.MonitoredState,
                            self.EmbySession.playstate,
                        )
                        return 0

                    if self.ws_config["DebugLevel"] > 0:
                        print('Stopped Playing')
                    if self.ws_config["DebugLevel"] > 0 and item_data:
                        print(item_data.get("DeviceName"))
                    if self.ws_config["DebugLevel"] > 0:
                        print(self.MonitoredState)
                    self.MonitoredState = ''

    def _playback_intent_dispatcher(self):
        return PlaybackIntentDispatcher(
            playback_application_service=self.playback_application_service,
        )

    def _playstate(self, data):
        self.playback_command_handler.handle_playstate(data)

    def on_message(self, ws, msg):
        msg_json = json.loads(msg)
        msg_type = msg_json.get("MessageType")
        data = msg_json.get('Data')

        if self.ws_config.get("DebugLevel", 0) > 0:
            if msg_type == "Sessions" and isinstance(data, list):
                print(f"Ws:Message Arrived: Sessions | playstate={self.EmbySession.playstate} | sessions={len(data)}")
            else:
                print(f"Ws:Message Arrived: {msg_type} | playstate={self.EmbySession.playstate}")

        logging.debug("Ws:Message Arrived: %s", msg_type)
        self.emby_state = "Message Arrived:" + str(msg_type)

        if msg_type == 'Play':
            self._play(data)

        elif msg_type == 'Playstate':
            self._playstate(data)

        elif msg_type == "UserDataChanged":
            pass
            # self._check_state(data, False)

        elif msg_type == "LibraryChanged":
            pass
            # self._library_changed(data)

        elif msg_type == "GeneralCommand":
            self._general_commands(data)

        elif msg_type == "Sessions":
            self._check_state(data, True)

        else:
            logging.debug("WebSocket Message Type: %s", msg_type)

    def on_error(self, ws, error):
        if self.ws_config["DebugLevel"] > 0: print(error)
        self.emby_state = 'Ws::Error'

    def on_close(self, ws, close_status_code=None, close_msg=None):
        if self.ws_config["DebugLevel"] > 0: print("Ws:Connection Closed")
        self.emby_state = 'Closed'

    def on_open(self, ws):
        if self.ws_config["DebugLevel"] > 0: print('Ws:Open')
        self.emby_state = 'Opened'
        self.wsock.send('{"MessageType":"SessionsStart", "Data": "0,1500"}')

    def run(self):
        self.EmbySession=EmbyHttp(self.ws_config)
        self.EmbySession.lang=self.ws_lang
        self.ws_user_info = self.EmbySession.user_info
        self.EmbySession.set_capabilities()
        self.playback_application_service = PlaybackApplicationService(
            playback_session=self.EmbySession,
            reload_config=self.reload_config,
        )
        self.playback_command_handler = EmbyPlaybackCommandHandler(
            emby_session=self.EmbySession,
            config_provider=lambda: self.ws_config,
            playback_intent_dispatcher_factory=self._playback_intent_dispatcher,
        )
        uri = self.ws_config["emby_server"].replace('http://', 'ws://').replace('https://', 'wss://')
        uri = uri + '/?api_key=' + self.ws_user_info["AccessToken"] + '&deviceId=''Xnoppo'''
        #uri = uri + '/?api_key=' + self.ws_user_info["AccessToken"] + '&deviceId={}'
        if self.ws_config.get("DebugLevel", 0) > 0:
            safe_uri = uri.replace(self.ws_user_info["AccessToken"], "***")
            print(safe_uri)
        self.wsock = WebSocketApp(uri,
                                    on_open=self.on_open,
                                    on_message=self.on_message,
                                    on_error=self.on_error,
                                    on_close=self.on_close)
        if self.ws_config["DebugLevel"]>0: print('Ws:Fin open ws\n')
        self.emby_state='Run'
        while not self.stop_websocket:
            self.wsock.run_forever(ping_interval=10)
            if self.ws_config["DebugLevel"] > 0: print("after run forever")
            if self.stop_websocket:
                break
            self.emby_state='On run_forever'

        if self.ws_config["DebugLevel"]>0: print("WebSocketClient Stopped")
