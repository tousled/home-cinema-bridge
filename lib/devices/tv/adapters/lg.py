import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress

from bscpylgtv import WebOsClient
from wakeonlan import send_magic_packet

from lib.network.arp import find_mac_by_ip

from lib.devices.tv.base import BaseTvController, TvStatus


EMBY_APP_ID = "com.emby.app"

LG_CONNECT_TIMEOUT_SECONDS = 20.0
LG_FAST_CONNECT_TIMEOUT_SECONDS = 2.0
LG_WAKE_TIMEOUT_SECONDS = 20.0
LG_WAKE_RETRY_INTERVAL_SECONDS = 1.0
LG_KEY_FILE_PATH = "/config/.aiopylgtv.sqlite"


def _map_webos_inputs_to_legacy_sources(inputs: list[dict]) -> list[dict]:
    sources = []

    for index, webos_input in enumerate(inputs):
        input_id = webos_input.get("id")

        if not input_id:
            logging.warning("Skipping LG input without id: %s", webos_input)
            continue

        sources.append({
            "index": index,
            "id": input_id,
            "appId": webos_input.get("appId", ""),
            "nombre": webos_input.get("label") or input_id,
            "connected": bool(webos_input.get("connected", False)),
        })

    return sources


class LgTvController(BaseTvController):
    async def test_connection(self) -> TvStatus:
        return await self._execute_tv_operation(
            "testing LG TV connection",
            self._test_connection,
        )

    async def refresh_inputs(self) -> TvStatus:
        return await self._execute_tv_operation(
            "refreshing LG TV inputs",
            self._refresh_inputs,
        )

    async def switch_to_player_input(self) -> TvStatus:
        return await self._execute_tv_operation(
            "switching LG TV to player input",
            self._switch_to_player_input,
        )

    async def return_to_previous_app(self) -> TvStatus:
        return await self._execute_tv_operation(
            "returning LG TV to previous app",
            self._return_to_previous_app,
        )

    @asynccontextmanager
    async def _connected_client(self, *, wake_if_unreachable: bool = False):
        client = None

        try:
            if wake_if_unreachable:
                client = await self._connect_or_wake()
            else:
                client = await self._connect()

            yield client

        finally:
            await self._disconnect(client)

    async def _connect(self, *, timeout: float = LG_CONNECT_TIMEOUT_SECONDS) -> WebOsClient:
        tv_ip = self.config.get("TV_IP", "")

        if not tv_ip:
            raise ValueError("TV_IP is not configured")

        client = await WebOsClient.create(
            tv_ip,
            key_file_path=LG_KEY_FILE_PATH,
            timeout_connect=timeout,
        )
        await asyncio.wait_for(client.connect(), timeout=timeout)

        return client

    async def _connect_or_wake(self) -> WebOsClient:
        try:
            return await self._connect(timeout=LG_FAST_CONNECT_TIMEOUT_SECONDS)

        except ValueError:
            raise

        except TimeoutError:
            logging.info("LG TV is not reachable due to timeout. Attempting Wake-on-LAN.")
            self._wake_tv()
            return await self._wait_until_reachable()

        except OSError:
            logging.info("LG TV is not reachable due to network error. Attempting Wake-on-LAN.")
            self._wake_tv()
            return await self._wait_until_reachable()

    async def _wait_until_reachable(self) -> WebOsClient:
        deadline = time.monotonic() + LG_WAKE_TIMEOUT_SECONDS
        last_error = None

        while time.monotonic() < deadline:
            try:
                return await self._connect(timeout=LG_FAST_CONNECT_TIMEOUT_SECONDS)

            except TimeoutError as exc:
                last_error = exc
                await asyncio.sleep(LG_WAKE_RETRY_INTERVAL_SECONDS)

            except OSError as exc:
                last_error = exc
                await asyncio.sleep(LG_WAKE_RETRY_INTERVAL_SECONDS)

        raise TimeoutError(f"LG TV did not become reachable after Wake-on-LAN: {last_error}")

    @staticmethod
    async def _disconnect(client: WebOsClient | None) -> None:
        if client is not None:
            with suppress(Exception):
                await client.disconnect()

    def _wake_tv(self) -> None:
        mac = self._get_mac_for_wake()

        if not mac:
            raise ValueError("TV_MAC is not available and could not be detected automatically")

        try:
            logging.info("Sending Wake-on-LAN packet to LG TV: %s", mac)
            send_magic_packet(mac)

        except (OSError, ValueError) as exc:
            raise OSError(f"Unable to send Wake-on-LAN packet to LG TV: {exc}") from exc

    def _get_mac_for_wake(self) -> str | None:
        return self.config.get("TV_MAC") or self._refresh_mac_from_arp()

    def _refresh_mac_from_arp(self) -> str | None:
        tv_ip = self.config.get("TV_IP", "")

        if not tv_ip:
            return None

        detected_mac = find_mac_by_ip(tv_ip)

        if not detected_mac:
            return None

        stored_mac = self.config.get("TV_MAC", "")

        if stored_mac != detected_mac:
            if stored_mac:
                logging.info(
                    "LG TV MAC updated from ARP: old=%s | new=%s",
                    stored_mac,
                    detected_mac,
                )
            else:
                logging.info("LG TV MAC learned from ARP: %s", detected_mac)

            self.config["TV_MAC"] = detected_mac

        return detected_mac

    def _selected_input_id(self) -> str:
        source_index = int(self.config.get("Source", 0))
        sources = self.config.get("TV_SOURCES", [])

        if not 0 <= source_index < len(sources):
            raise ValueError(f"Selected TV input index is not available: {source_index}")

        selected_source = sources[source_index]
        input_id = selected_source.get("id")

        if not input_id:
            raise ValueError("Selected TV input has no WebOS id. Refresh TV inputs first.")

        return input_id

    async def _test_connection(self) -> TvStatus:
        async with self._connected_client():
            self._refresh_mac_from_arp()
            return TvStatus.OK

    async def _refresh_inputs(self) -> TvStatus:
        async with self._connected_client() as client:
            self._refresh_mac_from_arp()

            inputs = await client.get_inputs()
            self.config["TV_SOURCES"] = _map_webos_inputs_to_legacy_sources(inputs)

            return TvStatus.OK

    async def _switch_to_player_input(self) -> TvStatus:
        async with self._connected_client(wake_if_unreachable=True) as client:
            current_app = await client.get_current_app()

            if current_app:
                self.config["current_LG"] = current_app
                logging.info("Current LG app before HDMI switch: %s", current_app)

            target_input = self._selected_input_id()
            logging.info("Changing LG TV input to %s", target_input)

            await client.set_input(target_input)
            return TvStatus.OK

    async def _return_to_previous_app(self) -> TvStatus:
        async with self._connected_client() as client:
            target_app = self.config.get("current_LG") or EMBY_APP_ID
            logging.info("Launching LG app: %s", target_app)

            await client.launch_app(target_app)
            return TvStatus.OK