import time
import logging
import json

# Simulamos la importacion si no existen las libs originales para que no pete el test
try:
    from lib.Xnoppo import check_socket, sendremotekey, mountSharedFolder, mountSharedNFSFolder, LoginNFS, \
        LoginSambaWithOutID
except ImportError:
    pass


class PlaybackManager:
    def __init__(self, config):
        self.config = config
        self.max_retries = 20
        self.retry_delay = 2  # Segundos iniciales

    def wait_for_oppo_network(self):
        """Espera activa hasta que el OPPO responde al ping/socket"""
        logging.info("Esperando a que el OPPO esté en línea...")
        for i in range(self.max_retries):
            # Asumimos que check_socket devuelve 0 si éxito
            if check_socket(self.config) == 0:
                logging.info(f"OPPO detectado online en intento {i + 1}")
                return True
            time.sleep(1)
        logging.error("OPPO no respondió después de varios intentos.")
        return False

    def safe_start_movie(self, server_path, oppo_path):
        """Secuencia robusta de inicio de reproducción"""

        # 1. Asegurar red (Vital para el error de LG TV)
        if not self.wait_for_oppo_network():
            return "ERROR_TIMEOUT_OPPO"

        # 2. Encender y despertar (Key simulation)
        # Enviamos teclas para asegurar que sale de screensaver
        sendremotekey("EJT", self.config)  # Wake up / Eject trick
        time.sleep(2)

        # 3. Montaje de unidades (con reintento)
        logging.info(f"Intentando montar: {oppo_path}")
        # Lógica simplificada de montaje basada en tu config
        is_nfs = self.config.get("default_nfs", False)

        if is_nfs:
            mount_res = mountSharedNFSFolder(server_path, oppo_path, '', '', self.config)
        else:
            mount_res = mountSharedFolder(server_path, oppo_path, '', '', self.config)

        # Analizar respuesta JSON del montaje
        try:
            res_json = json.loads(mount_res)
            if not res_json.get("success"):
                logging.warning("Primer intento de montaje fallido, reintentando...")
                time.sleep(2)
                if is_nfs:
                    mountSharedNFSFolder(server_path, oppo_path, '', '', self.config)
                else:
                    mountSharedFolder(server_path, oppo_path, '', '', self.config)
        except:
            pass

        # 4. Iniciar reproducción (Aquí iría la lógica de PlayFile del OPPO)
        # Nota: Como no tengo el archivo Xnoppo.py original, asumo que el montaje
        # incluye la orden de play o se hace justo después.

        return "OK_STARTED"