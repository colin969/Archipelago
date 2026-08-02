from typing import Any, Dict
from uuid import UUID
import zlib

from flask import abort, url_for

from WebHostLib import to_url
import worlds.Files
from . import api_endpoints, get_players
from ..models import Room
from ..tracker import TrackerData
from Utils import restricted_loads

@api_endpoints.route('/room_status/<suuid:room_id>')
def room_info(room_id: UUID) -> Dict[str, Any]:
    room = Room.get(id=room_id)
    if room is None:
        return abort(404)

    def supports_apdeltapatch(game: str) -> bool:
        return game in worlds.Files.AutoPatchRegister.patch_types

    downloads = []
    for slot in sorted(room.seed.slots):
        if slot.data and not supports_apdeltapatch(slot.game):
            slot_download = {
                "slot": slot.player_id,
                "download": url_for("download_slot_file", room_id=room.id, player_id=slot.player_id)
            }
            downloads.append(slot_download)
        elif slot.data:
            slot_download = {
                "slot": slot.player_id,
                "download": url_for("download_patch", patch_id=slot.id, room_id=room.id)
            }
            downloads.append(slot_download)

    return {
        "tracker": to_url(room.tracker),
        "players": get_players(room.seed),
        "last_port": room.last_port,
        "last_activity": room.last_activity,
        "timeout": room.timeout,
        "downloads": downloads,
    }

@api_endpoints.route('/room/<suuid:room_id>/players')
def room_players(room_id: UUID) -> Dict[str, Any]:
    room = Room.get(id=room_id)
    if room is None:
        return abort(404)

    multidata = decompress(room.seed.multidata)
    return {
        "slots": multidata["slot_info"],
        "auth": multidata["connect_names"]
    }

@api_endpoints.route('/room/<suuid:room_id>/spheres')
def room_spheres(room_id: UUID):
    room = Room.get(id=room_id)
    if not room:
        abort(404)

    tracker_data = TrackerData(room)
    spheres = tracker_data.get_json_spheres()
    return spheres

@api_endpoints.route('/room/<suuid:room_id>/checked_locations')
def room_checked_locations(room_id: UUID) -> Dict[str, Any]:
    room = Room.get(id=room_id)
    if not room:
        abort(404)

    tracker_data = TrackerData(room)
    return tracker_data.get_all_checked_locations_json()

def decompress(data: bytes) -> dict:
    return restricted_loads(zlib.decompress(data[1:]))