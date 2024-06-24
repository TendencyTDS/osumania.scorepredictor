import sys
import os
from osrparse import Replay, GameMode
from datetime import datetime
from typing import List, Tuple

def expand_key_events(events: List[Tuple[int, int]]) -> List[Tuple[int, int, int]]:
    expanded_events = []
    current_time = 0
    active_keys = {}  # Dictionary to store the press time of each active key

    for time_delta, keys in events:
        current_time += time_delta
        new_keys = set(i+1 for i in range(7) if keys & (1 << i))
        
        # Handle key releases
        for key in set(active_keys.keys()) - new_keys:
            expanded_events.append((active_keys[key], key, current_time))
            del active_keys[key]
        
        # Handle key presses
        for key in new_keys - set(active_keys.keys()):
            active_keys[key] = current_time

    # Handle any remaining active keys at the end
    for key, press_time in active_keys.items():
        expanded_events.append((press_time, key, current_time))

    return expanded_events

def write_replay_to_mlrc(replay: Replay, output_path: str):
    with open(output_path, 'w') as f:
        f.write(f"Mode: {replay.mode.name}\n")
        f.write(f"Version: {replay.game_version}\n")
        f.write(f"BeatmapHash: {replay.beatmap_hash}\n")
        f.write(f"Player: {replay.username}\n")
        f.write(f"ReplayHash: {replay.replay_hash}\n")
        f.write(f"300s: {replay.count_300}\n")
        f.write(f"100s: {replay.count_100}\n")
        f.write(f"50s: {replay.count_50}\n")
        f.write(f"Gekis: {replay.count_geki}\n")
        f.write(f"Katus: {replay.count_katu}\n")
        f.write(f"Misses: {replay.count_miss}\n")
        f.write(f"Score: {replay.score}\n")
        f.write(f"MaxCombo: {replay.max_combo}\n")
        f.write(f"Perfect: {replay.perfect}\n")
        f.write(f"Mods: {replay.mods.value}\n")
        
        # Extract the first timestamp from LifeBarGraph
        initial_offset = 0
        if replay.life_bar_graph:
            initial_offset = int(replay.life_bar_graph[0].time)
        
        f.write(f"LifeBarGraph: {','.join([f'{state.time}|{state.life}' for state in replay.life_bar_graph]) if replay.life_bar_graph else 'None'}\n")
        f.write(f"Timestamp: {replay.timestamp.isoformat()}\n")
        f.write(f"ReplayID: {replay.replay_id}\n")
        f.write(f"RNGSeed: {replay.rng_seed if replay.rng_seed is not None else 'None'}\n")
        f.write("ReplayData:\n")

        events = []
        for event in replay.replay_data:
            if event.time_delta < 0:
                continue
            events.append((event.time_delta, event.keys.value))

        expanded_events = expand_key_events(events)

        # Sort events by hit time, then by key number
        expanded_events.sort(key=lambda x: (x[0], x[1]))

        if expanded_events:
            first_hit_time = expanded_events[0][0]
            time_adjustment = first_hit_time - initial_offset

            # Write the first event with the initial_offset as hit time
            hit_time, key, release_time = expanded_events[0]
            adjusted_release_time = max(initial_offset, release_time - time_adjustment)
            f.write(f"{initial_offset},{key},{adjusted_release_time}\n")

            # Adjust timestamps for the rest of the events
            for hit_time, key, release_time in expanded_events[1:]:
                adjusted_hit_time = max(initial_offset, hit_time - time_adjustment)
                adjusted_release_time = max(initial_offset, release_time - time_adjustment)
                f.write(f"{adjusted_hit_time},{key},{adjusted_release_time}\n")

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_osr_file>")
        sys.exit(1)

    osr_path = sys.argv[1]
    if not os.path.exists(osr_path):
        print(f"Error: File '{osr_path}' does not exist.")
        sys.exit(1)

    if not osr_path.lower().endswith('.osr'):
        print("Error: The input file must have a .osr extension.")
        sys.exit(1)

    try:
        replay = Replay.from_path(osr_path)
    except Exception as e:
        print(f"Error reading the .osr file: {e}")
        sys.exit(1)

    mlrc_path = os.path.splitext(osr_path)[0] + '.lauread'
    write_replay_to_mlrc(replay, mlrc_path)
    print(f"Successfully created {mlrc_path}")

if __name__ == "__main__":
    main()