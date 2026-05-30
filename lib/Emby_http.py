import json
import threading
import logging

from home_cinema_bridge.media_servers.emby import EmbyClient


class EmbyHttp(threading.Thread):
    config=None
    user_info=None
    playstate="Free"
    playedtitle=None
    server=None
    folder=None
    filename=None
    currentdata=None
    lang=None
    def __init__(self,config):
        self.config=config
        threading.Thread.__init__(self)
        self.client = EmbyClient.from_config(config)
        self.user_info = self.authenticate()
        logging.info('EmbyHttp Iniciado')

    def authenticate(self):
        return self.client.authenticate()

    def process_data(self, data):
        startat = data.get("StartPositionTicks")

        if startat is None:
            startat = data.get("SavedPlaybackPositionTicks")

        if startat is None:
            startat = -1

        startat = int(startat)

        item_ids = data["ItemIds"]
        media_source_id = data.get("MediaSourceId", "")
        subtitle_stream_index = data.get("SubtitleStreamIndex", -1)
        audio_stream_index = data.get("AudioStreamIndex", 1)
        start_index = data.get("StartIndex", 0)

        if self.config["DebugLevel"] > 0:
            print(len(item_ids))

        if len(item_ids) > 0:
            item_ids = item_ids[0]

        if start_index > 0 and start_index < len(item_ids):
            item_ids = item_ids[start_index:]

        if startat < 0:
            iteminfo = self.get_item_info(data.get("ControllingUserId", ""), item_ids)
            startat = int(iteminfo.get("UserData", {}).get("PlaybackPositionTicks", 0))

        params = {}
        params["item_id"] = item_ids
        params["auto_resume"] = startat
        params["media_source_id"] = media_source_id
        params["subtitle_stream_index"] = subtitle_stream_index
        params["audio_stream_index"] = audio_stream_index
        params["ControllingUserId"] = data.get("ControllingUserId", "")
        params["Session_id"] = data.get("SessionID", None)
        params["play_session_id"] = data.get("PlaySessionId", "")
        params["DeviceName"] = data.get("DeviceName", "")
        params["Device_Id"] = data.get("Device_Id", "")

        if self.config.get("DebugLevel", 0) > 0:
            print(
                "EmbyHttp:playback params | "
                f"item_id={params.get('item_id')} | "
                f"auto_resume={params.get('auto_resume')} | "
                f"media_source_id={params.get('media_source_id')} | "
                f"audio={params.get('audio_stream_index')} | "
                f"subtitle={params.get('subtitle_stream_index')} | "
                f"device={params.get('DeviceName')}"
            )

        return params

    def playnow(self,data):

        params = self.process_data(data)
        session_info = self.user_info["SessionInfo"]
        message_data = {
                      "CanSeek": True,
                      "ItemId": params["item_id"],
                      "SessionId": session_info["Id"],
                      "MediaSourceId": params["media_source_id"],
                      "AudioStreamIndex": params["audio_stream_index"],
                      "SubtitleStreamIndex": params["subtitle_stream_index"],
                      "IsPaused": False,
                      "IsMuted": False,
                      "PositionTicks": params["auto_resume"],
                      "PlayMethod": "DirectPlay",
                      "PlaySessionId": params["play_session_id"],
                      "RepeatMode": "RepeatNone"
                        }
        response = self.client.notify_playback_started(message_data)
        logging.debug(
            "Emby playback started response | status=%s | body=%s",
            response.status_code,
            response.text,
        )
        if self.config["DebugLevel"]>0: print (response.text)

        return response

    def playingprogress(self,data,positionticks,totalticks,ispaused,ismuted):

        params = self.process_data(data)
        session_info = self.user_info["SessionInfo"]
        message_data = {
                      "CanSeek": True,
                      "ItemId": params["item_id"],
                      "SessionId": session_info["Id"],
                      "MediaSourceId": params["media_source_id"],
                      "AudioStreamIndex": params["audio_stream_index"],
                      "SubtitleStreamIndex": params["subtitle_stream_index"],
                      "IsPaused": ispaused,
                      "IsMuted": ismuted,
                      "PositionTicks": positionticks,
                      "RunTimeTicks": totalticks,
                      "PlayMethod": "DirectPlay",
                      "PlaySessionId": params["play_session_id"],
                      "RepeatMode": "RepeatNone",
                      "EventName": "TimeUpdate"
                        }
        response = self.client.report_playback_progress(message_data)
        if self.config["DebugLevel"]>0: print (response.text)

        return response

    def playingstopped(self,data,positionticks,ispaused,ismuted):

        params = self.process_data(data)
        session_info = self.user_info["SessionInfo"]
        message_data = {
                      "CanSeek": True,
                      "ItemId": params["item_id"],
                      "SessionId": session_info["Id"],
                      "MediaSourceId": params["media_source_id"],
                      "AudioStreamIndex": params["audio_stream_index"],
                      "SubtitleStreamIndex": params["subtitle_stream_index"],
                      "IsPaused": ispaused,
                      "IsMuted": ismuted,
                      "PositionTicks": positionticks,
                      "PlayMethod": "DirectPlay",
                      "PlaySessionId": params["play_session_id"],
                      "RepeatMode": "RepeatNone",
                        }
        response = self.client.notify_playback_stopped(message_data)
        if self.config["DebugLevel"]>0: print (response.text)

        return response
    
    def setitemplaybackposition(self,data,positionticks,played):

        params = self.process_data(data)
        user_id = params.get("ControllingUserId") or self.user_info["User"]["Id"]
        
        message_data = {
                    "played" : played,
                    "PlaybackPositionTicks" : positionticks
                        }
        logging.debug ('setitemplaybackposition data: %s',message_data)
        response = self.client.set_item_playback_position(
            user_id,
            params["item_id"],
            message_data,
        )
        logging.debug(
            'setitemplaybackposition respuesta: status=%s body=%s',
            response.status_code,
            response.text,
        )

        return response

    def playback_stop(self,session_id):

        message_data = {}
        message_data["Command"] = 'Stop'

        response = self.client.stop_session_playback(session_id, message_data)
        if self.config["DebugLevel"]>0: print (response.text)

        return response


    def get_headers(self,user_info=None):
        return self.client.get_headers(user_info)

    def send_message2(self,session_id, sms_txt, timeout=3500):
        response = self.client.send_session_message(session_id, sms_txt, timeout)
        if self.config["DebugLevel"]>0: print (response.text)

        return response

    def set_capabilities(self):
        message_data = {
                'IconUrl': "https://img.alicdn.com/imgextra/i1/1840220527/O1CN018lXYlv1FlPES6Bgcw_!!1840220527.png",
                'SupportsMediaControl': True,
                'PlayableMediaTypes': ["Video", "Audio"],
                'SupportedCommands': ["Play",
                                      "Playstate",
                                      "MoveUp",
                                      "MoveDown",
                                      "MoveLeft",
                                      "MoveRight",
                                      "Select",
                                      "Back",
                                      "ToggleContextMenu",
                                      "ToggleFullscreen",
                                      "ToggleOsdMenu",
                                      "GoHome",
                                      "PageUp",
                                      "NextLetter",
                                      "GoToSearch",
                                      "GoToSettings",
                                      "PageDown",
                                      "PreviousLetter",
                                      "TakeScreenshot",
                                      "VolumeUp",
                                      "VolumeDown",
                                      "ToggleMute",
                                      "SendString",
                                      "DisplayMessage",
                                      "SetAudioStreamIndex",
                                      "SetSubtitleStreamIndex",
                                      "SetRepeatMode",
                                      "Mute",
                                      "Unmute",
                                      "SetVolume",
                                      "PlayNext",
                                      "PlayMediaSource"],
                'DeviceProfile':{}
            }
        if self.config["DebugLevel"]>0: print(message_data)
        response = self.client.set_capabilities(message_data)
        if self.config["DebugLevel"]>0: print (response.text)

        return response

    def set_movie(self,session_id,item_id,item_type,item_name):

        response = self.client.set_session_viewing(
            session_id,
            item_type,
            item_id,
            item_name,
        )
        if self.config["DebugLevel"]>0: print (response.text)

        return response


    def get_ulr_data(self,url, config, user_info):

        if url.find("{server}") != -1:
            server = config["emby_server"]
            url = url.replace("{server}", server)

        if url.find("{userid}") != -1:
            user_id = user_info["User"]["Id"]
            url = url.replace("{userid}", user_id)

        #print (url)
        logging.debug(url)
        response_text = self.client.get_text(url)
        #print (response_text)
        return response_text


    def send_user_message(self,user_id,message,timeout=3500):
        url = ('{server}/emby/Sessions?ControllableByUserId=' + user_id)
        response_data = self.get_ulr_data(url, self.config, self.user_info)
        item_list = json.loads(response_data)
        logging.debug('Session_Info Response Data: %s',response_data)
        for item in item_list:
           item_data = {}
           item_data["Id"] = item["Id"]
           self.send_message2(item_data["Id"],message,timeout)
        return item_data


    def get_session_user_info(self,user_id,device_id):
            url = ('{server}/emby/Sessions?ControllableByUserId=' + str(user_id) + '&DeviceID=' + str(device_id))
            response_data = self.get_ulr_data(url, self.config, self.user_info)
            item_list = json.loads(response_data)
            logging.debug('Session_user_info Response Data: %s',response_data)
            item = {}
            for item in item_list:
               item_data = {}
               item_data["Id"] = item["Id"]
               item_data["Client"] = item["Client"]
               item_data["DeviceName"] = item["DeviceName"]
               logging.info("Session ID             : %s " % item_data["Id"])
               logging.info("Client                 : %s " % item_data["Client"])
               logging.info("DeviceName             : %s " % item_data["DeviceName"])
               try:
                   if item["NowPlayingItem"]:
                       item_data["NowPlayingItem"] = item["NowPlayingItem"]
                       logging.info("Path                   : %s " % item_data["NowPlayingItem"]["Path"])
                       logging.info("Name                   : %s " % item_data["NowPlayingItem"]["Name"])
               except:
                   pass
               logging.info("-----------------------------------------------------------\n")
            return item


    def get_item_path(self,user_id,item_id):
        url2 = ('{server}/emby/Users/' + str(user_id) + '/Items/' + str(item_id))
        response_data_item = self.get_ulr_data(url2, self.config, self.user_info)
        item_list_data = json.loads(response_data_item)
        logging.debug('Item List Data Path %s',item_list_data["Path"])
        return item_list_data["Path"]

    def get_item_info(self,user_id,item_id):
        url2 = ('{server}/emby/Users/' + str(user_id) + '/Items/' + str(item_id))
        response_data_item = self.get_ulr_data(url2, self.config, self.user_info)
        item_list_data = json.loads(response_data_item)
        logging.debug('Item List Data %s',item_list_data)
        return item_list_data

    def get_item_info2(self,user_id,item_id,mediasource_id):
        url2 = ('{server}/emby/Users/' + str(user_id) + '/Items/' + str(item_id))
        response_data_item = self.get_ulr_data(url2, self.config, self.user_info)
        item_list_data = json.loads(response_data_item)
        logging.debug('Item List Data %s',item_list_data)
        for mediasource in item_list_data["MediaSources"]:
            if mediasource["Id"]==mediasource_id:
                return(mediasource)
        return item_list_data
    
    def get_item_container(self,user_id,item_id):
        url2 = ('{server}/emby/Users/' + str(user_id) + '/Items/' + str(item_id))
        response_data_item = self.get_ulr_data(url2, self.config, self.user_info)
        item_list_data = json.loads(response_data_item)
        logging.debug('Item List Data Container %s',item_list_data["Container"])
        return item_list_data["Container"]

    def get_item_ascenstors(self,item_id):
        url2 = ('{server}/emby/Items/' + str(item_id) + '/Ancestors')
        response_data_item = self.get_ulr_data(url2, self.config, self.user_info)
        item_list_data = json.loads(response_data_item)
        logging.debug('Item List Data Container %s',item_list_data)
        return item_list_data
   
    def get_user_views(self,user_id):
        url2 = ('{server}/emby/Users/' + str(user_id) + '/Views?IncludeExternalContent=false')
        response_data_item = self.get_ulr_data(url2, self.config, self.user_info)
        item_list_data = json.loads(response_data_item)
        logging.debug('Item List Data User Views %s',item_list_data)
        return item_list_data["Items"]
    
    def get_view_items(self, view_id):
        url2 = ('{server}/emby/Items?parentId=' + str(view_id))
        response_data_item = self.get_ulr_data(url2, self.config, self.user_info)
        item_list_data = json.loads(response_data_item)
        return item_list_data["Items"]

    def get_view_items2(self,user_id,view_id,item_id):
        url2 = ('{server}/emby/Users/' + str(user_id) + '/Items?parentId=' + str(view_id) + '&item_id=' + str(item_id))
        response_data_item = self.get_ulr_data(url2, self.config, self.user_info)
        item_list_data = json.loads(response_data_item)
        return item_list_data["Items"]

    def get_info_from_device(self,device_id):
        url = ('{server}/emby/Sessions?DeviceId=' + device_id)
        response_data = self.get_ulr_data(url, self.config, self.user_info)
        item_list = json.loads(response_data)
        if self.config["DebugLevel"]>2:
            logging.debug('Response Data: %s',response_data)
        for item in item_list:
            item_data = {}
            item_data["Id"] = item["Id"]
            item_data["Client"] = item["Client"]
            item_data["DeviceName"] = item["DeviceName"]
            print (item_data["Id"])
            logging.info ("Session ID             : %s " % item_data["Id"])
            logging.info ("Client                 : %s " % item_data["Client"])
            logging.info ("DeviceName             : %s " % item_data["DeviceName"])
            logging.info ("-----------------------------------------------------------")
        return item

    def is_item_in_library(self,view_id,item_id):
        resultado=False
        item_list = self.get_view_items(view_id)
        for item in item_list:
            if item["Id"]==item_id:
                return True
        return resultado

    def is_item_in_library2(self, view_id, item_path):
        resultado=False
        media_folders = self.get_emby_selectable_folders()
        for folder in media_folders:
            if folder["Id"]==view_id:
                for subfolder in folder["SubFolders"]:
                    resultado=item_path.startswith(subfolder["Path"])
                    if resultado:
                        return resultado
        return resultado

    def get_emby_devices(self):
        url = ('{server}/emby/Devices?')
        response_data = self.get_ulr_data(url, self.config, self.user_info)
        item_list = json.loads(response_data)
        return(item_list)


    def get_emby_selectable_folders(self):
        url = ('{server}/emby/Library/SelectableMediaFolders?')
        response_data = self.get_ulr_data(url, self.config, self.user_info)
        item_list = json.loads(response_data)
        return(item_list)

    def get_xnoppo_audio_index(self,user_id,item_id,index):
        response = self.get_item_info(user_id,item_id)
        audio_index=0
        for media in response["MediaStreams"]:
            if media["Type"]=="Audio":
                audio_index=audio_index+1
                if media["Index"]==index:
                    return(audio_index)
        return 1

    def get_xnoppo_subs_index(self,user_id,item_id,index):
        if index < 0:
            return 0
        else:
            response = self.get_item_info(user_id,item_id)
            if self.config["DebugLevel"]==2:
                print(response["MediaStreams"])
            subs_index=0
            for media in response["MediaStreams"]:
                if media["Type"]=="Subtitle":
                    subs_index=subs_index+1
                    if media["Index"]==index:
                        return(subs_index)
            return 0
