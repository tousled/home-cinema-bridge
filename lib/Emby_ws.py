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
import time
from .Emby_http import EmbyHttp
from lib.playback_manager import PlaybackManager
from .Xnoppo import *

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
        threading.Thread.__init__(self)
        logging.info('Ws:Fin init\n')

    def thread_function_play(self, data, scripterx=False):
        print("Thread Play: starting")

        # --- INICIO BLOQUE ROBUSTO (Gestión de Errores LG/OPPO) ---
        try:
            # 1. Instanciamos el Manager con la configuración actual
            manager = PlaybackManager(self.ws_config)

            # 2. Espera Activa: No intentamos reproducir hasta que el OPPO tenga red
            # Esto soluciona el fallo cuando la TV LG envía la orden demasiado rápido
            is_online = manager.wait_for_oppo_network()

            if is_online:
                # 3. Despertar / Handshake HDMI
                # Enviamos tecla 'EJT' (Eject) o similar para asegurar que sale del reposo
                # Usamos sendremotekey importado de .Xnoppo
                if self.ws_config.get("DebugLevel", 0) > 0: print("Despertando OPPO...")
                sendremotekey("EJT", self.ws_config)
                time.sleep(2)  # Damos tiempo al OPPO para procesar el despertar
            else:
                print("ADVERTENCIA: OPPO no responde a la red. Intentando reproducción de todas formas...")

        except Exception as e:
            print(f"Error en el pre-chequeo de PlaybackManager: {e}")
            # No bloqueamos el flujo si falla el manager, intentamos reproducir igual
        # --- FIN BLOQUE ROBUSTO ---

        playto_file(self.EmbySession, data, scripterx)
        self.reload_config()
        print("Thread Play: finishing")

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
        command = data['PlayCommand']
        if command == 'PlayNow':
            #self.EmbySession.playnow(data)
            if self.EmbySession.playstate=="Loading" or self.EmbySession.playstate=="Replay":
                if self.ws_config["DebugLevel"]>0: print("Esta en la pantalla de Loading, tenemos que esperar")
                timeout=60
                time=0
                while self.EmbySession.playstate=="Loading" or time>timeout:
                    time.sleep(3)
                    time=time+3
            if self.EmbySession.playstate=="Playing":
                if self.ws_config["DebugLevel"]>0: print("ya se esta reproduciendo algo")
                playother(self.EmbySession,data,False)
            else:
                x = threading.Thread(target=self.thread_function_play, args=(data,))
                x.start()

    def _general_commands(self,data):
        cmd = data['Name']
        args = data['Arguments']
        #print(cmd)
        #print(args)
        if cmd == 'SetAudioStreamIndex':
            params = self.EmbySession.process_data(self.EmbySession.currentdata)
            audio_index = self.EmbySession.get_xnoppo_audio_index(params["ControllingUserId"],params["item_id"],int(args['Index']))
            setaudiotrack(self.ws_config,audio_index)
            self.EmbySession.currentdata["AudioStreamIndex"]=int(args['Index'])
        elif cmd == 'SetSubtitleStreamIndex':
            params = self.EmbySession.process_data(self.EmbySession.currentdata)
            subs_index = self.EmbySession.get_xnoppo_subs_index(params["ControllingUserId"],params["item_id"],int(args['Index']))
            set_subtitles_track(self.ws_config, subs_index)
            self.EmbySession.currentdata["SubtitleStreamIndex"]=int(args['Index'])
        #elif cmd == 'SetVolume'

    def _check_state(self, data, sessions):
        if self.ws_config["MonitoredDevice"]:
            item_data = None
            item_data_list = None

            if sessions:
                if self.ws_config.get("DebugLevel", 0) > 1:
                    print(f"Ws:Checking sessions for monitored device | sessions={len(data)}")

                for item in data:
                    if item["DeviceId"] == self.ws_config["MonitoredDevice"]:
                        item_data = item
                        try:
                            now_playing = item_data.get("NowPlayingItem")
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
                            break
                        except Exception as e:
                            if self.ws_config.get("DebugLevel", 0) > 0:
                                print(f"Ws:Could not load monitored item details: {e}")
                            break
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

                            try:
                                playstate = item_data["PlayState"]
                            except:
                                playstate = {}


                            requested_start_ticks = playstate.get("PositionTicks")
                            data2 = {
                                "ItemIds": [int(item_data["NowPlayingItem"]["Id"])],
                                "StartIndex": 0,
                                "MediaSourceId": playstate.get("MediaSourceId", ""),
                                "AudioStreamIndex": playstate.get(
                                    "AudioStreamIndex", 1
                                ),
                                "SubtitleStreamIndex": playstate.get(
                                    "SubtitleStreamIndex", -1
                                ),
                                "ControllingUserId": item_data["UserId"],
                                "SessionID": item_data["Id"],
                                "DeviceName": item_data["DeviceName"],
                                "Device_Id": self.ws_config["MonitoredDevice"],
                            }

                            if requested_start_ticks is not None:
                                data2["StartPositionTicks"] = requested_start_ticks
                            else:
                                data2["SavedPlaybackPositionTicks"] = userdata.get(
                                    "PlaybackPositionTicks", 0
                                )

                            if self.ws_config.get("DebugLevel", 0) > 0:
                                print(
                                    "Ws:Preparing playback handoff | "
                                    f"item_id={data2['ItemIds'][0]} | "
                                    f"device={data2['DeviceName']} | "
                                    f"start_ticks={data2['StartPositionTicks']} | "
                                    f"audio={data2['AudioStreamIndex']} | "
                                    f"subtitle={data2['SubtitleStreamIndex']}"
                                )

                            timeout = 60
                            elapsed = 0
                            while self.EmbySession.playstate == "Loading" or elapsed > timeout:
                                time.sleep(3)
                                elapsed = elapsed + 3

                            if self.EmbySession.playstate == "Playing" or self.EmbySession.playstate == "Replay":
                                if self.ws_config["DebugLevel"] > 0:
                                    print("ya se esta reproduciendo algo")
                                playother(self.EmbySession, data2, True)
                            else:
                                x = threading.Thread(
                                    target=self.thread_function_play,
                                    args=(data2, True)
                                )
                                x.start()

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
                    if self.ws_config["DebugLevel"] > 0:
                        print('Stopped Playing')
                    if self.ws_config["DebugLevel"] > 0 and item_data:
                        print(item_data.get("DeviceName"))
                    if self.ws_config["DebugLevel"] > 0:
                        print(self.MonitoredState)
                    self.MonitoredState = ''

    def _playstate(self, data):
        command = data['Command']
        if command == 'Stop':
            sendremotekey('STP',self.ws_config)
        elif command == 'Pause':
            sendremotekey('PAU',self.ws_config)
        elif command == 'Unpause':
            sendremotekey('PLA',self.ws_config)
        elif command == 'NextTrack':
            sendremotekey('NXT',self.ws_config)
        elif command == 'PreviousTrack':
            sendremotekey('PRE',self.ws_config)
        elif command == 'Seek':
            playticks=data["SeekPositionTicks"]
            setplaytime(self.ws_config,playticks)
        elif command == 'Rewind':
            sendremotekey('REV',self.ws_config)
        elif command == 'FastForward':
            sendremotekey('FWD',self.ws_config)
        elif command == 'PlayPause':
            sendremotekey('PAU',self.ws_config)

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