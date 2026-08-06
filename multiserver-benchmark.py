import argparse
import asyncio
import functools
import threading
import time
import websockets
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ModuleUpdate
ModuleUpdate.update()

import MultiServer
from NetUtils import decode, encode
from Utils import Version


def parse_args():
    parser = argparse.ArgumentParser(description="MultiServer release_player benchmark")
    parser.add_argument("--archipelago", default="benchmark.archipelago",
                        help="Path to the .archipelago multidata file")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=38281, type=int)
    return parser.parse_args()

def run_server(args, ready_event: threading.Event, ctx_holder: list):
    async def _main():
        import logging
        ctx = MultiServer.Context(
            host=args.host,
            port=args.port,
            server_password="",
            password="",
            location_check_points=1,
            hint_cost=10,
            item_cheat=False,
            release_mode="enabled",
            collect_mode="disabled",
            countdown_mode="disabled",
            remaining_mode="disabled",
            auto_shutdown=0,
            compatibility=2,
            log_network=False,
            logger=logging.getLogger("benchmark_server"),
        )
        ctx.load(args.archipelago, use_embedded_server_options=False)
        ctx.init_save(enabled=False)

        ctx.server = websockets.serve(
            functools.partial(MultiServer.server, ctx=ctx),
            host=ctx.host,
            port=ctx.port,
        )
        await ctx.server

        ctx_holder.append(ctx)
        ready_event.set()          # signal: server is up
        await ctx.exit_event.wait()

    asyncio.run(_main())

async def run_client(host: str, port: int, slot_name: str, password: str,
                     game: str, version: tuple, connected_event: asyncio.Event):
    uri = f"ws://{host}:{port}"
    try:
        async with websockets.connect(uri) as ws:
            # Wait for RoomInfo
            while True:
                raw = await ws.recv()
                msgs = decode(raw)
                if any(m.get("cmd") == "RoomInfo" for m in msgs):
                    break

            # Send Connect
            connect_msg = encode([{
                "cmd": "Connect",
                "game": game,
                "name": slot_name,
                "password": password,
                "version": {"major": version[0], "minor": version[1], "build": version[2],
                            "class": "Version"},
                "items_handling": 0b111,
                "tags": [],
                "uuid": f"bench-{slot_name}",
                "slot_data": False,
            }])
            await ws.send(connect_msg)

            # Wait for Connected (or ConnectionRefused)
            while True:
                raw = await ws.recv()
                msgs = decode(raw)
                for m in msgs:
                    if m.get("cmd") == "Connected":
                        connected_event.set()
                        break
                    if m.get("cmd") == "ConnectionRefused":
                        print(f"[client:{slot_name}] ConnectionRefused: {m.get('errors')}")
                        connected_event.set()
                        return
                if connected_event.is_set():
                    break

            # Idle drain (covers pings and roomupdates or something)
            try:
                async for _ in ws:
                    pass
                print(f"[client:{slot_name}] disconnected unexpectedly")
            except websockets.ConnectionClosed as e:
                print(f"[client:{slot_name}] disconnected unexpectedly: {e}")
            except asyncio.CancelledError:
                pass
    except Exception as e:
        print(f"[client:{slot_name}] error: {e}")
        connected_event.set()   # unblock even on error


async def run_all_clients(host: str, port: int, slots: list[tuple[str, str, tuple]],
                          password: str = "", time_holder: list = None):
    events = [asyncio.Event() for _ in slots]
    tasks = []
    for (slot_name, game, version), ev in zip(slots, events):
        t = asyncio.create_task(
            run_client(host, port, slot_name, password, game, version, ev)
        )
        tasks.append(t)

    await asyncio.gather(*[ev.wait() for ev in events])
    if time_holder is not None:
        time_holder.append(time.monotonic_ns())
    print(f"[bench] All {len(slots)} clients connected.")
    return tasks

def benchmark_release(ctx) -> tuple:
    from NetUtils import SlotType

    player_slots = [
        (team, slot)
        for team in ctx.clients
        for slot, slot_info in ctx.slot_info.items()
        if slot_info.type == SlotType.player
    ]

    async def _run():
        start = time.process_time_ns()
        for team, slot in player_slots:
            print(slot)
            MultiServer.release_player(ctx, team, slot)
            await asyncio.sleep(0)
        if hasattr(ctx, '_flush_broadcasts'):
            await ctx._flush_broadcasts()
        return time.process_time_ns() - start, len(player_slots)

    loop = ctx.server.ws_server.get_loop()
    future = asyncio.run_coroutine_threadsafe(_run(), loop)
    return future.result(timeout=300)


def main():
    args = parse_args()

    if not os.path.exists(args.archipelago):
        print(f"Error: '{args.archipelago}' not found.")
        sys.exit(1)

    # Start server in background thread
    ready_event = threading.Event()
    ctx_holder: list = []

    server_thread = threading.Thread(
        target=run_server, args=(args, ready_event, ctx_holder), daemon=True
    )
    server_thread.start()

    print("[bench] Waiting for server to start…")
    ready_event.wait(timeout=30)
    if not ctx_holder:
        print("[bench] Server failed to start in time.")
        sys.exit(1)

    ctx = ctx_holder[0]
    print(f"[bench] Server up. Seed: {ctx.seed_name}")

    from NetUtils import SlotType

    slots_to_connect = []
    for slot_name, (team, slot_id) in ctx.connect_names.items():
        slot_info = ctx.slot_info.get(slot_id)
        if slot_info is None or slot_info.type != SlotType.player:
            continue
        min_ver = ctx.minimum_client_versions.get(slot_id, (0, 5, 0))
        game = ctx.games.get(slot_id, "")
        slots_to_connect.append((slot_name, game, tuple(min_ver)))

    print(f"[bench] Connecting {len(slots_to_connect)} player slots…")

    # Connect all clients 
    client_loop = asyncio.new_event_loop()
    connect_time_holder = []
    connect_start = time.monotonic_ns()

    def run_clients():
        asyncio.set_event_loop(client_loop)
        client_loop.run_until_complete(
            run_all_clients(args.host, args.port, slots_to_connect,
                            password=ctx.password or "", time_holder=connect_time_holder)
        )

    client_thread = threading.Thread(target=run_clients, daemon=True)
    client_thread.start()
    client_thread.join(timeout=120)
    connect_ns = (connect_time_holder[0] if connect_time_holder else time.monotonic_ns()) - connect_start

    time.sleep(1.0)
    # Benchmark release_player
    print("benchmarking release")

    elapsed_ns, n_slots = benchmark_release(ctx)
    print(f"connect: {connect_ns:,}")
    print(f"release: {elapsed_ns:,}")

    # 5. Shut down, screw cleanup 
    os._exit(0)


if __name__ == "__main__":
    main()
