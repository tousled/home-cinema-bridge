from http.server import BaseHTTPRequestHandler, HTTPServer
from lib.config_manager import ensure_config_exists, is_configured
import requests
from lib.Emby_ws import XnoppoWs
from lib.Xnoppo import *
from lib.Xnoppo_TV import *
import shutil
import threading
import logging
import logging.handlers
import psutil
import sys

def get_version():
    return("2.03")

def thread_function(ws_object):
    print("Thread: starting")
    ws_object.start()
    print("Thread: finishing")


def watchdog_function(ws_object, config):
    """
    Vigila que el estado del script no se quede huérfano.
    Comprueba 2 cosas:
    1. Que el OPPO no se haya apagado a lo bruto.
    2. Que no se quede atascado en "Iniciando" si la app de Emby se cuelga.
    """
    tiempo_atascado = 0  # Contador de segundos

    while True:
        time.sleep(5)  # Revisamos la salud cada 5 segundos
        try:
            if hasattr(ws_object, 'EmbySession') and hasattr(ws_object.EmbySession, 'playstate'):
                estado_actual = ws_object.EmbySession.playstate

                # Caso 1: El OPPO se ha apagado físicamente/desconectado de la red
                if check_socket(config) != 0:
                    if estado_actual not in ["Free", "Not_Connected", "Stopped"]:
                        logging.warning(
                            f"Watchdog: OPPO apagado o inalcanzable. Reseteando estado desde '{estado_actual}' a Libre.")
                        ws_object.EmbySession.playstate = "Free"
                        ws_object.EmbySession.playedtitle = ""
                        ws_object.EmbySession.filename = ""
                        tiempo_atascado = 0
                    continue  # Saltamos a la siguiente comprobación en 5 seg

                # Caso 2: El OPPO está encendido, pero la app de la TV se colgó y no manda estado
                # Asumimos que los estados de transición se llaman "Iniciando" o "Starting"
                if estado_actual in ["Iniciando", "Starting"]:
                    tiempo_atascado += 5

                    # Leemos el timeout de tu config (o usamos 60s por defecto)
                    max_timeout = config.get("timeout_oppo_playitem", 60)

                    if tiempo_atascado > max_timeout:
                        logging.warning(
                            f"Watchdog: Atascado en 'Iniciando' más de {max_timeout}s. App colgada. Reseteando a Libre.")
                        ws_object.EmbySession.playstate = "Free"
                        ws_object.EmbySession.playedtitle = ""
                        ws_object.EmbySession.filename = ""
                        tiempo_atascado = 0
                else:
                    # Si está "Reproduciendo" (Playing) o "Libre", reseteamos el cronómetro
                    tiempo_atascado = 0

        except Exception as e:
            # Silenciamos errores para no saturar el log si las variables aún no existen
            pass

def restart():
        print('restart')
        try:
            emby_wsocket.stop()
        except:
            pass
        print('fin restart')
        os._exit(0)

def save_config(config_file, config):
    with open(config_file, 'w') as fw:
        json.dump(config, fw, indent=4)
    fw.close
    try:
        emby_wsocket.ws_config=config
        emby_wsocket.EmbySession.config=config
    except:
        emby_wsocket.ws_config=config
def get_state():
        status={}
        status["Version"]=get_version()
        try:
            status["Playstate"]=emby_wsocket.EmbySession.playstate
            status["playedtitle"]=emby_wsocket.EmbySession.playedtitle
            status["server"]=emby_wsocket.EmbySession.server
            status["folder"]=emby_wsocket.EmbySession.folder
            status["filename"]=emby_wsocket.EmbySession.filename
            status["CurrentData"]=emby_wsocket.EmbySession.currentdata
            # gives a single float value
        except:
            status["Playstate"]="Not_Connected"
            status["playedtitle"]=""
            status["server"]=""
            status["folder"]=""
            status["filename"]=""
            status["CurrentData"]=""
        status["cpu_perc"]=psutil.cpu_percent()
        status["mem_perc"]=psutil.virtual_memory().percent
        
        # you can have the percentage of used RAM
        print(psutil.virtual_memory().percent)


        print(status)
        return(status)

def load_config(config_file,tv_path,av_path,lang_path):

        with open(config_file, 'r') as f:    
                config = json.load(f)
                #ver_configuracion(config)
        f.close
        ## new options default config values
        config["Version"]=get_version()
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
        default = config.get("TV_script_init", "")
        config["TV_script_init"]=default
        default = config.get("TV_script_end", "")
        config["TV_script_end"]=default
        default = config.get("av_delay_hdmi", 0)
        config["av_delay_hdmi"]=default
        default = config.get("AV_Port", 23)
        config["AV_Port"]=default
        default = config.get("timeout_oppo_mount", 60)
        config["timeout_oppo_mount"]=default
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
        default = config.get("BRDisc",False)
        config["BRDisc"]=default

        ## testeado de rutas
        edit_server=0
        server_list = config["servers"]
        for server in server_list:
            default = server.get("Test_OK", False)
            server_list[edit_server]["Test_OK"]=default
            edit_server=edit_server+1
        ## Cambio de booleans de texto antiguos a boleans actuales.
        if config["TV"]=='True':
            config["TV"]=True;
        if config["TV"]=='False':
            config["TV"]=False;
        if config["AV"]=='True':
            config["AV"]=True;
        if config["AV"]=='False':
            config["AV"]=False;
        config["servers"]=server_list
        config["tv_dirs"]=get_dir_folders(tv_path);
        config["av_dirs"]=get_dir_folders(av_path);
        config["langs"]=get_dir_folders(lang_path);

        return(config)

def check_version(config):

    url = "https://raw.githubusercontent.com/siberian-git/Xnoppo/main/versions/version.js"
    headers = {}
    response = requests.get(url, headers=headers)
    version = json.loads(response.text)
    print(version)
    print(config["check_beta"])
    if config["check_beta"]==True:
        last_version=version["beta_version"]
        last_version_file=version["beta_version_file"]
    else:
        last_version=version["curr_version"]
        last_version_file=version["curr_version_file"]
    xno_version=get_version()
    resp = {}
    resp["version"]=last_version
    resp["file"]=last_version_file
    print(xno_version)
    print(last_version)
    if xno_version<last_version:
        resp["new_version"]=True
    else:
        resp["new_version"]=False
    print(resp)
    return(resp)

def update_version(config,vers_path,cwd):

    url = "https://raw.githubusercontent.com/siberian-git/Xnoppo/main/versions/version.js"
    headers = {}
    response = requests.get(url, headers=headers)
    version = json.loads(response.text)
    print(version)
    if config["check_beta"]==True:
        last_version=version["beta_version"]
        last_version_file=version["beta_version_file"]
    else:
        last_version=version["curr_version"]
        last_version_file=version["curr_version_file"]
    url2 = "https://github.com/siberian-git/Xnoppo/raw/main/versions/" +  last_version_file
    headers = {}
    response2 = requests.get(url2, headers=headers)
    filename=vers_path + last_version_file
    with open(filename, 'wb') as f:
        f.write(response2.content)
        f.close()
    shutil.unpack_archive(filename, cwd)
    if sys.platform.startswith('win'):
       separador="\\"
    else:
       separador="/"
    tv_path = cwd + separador + 'web' + separador + 'libraries' + separador + 'TV' + separador
    av_path = cwd + separador + 'web' + separador + 'libraries' + separador + 'AV' + separador
    if config["TV"]==True and config["TV_model"]!="":
       move_files(tv_path + config["TV_model"],lib_path)
    if config["AV"]==True and config["AV_model"]!="":
       move_files(av_path + config["AV_model"],lib_path)
    resp = {}
    resp["version"]=last_version
    resp["file"]=last_version_file
    resp["new_version"]=False
    return(resp)

def cargar_lang(config_file):

        with open(config_file.encode(sys.getfilesystemencoding()), 'r',encoding='latin-1') as f:    
                config = json.load(f)
                #ver_configuracion(config)
        f.close
        ## new options default config values
        return(config)

def leer_file(web_file):

        with open(web_file, 'r',encoding='utf8') as f:
            num=f.read()
        f.close
        return(num)

def leer_img(web_file):

        with open(web_file, 'rb') as f:
            num=f.read()
        f.close
        return(num)


def test_path(config,server):
  
  rutas = get_mount_path(server["Emby_Path"] + "/test.mkv",server)
  result2 = test_mount_path(config,rutas["Servidor"],rutas["Carpeta"])
  return(result2)

def get_mount_path(movie,server_data):

        movie = movie.replace(server_data["Emby_Path"],server_data["Oppo_Path"])
        movie = movie.replace('\\\\','\\')
        movie = movie.replace('\\','/')
        word = '/'
        inicio = movie.find(word)
        inicio = inicio +1 
        final = movie.find(word,inicio,len(movie))
        servidor = movie[inicio:final]
        ultimo=final+1
        result=final+1
        while result > 0:
            ultimo=result+1
            result=movie.find(word,ultimo,len(movie))
        fichero=movie[ultimo:len(movie)]
        final=final+1
        ultimo=ultimo-1
        carpeta=movie[final:ultimo]
        resultado={}
        resultado["Servidor"]=servidor
        resultado["Carpeta"]=carpeta
        resultado["Fichero"]=fichero
        return(resultado)

def test_mount_path(config,servidor,carpeta):
    sendnotifyremote(config["Oppo_IP"])
    #print("Conectando con el OPPO")
    result=check_socket(config)
    if result==0:
        response_data6a = getmainfirmwareversion(config)
        response_data6c = getdevicelist(config)
        response_data6b = getsetupmenu(config)
        response_data6c = OppoSignin(config)
        response_data6d = getdevicelist(config)
        response_data6e = getglobalinfo(config)
        response_data6f = getdevicelist(config)
        response_data_on = sendremotekey("EJT",config)
        time.sleep(1)
        #print("Solicitando montar ruta al OPPO")
        response_data6b = getsetupmenu(config)
        while response_data6f.find('devicelist":[]') > 0:
              time.sleep(1)
              response_data6f = getdevicelist(config)
              response_data_on = sendremotekey("QPW",config)
        device_list=json.loads(response_data6f)
        if config["DebugLevel"]>0: print(device_list)
        nfs=config["default_nfs"]
        for device in device_list["devicelist"]:
            if device["name"].upper()==servidor.upper():
                if device["sub_type"]=="nfs":
                    nfs=True
                    break
                else:
                    nfs=False
                    break
        if nfs:
            response_login = LoginNFS(config,servidor)
        else:
            response_login = LoginSambaWithOutID(config,servidor)
        if config["Always_ON"]==False:
            time.sleep(5)
        response_data6b = getsetupmenu(config)
        if nfs:
            response_mount = mountSharedNFSFolder(servidor,carpeta,'','',config)
        else:
            response_mount = mountSharedFolder(servidor,carpeta,'','',config)
        response=json.loads(response_mount)
        #print(response)
        if config["Autoscript"]==True:
            result=umountSharedFolder(config)
        if response["success"]==True:
            a = "OK"
        else:
            a = "FAILURE"           
        return(a)
    else:
        print("No se puede conectar, revisa las configuraciones o que el OPPO este encendido o en reposo")

def test_emby(config):
    try:
        EmbySession=EmbyHttp(config)
        user_info = EmbySession.user_info
        if user_info["SessionInfo"]["Id"]!="":
            return("OK")
        else:
            return("FAILED")
    except:
            return("FAILED")

def test_oppo(config):
    result=check_socket(config)
    if result==0:
            return("OK")
    else:
            return("FAILED")

def carga_libraries(config):
    try:
        EmbySession=EmbyHttp(config)
        views_list=EmbySession.get_user_views(EmbySession.user_info["User"]["Id"])
        libraries = []
        for view in views_list:
            library= {}
            library["Name"]=view["Name"]
            library["Id"]=view["Id"]
            library["Active"]=False
            try:
                lib_list=config["Libraries"]
            except:
                lib_list={}
            for lib in lib_list:
                if lib["Id"]==view["Id"]:
                     library["Active"]=lib["Active"]
            libraries.append(library)
        config["Libraries"]=libraries
        return(0)
    except:
        return(1)
def is_library_active(config,libraryname):
    for library in config["Libraries"]:
        if library["Name"]==libraryname:
            return(library["Active"])
    return(False)

def get_selectableFolders(config):
        EmbySession=EmbyHttp(config)
        MediaFolders = EmbySession.get_emby_selectablefolders()
        servers=[]
        for Folder in MediaFolders:
            index=1
            active=is_library_active(config,Folder["Name"])
            if config["enable_all_libraries"]==True:
                active=True;
            if active==True:
                for SubFolder in Folder["SubFolders"]:    
                    server={}
                    server["Id"]=SubFolder["Id"]
                    if index>1:
                        server["name"]=Folder["Name"]+"("+str(index)+")"
                    else:
                        server["name"]=Folder["Name"]
                    server["Emby_Path"]=SubFolder["Path"]
                    server["Oppo_Path"]="/"
                    try:
                        serv_list=config["servers"]
                    except:
                        serv_list={}
                    for serv in serv_list:
                        if server["Emby_Path"]==serv["Emby_Path"]:
                             server["name"]=serv["name"];
                             server["Oppo_Path"]=serv["Oppo_Path"];
                             server["Test_OK"]=serv["Test_OK"];
                    servers.append(server)
                    index=index+1
        config["servers"]=servers

def get_dir_folders(directory):
    os.chdir(directory)
    dirs = os.listdir(".")
    encontrado=False
    list_dir=[]
    #a =""
    #list_dir.append(a)
    for x in dirs:
      if os.path.isdir(x):
         list_dir.append(x)
    return(list_dir)

def move_files(src, dest):
    os.chdir(src)
    src_files = os.listdir('.')
    for file_name in src_files:
        full_file_name = os.path.join(src, file_name)
        if os.path.isfile(full_file_name):
            shutil.copy(full_file_name, dest)
    return(0)

def get_devices(config):
    try:
        EmbySession=EmbyHttp(config)
        devices = EmbySession.get_emby_devices()
        index=0
        dev_temp = []
        for device in devices["Items"]:
                try:
                    if device["ReportedDeviceId"]!='Xnoppo':
                        device["Name"]=device["Name"] + " / " + device["AppName"]
                        device["Id"]=device["ReportedDeviceId"]
                        dev_temp.append(device)
                except:
                    pass
        config["devices"]=dev_temp
        return('OK')
    except:
        return('FAILURE')

class MyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        cwd = os.path.dirname(os.path.abspath(__file__))
        if sys.platform.startswith('win'):
              separador="\\"
        else:
              separador="/"
        resource_path=cwd + separador + 'web' + separador + 'resources' + separador
        html_path = cwd + separador + 'web' + separador
        tv_path = cwd + separador + 'web' + separador + 'libraries' + separador + 'TV' + separador
        av_path = cwd + separador + 'web' + separador + 'libraries' + separador + 'AV' + separador
        lang_path = cwd + separador + 'web' + separador + 'lang' + separador
        vers_path = cwd + separador + 'versions' + separador
        
        print(self.path)
        if self.path == '/emby_conf.html':
            i = leer_file(html_path + 'emby_conf.html')
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes(i,"utf-8"))
            return(0)
        if self.path == '/oppo_conf.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            i = leer_file(html_path + 'oppo_conf.html')
            self.wfile.write(bytes(i,"utf-8"))
            return(0)
        if self.path == '/lib_conf.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            i = leer_file(html_path + 'lib_conf.html')
            self.wfile.write(bytes(i,"utf-8"))
            return(0)
        if self.path == '/path_conf.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            i = leer_file(html_path + 'path_conf.html')
            self.wfile.write(bytes(i,"utf-8"))
            return(0)
        if self.path == '/tv_conf.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            i = leer_file(html_path + 'tv_conf.html')
            self.wfile.write(bytes(i,"utf-8"))
            return(0)
        if self.path == '/av_conf.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            i = leer_file(html_path + 'av_conf.html')
            self.wfile.write(bytes(i,"utf-8"))
            return(0)
        if self.path == '/other_conf.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            i = leer_file(html_path + 'other_conf.html')
            self.wfile.write(bytes(i,"utf-8"))
            return(0)
        if self.path == '/status.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            i = leer_file(html_path + 'status.html')
            self.wfile.write(bytes(i,"utf-8"))
            return(0)
        if self.path == '/help.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            i = leer_file(html_path + 'help.html')
            self.wfile.write(bytes(i,"utf-8"))
            return(0)
        if self.path == '/remote.html':
            i = leer_file(html_path + 'remote.html')
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes(i,"utf-8"))
            return(0)
        if self.path == '/android-chrome-36x36.png':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            i = leer_img(resource_path + 'android-chrome-36x36.png')
            self.wfile.write(bytes(i))
            return(0)
        if self.path == '/av-receiver-icon-2.jpg':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            i = leer_img(resource_path + 'av-receiver-icon-2.jpg')
            self.wfile.write(bytes(i))
            return(0)
        if self.path == '/dragon.png':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            i = leer_img(resource_path + 'dragon.png')
            self.wfile.write(bytes(i))
            return(0)
        if self.path == '/xnoppo_config':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            a = load_config(config_file, tv_path, av_path, lang_path)
            self.wfile.write(bytes(json.dumps(a),"utf-8"))  
            return(0)
        if self.path == '/xnoppo_config_lib':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            a = load_config(config_file, tv_path, av_path, lang_path)
            carga_libraries(a)
            self.wfile.write(bytes(json.dumps(a),"utf-8"))
            return(0)
        if self.path == '/xnoppo_config_dev':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            a = load_config(config_file, tv_path, av_path, lang_path)
            get_devices(a)
            self.wfile.write(bytes(json.dumps(a),"utf-8"))
            return(0)
        if self.path == '/check_version':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            config = load_config(config_file, tv_path, av_path, lang_path)
            a = check_version(config)
            self.wfile.write(bytes(json.dumps(a),"utf-8"))
            return(0)
        if self.path == '/update_version':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            config = load_config(config_file, tv_path, av_path, lang_path)
            a = update_version(config,vers_path,cwd)
            restart()
            self.wfile.write(bytes(json.dumps(a),"utf-8"))
            return(0)
        if self.path == '/get_state':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            a = get_state()
            self.wfile.write(bytes(json.dumps(a),"utf-8"))
            return(0)
        if self.path == '/restart':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            a = "Restarting"
            self.wfile.write(bytes(a,"utf-8"))
            restart()
        if self.path == '/refresh_paths':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            a = load_config(config_file, tv_path, av_path, lang_path)
            get_selectableFolders(a)
            self.wfile.write(bytes(json.dumps(a),"utf-8"))
            return(0)
        if self.path == '/lang':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            config = load_config(config_file, tv_path, av_path, lang_path)
            a = cargar_lang(lang_path + config["language"] + separador +'lang.js')
            self.wfile.write(bytes(json.dumps(a),"utf-8"))  
            return(0)
        if self.path.find("/send_key?")>=0:
            get_data = self.path
            print(get_data)
            a = len('/send_key?sendkey=')
            b=get_data[a:len(get_data)]
            print(b)
            config = load_config(config_file, tv_path, av_path, lang_path)
            sendnotifyremote(config["Oppo_IP"])
            result=check_socket(config)
            if b=='PON':
                if result==0:
                    response_data6a = getmainfirmwareversion(config)
                    response_data6c = getdevicelist(config)
                    response_data6b = getsetupmenu(config)
                    response_data6c = OppoSignin(config)
                    response_data6d = getdevicelist(config)
                    response_data6e = getglobalinfo(config)
                    response_data6f = getdevicelist(config)
                    response_data_on = sendremotekey("EJT",config)
                    if config["BRDisc"]==True:
                        time.sleep(1)
                        response_data_on = sendremotekey("EJT",config)
                    time.sleep(1)
                    response_data6b = getsetupmenu(config)
            else:
                response_data_on = sendremotekey(b,config)
            self.send_response(200)
            self.send_header("Content-type", "text")
            self.end_headers()
            a = "ok"
            self.wfile.write(bytes(a,"utf-8"))  
            return(0)
        if self.path == '/log.txt':
            self.send_response(200)
            self.send_header("Content-type", "text")
            self.end_headers()
            config = load_config(config_file, tv_path, av_path, lang_path)
            a = leer_img(cwd + separador + 'emby_xnoppo_client_logging.log')
            self.wfile.write(bytes(a))  
            return(0)
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("<html><head><title>https://pythonbasics.org</title></head>", "utf-8"))
            self.wfile.write(bytes("<p>Request: %s</p>" % self.path, "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))
            self.wfile.write(bytes("<p>This is an example web server.</p>", "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))

    def do_POST(self):
        cwd = os.path.dirname(os.path.abspath(__file__))
        if sys.platform.startswith('win'):
              separador="\\"
        else:
              separador="/"
        resource_path=cwd + separador + 'web' + separador + 'resources' + separador
        html_path = cwd + separador + 'web' + separador
        tv_path = cwd + separador + 'web' + separador + 'libraries' + separador + 'TV' + separador
        av_path = cwd + separador + 'web' + separador + 'libraries' + separador + 'AV' + separador
        lib_path = cwd + separador + 'lib' + separador
        lang_path = cwd + separador + 'web' + separador + 'lang' + separador
        vers_path = cwd + separador + 'versions' + separador
        
        print(self.path)
        if self.path == '/save_config':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))
                save_config(config_file, config)
                self.send_response(200)
                self.send_header("Content-Length", len(config))
                self.send_header("Content-Type", "text/html")
                self.send_header('Access-Control-Allow-Credentials', 'true')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(bytes(json.dumps(config),"utf-8"))
        if self.path == '/check_emby':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))       
                a = test_emby(config)
                if a == 'OK':
                    self.send_response(200)
                    self.send_header("Content-Length", len(config))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(config),"utf-8"))
                    status = get_state()
                    if status["Playstate"]=="Not_Connected":
                        save_config(config_file, config)
                        emby_wsocket.ws_config=config
                        restart()
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/check_oppo':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))       
                a = test_oppo(config)
                if a == 'OK':
                    self.send_response(200)
                    self.send_header("Content-Length", len(config))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(config),"utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/test_path':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                server = json.loads(post_data.decode('utf-8'))
                config = load_config(config_file, tv_path, av_path, lang_path)
                a = test_path(config,server)
                if a == 'OK':
                    self.send_response(200)
                    self.send_header("Content-Length", len(server))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(server),"utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/navigate_path':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                path_obj = json.loads(post_data.decode('utf-8'))
                path = path_obj["path"]
                config = load_config(config_file, tv_path, av_path, lang_path)
                a = navigate_folder(path,config)
                a_json=json.dumps(a)
                print(len(a_json))
                self.send_response(200)
                self.send_header("Content-Length", len(a_json))
                self.send_header("Content-Type", "text/html")
                self.send_header('Access-Control-Allow-Credentials', 'true')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(bytes(json.dumps(a),"utf-8"))
                return(0)

        if self.path == '/move_tv':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))
                save_config(config_file, config)
                move_files(tv_path + config["TV_model"],lib_path)
                self.send_response(200)
                self.send_header("Content-Length", len(config))
                self.send_header("Content-Type", "text/html")
                self.send_header('Access-Control-Allow-Credentials', 'true')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(bytes(json.dumps(config),"utf-8"))
                restart()
                return(0)
        if self.path == '/move_av':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))
                save_config(config_file, config)
                move_files(av_path + config["AV_model"],lib_path)
                self.send_response(200)
                self.send_header("Content-Length", len(config))
                self.send_header("Content-Type", "text/html")
                self.send_header('Access-Control-Allow-Credentials', 'true')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(bytes(json.dumps(config),"utf-8"))
                restart()
                return(0)
        if self.path == '/get_tv_key':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))       
                a = get_tv_key(config)
                if a == 'OK':
                    save_config(config_file, config)
                    self.send_response(200)
                    self.send_header("Content-Length", len(config))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(config),"utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/tv_test_conn':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))       
                a = tv_test_conn(config)
                if a == 'OK':
                    self.send_response(200)
                    self.send_header("Content-Length", len(config))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(config),"utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/get_tv_sources':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))       
                a = get_tv_sources(config)
                if a == 'OK':
                    save_config(config_file, config)
                    self.send_response(200)
                    self.send_header("Content-Length", len(config))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(config),"utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/get_av_sources':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))       
                a = get_hdmi_list(config)
                if a != None:
                    config["AV_SOURCES"]=a
                    save_config(config_file, config)
                    self.send_response(200)
                    self.send_header("Content-Length", len(config))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(config),"utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/tv_test_init':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))       
                a = tv_change_hdmi(config)
                if a == 'OK':
                    self.send_response(200)
                    self.send_header("Content-Length", len(config))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(config),"utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/tv_test_end':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))       
                a = tv_set_prev(config)
                if a == 'OK':
                    self.send_response(200)
                    self.send_header("Content-Length", len(config))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(config),"utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/av_test_on':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))       
                a = av_check_power(config)
                if a == 'OK':
                    self.send_response(200)
                    self.send_header("Content-Length", len(config))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(config),"utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/av_test_off':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))       
                a = av_power_off(config)
                if a == 'OK':
                    self.send_response(200)
                    self.send_header("Content-Length", len(config))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(config),"utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/av_test_hdmi':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                config = json.loads(post_data.decode('utf-8'))       
                a = av_change_hdmi(config)
                if a == 'OK':
                    self.send_response(200)
                    self.send_header("Content-Length", len(config))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes(json.dumps(config),"utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
        if self.path == '/start_movie':
                content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
                post_data = self.rfile.read(content_length) # <--- Gets the data itself
                print(post_data)
                data=json.loads(post_data.decode('utf-8'))
                print(data)
                emby_wsocket._play(data)
                a = 'OK'
                if a == 'OK':
                    self.send_response(200)
                    self.send_header("Content-Length", len("Ok"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("OK","utf-8"))
                else:
                    self.send_response(300)
                    self.send_header("Content-Length", len("ERROR"))
                    self.send_header("Content-Type", "text/html")
                    self.send_header('Access-Control-Allow-Credentials', 'true')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(bytes("ERROR","utf-8"))
                return(0)
if __name__ == "__main__":

    cwd = os.path.dirname(os.path.abspath(__file__))
    if sys.platform.startswith('win'):
              separador="\\"
    else:
              separador="/"
    config_file = str(ensure_config_exists())
    resource_path=cwd + separador + 'web' + separador + 'resources' + separador
    html_path = cwd + separador + 'web' + separador
    tv_path = cwd + separador + 'web' + separador + 'libraries' + separador + 'TV' + separador
    av_path = cwd + separador + 'web' + separador + 'libraries' + separador + 'AV' + separador
    lib_path = cwd + separador + 'lib' + separador
    lang_path = cwd + separador + 'web' + separador + 'lang' + separador
    vers_path = cwd + separador + 'versions' + separador
    config = load_config(config_file,tv_path,av_path,lang_path)
    logfile=cwd + separador + "emby_xnoppo_client_logging.log"
    lang = cargar_lang(lang_path + config["language"] + separador +'lang.js')

    if config["DebugLevel"]==0:
       logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',datefmt='%d/%m/%Y %I:%M:%S %p',level=logging.CRITICAL)
    elif config["DebugLevel"]==1:
       rfh = logging.handlers.RotatingFileHandler(
                filename=logfile, 
                mode='a',
                maxBytes=50*1024*1024,
                backupCount=2,
                encoding=None,
                delay=0
       )
       logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',datefmt='%d/%m/%Y %I:%M:%S %p',level=logging.INFO,handlers=[rfh])
    elif config["DebugLevel"]==2:
       rfh = logging.handlers.RotatingFileHandler(
                filename=logfile, 
                mode='a',
                maxBytes=5*1024*1024,
                backupCount=2,
                encoding=None,
                delay=0
       )
       logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',datefmt='%d/%m/%Y %I:%M:%S %p',level=logging.DEBUG,handlers=[rfh])

    config_file = str(ensure_config_exists())
    config = load_config(config_file, tv_path, av_path, lang_path)
    config_ready = is_configured(config)
    emby_wsocket = None

    if config_ready:
        emby_wsocket = XnoppoWs()
        emby_wsocket.ws_config=config
        emby_wsocket.config_file=config_file
        emby_wsocket.ws_lang=lang
        x = threading.Thread(target=thread_function, args=(emby_wsocket,))
        x.daemon = True
        x.start()
    else:
        print("Config is not complete yet. Web UI is available; Emby websocket will not start.")

    if config_ready:
        # Arrancamos el Perro Guardián para evitar estados congelados
        w = threading.Thread(target=watchdog_function, args=(emby_wsocket, config))
        w.daemon = True
        w.start()
    else:
        print("Watchdog will not start until configuration is complete.")

    espera=0
    estado_anterior=''

    logging.debug('Arrancamos el Servidor Web\n')
    serverPort = 8090
    webServer = HTTPServer(("", serverPort), MyServer)
    print("Server started http://%s:%s" % ("", serverPort))
    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass
    webServer.server_close()
    logging.info('Fin proceso')
    logging.info('Finished')
    print("Server stopped.")
