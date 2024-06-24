import os
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
import glob
import re
import subprocess

def parse_filename(filename):
    # Parse .osu filename
    osu_match = re.match(r'(.*) - (.*) \((.*)\) \[(.*)\]\.osu', filename)
    if osu_match:
        return {
            'artist': osu_match.group(1),
            'title': osu_match.group(2),
            'difficulty': osu_match.group(4)
        }
    
    # Parse .osr filename
    osr_match = re.match(r'.*? - (.*) - (.*) \[(.*)\].*\.osr', filename)
    if osr_match:
        return {
            'artist': osr_match.group(1),
            'title': osr_match.group(2),
            'difficulty': osr_match.group(3)
        }
    
    return None

def find_matching_osr(osu_file, osr_files):
    osu_info = parse_filename(os.path.basename(osu_file))
    if not osu_info:
        return None
    
    for osr_file in osr_files:
        osr_info = parse_filename(os.path.basename(osr_file))
        if not osr_info:
            continue
        
        if (osu_info['artist'].lower() == osr_info['artist'].lower() and
            osu_info['title'].lower() == osr_info['title'].lower() and
            osu_info['difficulty'].lower() == osr_info['difficulty'].lower()):
            return osr_file
    
    return None

def parse_osu_file(file_path):
    notes = []
    with open(file_path, 'r', encoding='utf-8') as f:
        hit_objects_section = False
        for line in f:
            if line.strip() == '[HitObjects]':
                hit_objects_section = True
                continue
            if hit_objects_section:
                parts = line.strip().split(',')
                if len(parts) >= 4:
                    column = (int(parts[0]) - 36) // 73  # Convert x-coordinate to column number (0-6)
                    timestamp = int(parts[2])
                    note_type = int(parts[3])
                    notes.append((column, timestamp, note_type))
    return sorted(notes, key=lambda x: x[1])  # Sort by timestamp

def parse_lauread_file(file_path):
    keystrokes = []
    with open(file_path, 'r') as f:
        replay_data_section = False
        for line in f:
            if line.strip() == 'ReplayData:':
                replay_data_section = True
                continue
            if replay_data_section:
                parts = line.strip().split(',')
                if len(parts) == 3:
                    timestamp = int(parts[0])
                    key = int(parts[1])
                    release_time = int(parts[2])
                    keystrokes.append((timestamp, key, release_time))
    return sorted(keystrokes, key=lambda x: x[0])  # Sort by timestamp

def convert_osr_to_lauread(osr_file):
    lauread_file = os.path.splitext(osr_file)[0] + '.lauread'
    subprocess.run(['python', 'parser.py', osr_file], check=True)
    return lauread_file

def extract_difficulty(osu_file):
    difficulty = {
        'overall_difficulty': 0,
        'approach_rate': 0,
        'slider_multiplier': 0,
        'slider_tick_rate': 0,
    }
    with open(osu_file, 'r', encoding='utf-8') as f:
        difficulty_section = False
        for line in f:
            if line.strip() == '[Difficulty]':
                difficulty_section = True
                continue
            if difficulty_section:
                if line.strip() == '':
                    break
                key, value = line.strip().split(':')
                if key in difficulty:
                    difficulty[key] = float(value)
    return difficulty

def create_features(notes, difficulty):
    features = []
    for i, (column, timestamp, note_type) in enumerate(notes):
        prev_note_time = notes[i-1][1] if i > 0 else 0
        next_note_time = notes[i+1][1] if i < len(notes) - 1 else timestamp + 1000
        
        feature = {
            'column': column,
            'timestamp': timestamp,
            'note_type': note_type,
            'time_since_last_note': timestamp - prev_note_time,
            'time_to_next_note': next_note_time - timestamp,
            'relative_position': i / len(notes),
            'log_timestamp': np.log1p(timestamp),
            'overall_difficulty': difficulty['overall_difficulty'],
        }
        features.append(feature)
    return pd.DataFrame(features)

def create_target(notes, keystrokes):
    targets = []
    for note in notes:
        note_time = note[1]
        closest_keystroke = min(keystrokes, key=lambda k: abs(k[0] - note_time))
        hit_offset = closest_keystroke[0] - note_time
        release_offset = closest_keystroke[2] - closest_keystroke[0]
        targets.append((hit_offset, release_offset))
    return np.array(targets)

def train_model():
    all_features = []
    all_targets = []
    
    osu_files = glob.glob('training/*.osu')
    osr_files = glob.glob('training/*.osr')
    
    for osu_file in osu_files:
        matching_osr = find_matching_osr(osu_file, osr_files)
        if matching_osr:
            lauread_file = convert_osr_to_lauread(matching_osr)
            notes = parse_osu_file(osu_file)
            keystrokes = parse_lauread_file(lauread_file)
            difficulty = extract_difficulty(osu_file)
            
            features = create_features(notes, difficulty)
            targets = create_target(notes, keystrokes)
            
            all_features.append(features)
            all_targets.extend(targets)
        else:
            print(f"No matching .osr file found for {osu_file}")
    
    X = pd.concat(all_features, ignore_index=True)
    y = np.array(all_targets)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    hit_model = RandomForestRegressor(n_estimators=100, random_state=42)
    release_model = RandomForestRegressor(n_estimators=100, random_state=42)
    
    hit_model.fit(X_train_scaled, y_train[:, 0])
    release_model.fit(X_train_scaled, y_train[:, 1])
    
    print(f"Hit Model Score: {hit_model.score(X_test_scaled, y_test[:, 0])}")
    print(f"Release Model Score: {release_model.score(X_test_scaled, y_test[:, 1])}")
    
    return hit_model, release_model, scaler

def generate_predictions(hit_model, release_model, scaler):
    for osu_file in glob.glob('predict/*.osu'):
        notes = parse_osu_file(osu_file)
        difficulty = extract_difficulty(osu_file)
        features = create_features(notes, difficulty)
        
        X_predict = features
        X_predict_scaled = scaler.transform(X_predict)
        
        predicted_hit_offsets = hit_model.predict(X_predict_scaled)
        predicted_release_offsets = release_model.predict(X_predict_scaled)
        
        writency_file = os.path.splitext(osu_file)[0] + '.writency'
        with open(writency_file, 'w') as f:
            for (column, timestamp, _), hit_offset, release_offset in zip(notes, predicted_hit_offsets, predicted_release_offsets):
                # Ensure offsets are within realistic limits
                hit_offset = max(-200, min(200, hit_offset))  # Limit to +/- 100ms
                release_offset = max(20, min(200, release_offset))  # Limit to 20-200ms
                
                keypress_time = int(timestamp + hit_offset)
                release_time = int(keypress_time + release_offset)
                f.write(f"{keypress_time},{column},{release_time}\n")

def main():
    hit_model, release_model, scaler = train_model()
    generate_predictions(hit_model, release_model, scaler)

if __name__ == "__main__":
    main()