import os
import glob

def parse_osu_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    overall_difficulty = None
    hit_objects = []

    for line in lines:
        if line.startswith("OverallDifficulty"):
            overall_difficulty = float(line.split(":")[1].strip())
        if line.startswith("[HitObjects]"):
            hit_objects_start = lines.index(line) + 1
            hit_objects = lines[hit_objects_start:]
            break

    return overall_difficulty, hit_objects

def parse_writency_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    writency_objects = []
    for line in lines:
        parts = list(map(int, line.strip().split(',')))
        if parts[2] < parts[0]:
            parts[2] = parts[0]
        writency_objects.append(parts)

    return writency_objects

def calculate_judges(overall_difficulty, hit_objects, writency_objects):
    judge_counts = {'MAX': 0, '300': 0, '200': 0, '100': 0, '50': 0, '0': 0}

    timing_windows = {
        'MAX': 16,
        '300': 64 - 3 * overall_difficulty,
        '200': 97 - 3 * overall_difficulty,
        '100': 127 - 3 * overall_difficulty,
        '50': 151 - 3 * overall_difficulty,
        '0': 188 - 3 * overall_difficulty,
    }

    for hit_object, writency_object in zip(hit_objects, writency_objects):
        hit_time = int(hit_object.split(',')[2])
        start_time, end_time = writency_object[0], writency_object[2]

        if abs(hit_time - start_time) <= timing_windows['MAX']:
            judge_counts['MAX'] += 1
        elif abs(hit_time - start_time) <= timing_windows['300']:
            judge_counts['300'] += 1
        elif abs(hit_time - start_time) <= timing_windows['200']:
            judge_counts['200'] += 1
        elif abs(hit_time - start_time) <= timing_windows['100']:
            judge_counts['100'] += 1
        elif abs(hit_time - start_time) <= timing_windows['50']:
            judge_counts['50'] += 1
        else:
            judge_counts['0'] += 1

    return judge_counts

def calculate_accuracy(judge_counts):
    total_hits = sum(judge_counts.values())
    weighted_score = (
        judge_counts['MAX'] * 300 +
        judge_counts['300'] * 300 +
        judge_counts['200'] * 200 +
        judge_counts['100'] * 100 +
        judge_counts['50'] * 50
    )
    accuracy = (weighted_score / (total_hits * 300)) * 100 if total_hits > 0 else 0
    return round(accuracy, 2)

def process_files():
    osu_files = glob.glob('*.osu')
    for osu_file in osu_files:
        writency_file = osu_file.replace('.osu', '.writency')
        txt_file = osu_file.replace('.osu', '.txt')

        overall_difficulty, hit_objects = parse_osu_file(osu_file)
        writency_objects = parse_writency_file(writency_file)

        judge_counts = calculate_judges(overall_difficulty, hit_objects, writency_objects)
        accuracy = calculate_accuracy(judge_counts)

        with open(txt_file, 'w') as file:
            for judge, count in judge_counts.items():
                file.write(f"{judge}: {count}\n")
            file.write(f"Accuracy: {accuracy:.2f}%\n")

if __name__ == "__main__":
    process_files()
