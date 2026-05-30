# OPPO MediaControl HTTP API

This document collects the OPPO / Chinoppo UDP-203 HTTP endpoints observed in
this project and in public reverse-engineering notes for the OPPO MediaControl
app protocol.

The OPPO also exposes an official RS-232/IP control protocol over TCP, usually
port `23`. That protocol is good for remote-control commands and lightweight
state queries such as `QPL`. The HTTP API documented here is the MediaControl
app protocol exposed on port `436`; it is needed for network share discovery,
mounting, file playback, subtitle menu handling, and playback progress data.

## Sources

- Project implementation: `lib/devices/oppo/control_api_client.py`,
  `lib/Xnoppo.py`.
- Runtime validation from Docker container logs on 2026-05-30.
- Public reverse-engineering notes:
    - <https://xiaohai.co/oppo-udp-203-control-protocol/>
    - <https://www.avforums.com/threads/free-oppo-and-clones-jailbreak.2332399/page-59>
    - <https://www.avforums.com/threads/the-ultimate-oppo-media-device.2207229/page-189>
- Official TCP/RS-232 protocol reference, useful for comparison:
    - <https://download.oppodigital.com/UDP203/OPPO_UDP-20X_RS-232_and_IP_Control_Protocol.pdf>

## Transport

The MediaControl API uses HTTP GET:

```text
http://{player_host}:436/{endpoint}
http://{player_host}:436/{endpoint}?{json_payload}
```

The payload is JSON in the query string. Some endpoints tolerate raw JSON, while
others are safer with URL-encoded JSON. Existing validated code keeps the shape
that worked in real playback tests.

Before using port `436`, the player may need the MediaControl app activation
message on UDP port `7624`:

```text
NOTIFY OREMOTE LOGIN
```

After that, the OPPO opens or refreshes the HTTP control API on port `436`.

## Common Response Shapes

Successful command-style responses usually look like:

```json
{
  "success": true,
  "msg": ""
}
```

Some network-share operations use `retInfo`:

```json
{
  "success": true,
  "retInfo": ""
}
```

Failure responses observed or synthesized by this project:

```json
{
  "success": false,
  "msg": ""
}
{
  "success": false,
  "retInfo": "Timeout in Mount Request"
}
{
  "success": false,
  "retInfo": "Timeout in Play Request"
}
```

Important behaviour:

- `setplaytime`, `setaudiomenulist`, and related control commands may return
  `success:false` while still having useful side effects on the OPPO.
- `mountNfsSharedFolder` can return `{}` even when the mount succeeded. The
  project normalizes this to a successful response for compatibility.
- `getplayingtime` can temporarily return zero values during startup, disc/menu
  transitions, and immediately after stop. Do not overwrite a known nonzero
  Emby progress value just because a transient OPPO response says `0`.

## Playback Startup Endpoints

### `signin`

Registers the MediaControl app session with the OPPO. This is the first normal
HTTP call after UDP activation.

Request:

```http
GET /signin?{"appIconType":1,"appIpAddress":"192.168.50.110"}
```

Fields:

- `appIconType`: MediaControl client icon type. Existing code uses `1`.
- `appIpAddress`: IP address of the application/media server host.

Expected response:

```json
{
  "success": true,
  "msg": "",
  "player_name": "UDP-203_OPPO UDP-203",
  "player_port": "436"
}
```

Project usage:

- Used by the clean OPPO startup flow before `getdevicelist`.

### `getdevicelist`

Returns network devices/shares visible to the OPPO.

Request:

```http
GET /getdevicelist
```

Expected response:

```json
{
  "success": true,
  "msg": "",
  "devicelist": [
    {
      "sub_type": "nfs",
      "name": "192.168.50.110",
      "path": "192.168.50.110"
    }
  ]
}
```

Important fields:

- `name`: server name or IP as seen by the OPPO.
- `sub_type`: protocol family. Observed values include `nfs` and `cifs`.

Project usage:

- Used to decide whether to use NFS or SMB/CIFS.

### `loginNfsServer`

Selects/logs into an NFS server before mounting a folder.

Request:

```http
GET /loginNfsServer?{"serverName":"192.168.50.110"}
```

Expected response:

```json
{
  "success": true,
  "retInfo": ""
}
```

Project usage:

- Used for NFS playback before `mountNfsSharedFolder`.

### `getNfsShareFolderlist`

Lists NFS folders exposed by the selected server.

Request:

```http
GET /getNfsShareFolderlist
```

Expected response:

The response is not clean JSON in the legacy code path. Existing legacy parsing
splits binary-ish text by control separators and extracts folder names.

Project usage:

- Legacy browsing/navigation helper.
- Not required by the clean direct-play startup flow when Emby already provides
  the final media path.

### `mountNfsSharedFolder`

Mounts an NFS folder on the OPPO and returns the OPPO mount path.

Request:

```http
GET /mountNfsSharedFolder?{"server":"192.168.50.110","folder":"volume1/Video/Movies/Full%20HD"}
```

Expected response:

```json
{
  "success": true,
  "retInfo": "",
  "nfsMntPath": "/mnt/nfs1",
  "server": "192.168.50.110",
  "folder": "volume1/Video/Movies/Full HD"
}
```

Known compatibility response:

```json
{}
```

Project usage:

- Used for NFS playback startup.
- The returned `nfsMntPath` must be carried forward. Do not hardcode
  `/mnt/nfs1`; the OPPO may return another slot after previous failures.

### `loginSambaWithOutID`

Selects/logs into an SMB/CIFS server without credentials.

Request:

```http
GET /loginSambaWithOutID?{"serverName":"NAS"}
```

Expected response:

```json
{
  "success": true,
  "retInfo": ""
}
```

Project usage:

- Used for SMB/CIFS playback when the OPPO reports `sub_type:"cifs"`.

### `getSambaShareFolderlist`

Lists SMB/CIFS folders exposed by the selected server.

Request:

```http
GET /getSambaShareFolderlist
```

Expected response:

The legacy parser treats this similarly to `getNfsShareFolderlist`, extracting
folder names from a separator-based response rather than normal JSON.

Project usage:

- Legacy browsing/navigation helper.
- Not required by the clean direct-play startup flow.

### `mountSharedFolder`

Mounts an SMB/CIFS folder and returns the OPPO mount path.

Request without credentials:

```http
GET /mountSharedFolder?{"server":"NAS","bWithID":0,"folder":"Movies","userName":"","password":"","bRememberID":0}
```

Request with credentials:

```http
GET /mountSharedFolder?{"server":"NAS","bWithID":1,"folder":"Movies","userName":"user","password":"pass","bRememberID":1}
```

Expected response:

```json
{
  "success": true,
  "retInfo": "",
  "cifsMntPath": "/mnt/cifs1",
  "server": "NAS",
  "folder": "Movies"
}
```

Project usage:

- Used for SMB/CIFS playback startup.
- The returned `cifsMntPath` must be carried forward. Do not hardcode
  `/mnt/cifs1`.

### `playnormalfile`

Starts playback for a normal media file path on a mounted OPPO share. In our
validated flow this works for MKV and ISO file paths.

Request:

```http
GET /playnormalfile?{"path":"/mnt/nfs1/Movie.mkv","index":0,"type":1,"appDeviceType":2,"extraNetPath":"192.168.50.110","playMode":0}
```

Fields:

- `path`: full OPPO-side mounted file path.
- `index`: item index; existing direct-play flow uses `0`.
- `type`: media type; existing direct-play flow uses `1`.
- `appDeviceType`: observed values differ in public examples; project uses `2`
  in validated playback.
- `extraNetPath`: original server/share identifier.
- `playMode`: existing flow uses `0`.

Expected response:

```json
{
  "success": true,
  "msg": ""
}
```

Project usage:

- Core clean startup endpoint.
- After this command, QPL on TCP port `23` is preferred for detecting active
  playback startup.

### `checkfolderhasBDMV`

Checks/starts playback for a mounted folder containing a Blu-ray folder
structure.

Request:

```http
GET /checkfolderhasBDMV?{"folderpath":"/mnt/nfs1/SomeMovie/BDMV"}
```

Expected response:

```json
{
  "success": true,
  "msg": ""
}
```

Project usage:

- Used when the resolved media location represents a Blu-ray folder structure.
- For ISO files, the project currently uses `playnormalfile`.

### `getfilelist`

Lists files/folders under a mounted OPPO path.

Request:

```http
GET /getfilelist?{"path":"/mnt/nfs1","fileType":1,"mediaType":3,"flag":1}
```

Public examples use lower-case field names:

```json
{
  "path": "/mnt/cifs1",
  "filetype": 1,
  "mediatype": 3,
  "flag": 3,
  "deviceSubType": 7
}
```

Expected response:

The legacy parser treats the response as separator-delimited text and extracts
file/folder names. Do not assume normal JSON.

Project usage:

- Legacy navigation helper.
- Not required by the clean direct-play flow.

## Playback State and Progress Endpoints

### `getglobalinfo`

Returns broad state flags: active app, media type, volume, mute state, and
whether audio/video/picture/disc playback is active.

Request:

```http
GET /getglobalinfo
```

Expected response:

```json
{
  "success": true,
  "curr_volume": 100,
  "min_volume": 0,
  "max_volume": 100,
  "is_muted": false,
  "cur_media_type": 5,
  "is_audio_playing": false,
  "gapless_play_mode": 0,
  "is_pic_playing": false,
  "is_video_playing": true,
  "is_bdmv_playing": false,
  "is_disc_playing": false,
  "output_volume_mode": "variable",
  "activeapp": "playback",
  "msg": ""
}
```

Project usage:

- Still used by the legacy progress loop.
- Should be replaced as the loop stop/active condition by QPL where possible.
  Keep `getplayingtime` for seconds until a TCP alternative is validated.

### `getmovieplayinfo`

Returns richer current movie playback info.

Request:

```http
GET /getmovieplayinfo
```

Expected response:

```json
{
  "success": true,
  "msg": "",
  "playinfo": {
    "bd_file_path": "/mnt/nfs1/Movie",
    "file_path": "BDISO",
    "e_play_status": 0,
    "e_play_mode": 0,
    "cur_time": 4,
    "total_time": 6005
  }
}
```

Project usage:

- Documented externally.
- Not currently part of the active clean flow.

### `getplayingtime`

Returns current playback time and total duration in seconds.

Request:

```http
GET /getplayingtime
```

Expected response:

```json
{
  "success": true,
  "msg": "",
  "media_type": 13,
  "cur_time": 4,
  "total_time": 6005,
  "disc_cur_time": 0,
  "disc_total_time": 0
}
```

Project usage:

- Used to report progress back to Emby.

Known behaviour from real tests:

- MKV can initially report `0 de 7756` and then jump to the real resume point.
- ISO can initially report `0 de 145` and later jump to the full movie duration
  and resume point.
- A very early user stop can happen before the first valid nonzero reading.
  Seed progress from `auto_resume` and preserve the last valid nonzero value.

### `setplaytime`

Seeks/restores playback to an absolute time.

Request:

```http
GET /setplaytime?{"h":0,"m":8,"s":40}
```

Expected response:

```json
{
  "success": true,
  "msg": ""
}
```

Observed response:

```json
{
  "success": false,
  "msg": ""
}
```

Project usage:

- Used for Emby resume.
- A `success:false` response does not necessarily mean the seek failed. In real
  tests, `getplayingtime` later jumped to the requested resume area.

## Audio and Subtitle Endpoints

### `setaudiomenulist`

Selects an audio track by OPPO menu index.

Request:

```http
GET /setaudiomenulist?{"cur_index":1}
```

Expected response:

```json
{
  "success": true,
  "msg": ""
}
```

Observed response:

```json
{
  "success": false,
  "msg": ""
}
```

Project usage:

- Emby audio stream index is translated to OPPO audio menu index before calling
  this endpoint.
- Real tests show playback can continue even when the command response is
  `success:false`.

### `getsubtitlemenulist`

Returns subtitle menu entries and selected subtitle.

Request:

```http
GET /getsubtitlemenulist?
```

Expected response:

```json
{
  "success": true,
  "msg": "",
  "subtitle_list": [
    {
      "index": 0,
      "selected": true,
      "name": "Off"
    },
    {
      "index": 1,
      "selected": false,
      "name": "Spanish"
    }
  ]
}
```

Project usage:

- Used before and after `setsubttmenulist` to confirm selected subtitle.
- Keep the trailing `?` in the URL shape. This matches the legacy implementation
  and the public examples.

### `setsubttmenulist`

Selects a subtitle track by OPPO subtitle menu index.

Request:

```http
GET /setsubttmenulist?{"cur_index":2}
```

Expected response:

```json
{
  "success": true,
  "msg": ""
}
```

Project usage:

- Emby subtitle stream index is translated to OPPO subtitle menu index before
  calling this endpoint.
- Public forum notes specifically mention this endpoint as useful for enabling
  subtitles through port `436` when the normal remote UI path is insufficient.

Current caution:

- Real tests confirmed the endpoint is called, but subtitle selection can take a
  few seconds and should be validated carefully for MKV and ISO separately.
- Do not conclude failure just because an early stop records a transient
  `getplayingtime` zero; check QPL state and whether a valid nonzero progress
  reading had occurred.

## Remote and Diagnostic Endpoints

### `sendremotekey`

Sends a remote-control key through the MediaControl HTTP API.

Request:

```http
GET /sendremotekey?{"key":"SEL"}
```

Expected response:

```json
{
  "success": true,
  "msg": ""
}
```

Project usage:

- Legacy flows used this for keys such as `EJT`, `QPW`, and `POF`.
- For direct state queries such as playback state, prefer TCP/QPL where possible.
- For actual remote-button semantics, this endpoint can still be acceptable.

### `getmainfirmwareversion`

Returns firmware/version information.

Request:

```http
GET /getmainfirmwareversion
```

Expected response:

```json
{
  "success": true,
  "player_style": "UDP-203",
  "bbkver": "20XCN-65-0132"
}
```

Project usage:

- Legacy diagnostic/preparation call.
- Not needed in the clean playback startup flow.

### `getsetupmenu`

Reads setup/menu state.

Request:

```http
GET /getsetupmenu
```

Expected response:

```json
{
  "success": true,
  "msg": "setting done"
}
```

Project usage:

- Legacy refresh/sync call.
- Real startup tests show playback works without this call.

### `getvolume`

Returns OPPO volume and mute state.

Request:

```http
GET /getvolume
```

Expected response:

```json
{
  "success": true,
  "msg": "",
  "curr_volume": 40,
  "min_volume": 0,
  "max_volume": 100,
  "is_muted": false
}
```

Project usage:

- Documented externally.
- Not currently used by the playback handoff flow.

## Other Documented Endpoints

These endpoints appear in public notes but are not part of the active clean
startup/progress path.

### `getFavoriteDBFile`

Purpose:

- Reads favorite file database information.

Request:

```http
GET /getFavoriteDBFile
```

Expected response:

```json
{
  "success": true
}
```

### `getdvdbdgninfo`

Purpose:

- DVD/Blu-ray information endpoint. Public notes show an empty or unclear
  response.

Request:

```http
GET /getdvdbdgninfo
```

Expected response:

```json
{}
```

### `getmoviefileusercoverisready`

Purpose:

- Checks whether user cover art is ready for a movie file.

Request:

```http
GET /getmoviefileusercoverisready
```

Expected response:

```json
{
  "success": true,
  "hasCover": false
}
```

### `getUsbMediaCover`

Purpose:

- Requests cover information for a USB or mounted media file.

Request:

```http
GET /getUsbMediaCover?{"type":2,"fullName":"/mnt/cifs1/Movie.iso"}
```

Expected response:

The public notes list the request shape but do not provide a complete response
shape. Treat this endpoint as undocumented until validated locally.

## Recommended Project Usage

Keep using HTTP `436` for:

- MediaControl session registration.
- Network device/share discovery.
- NFS/SMB login and mount.
- File/BDMV playback startup.
- Absolute seek/resume by h/m/s.
- Audio and subtitle menu selection.
- Playback time reporting until a TCP equivalent is validated.

Prefer TCP port `23` for:

- Playback state polling, especially startup active-state detection.
- Power/status queries such as `QPL` or `QPW`.
- Remote-control style commands when they map directly to official OPPO control
  protocol commands.
