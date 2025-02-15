import argparse
import io
import os
import shutil
import time
import zipfile
from collections import defaultdict
from os import makedirs, walk
from os.path import join, isdir, dirname, realpath
from re import sub, split
from shutil import copyfile

import requests
from tqdm import tqdm


def format_file_name(f):  # formats file name to ASCII
    name = "".join(f.split('.')[:-1]).lower()  # lowercase; splits by period; removes extension
    formatted = sub('[^a-z0-9-_ ]', '', name)  # ignores special characters, except - and _
    return sub(' ', '_', formatted)  # replaces whitespace with _


def output_file(file_name, step_dict, output_dir):  # outputs results to file text
    ofile = file_name + '.txt'

    # pre-generate output data
    title = 'TITLE %s\n' % step_dict['title']
    bpm = 'BPM %s\n' % str(int(step_dict['bpm']))

    note_data = ''
    for difficulty in step_dict['notes'].keys():
        note_data = 'DIFFICULTY %s\n' % difficulty
        note_data += 'NOTES\n'
        for note in step_dict['notes'][difficulty]:
            note_data += note + '\n'

    with open(join(output_dir, ofile), 'w') as f:
        f.write(''.join((title, bpm, note_data)))


# ===================================================================================================

def convert_note(line):
    return sub('4', '1', sub('[MKLF]', '0', line))  # replaces extra notes: M, K, L, F; replaces 4 note


# ===================================================================================================

# BPM       = beats/minute -> BPS = beats/second = BPM/60
# measure   = 4 beats = 4 * 1/4th notes     = 1 note
# 1/256    -> 256 * 1/256th notes           = 1 measure

def calculate_timing(measure, measure_index, bpm, offset):  # calculate time in seconds for each line
    measure_seconds = 4 * 60 / bpm  # length of measure in seconds
    note_256 = measure_seconds / 256  # length of each 1/256th note in the measure in seconds
    measure_timing = measure_seconds * measure_index  # accumulated time from previous measures
    fraction_256 = 256 / len(measure)  # number of 1/256th notes per beat: 1/2nd = 128, 1/4th = 64, etc
    # combines note and its timing, if the note exists
    note_and_timings = [measure[i] + ' ' + str(i * note_256 * fraction_256 + measure_timing - offset) for i, is_set in
                        enumerate(measure) if is_set != None]

    return note_and_timings


def parse_sm(sm_file):
    step_dict = defaultdict(list)
    step_dict['notes'] = defaultdict(list)  # notes are paired with each difficulty
    current_difficulty = ''
    measure = []
    measure_index = 0

    read_notes = False

    with open(sm_file, encoding='ascii', errors='ignore') as f:
        read_values = ''  # contains combined data while not reading notes; structured '#type:data;'
        for line in f:
            line = line.rstrip()  # removes trailing newline '\n' and possible trailing whitespace
            if not read_notes:
                if line.startswith('#NOTES:'):
                    read_notes = True
                else:
                    read_values += line
                    if read_values.endswith(';'):  # begin processing read_values for data
                        metadata = read_values.lstrip('#').rstrip(';').split(
                            ':')  # removes extra characters; splits name from values
                        data_name = metadata[0]
                        data_value = ':'.join(metadata[1:])
                        if data_name == 'TITLE':
                            step_dict['title'] = data_value
                        elif data_name == 'BPMS':
                            if ',' in data_value:  # raises Exception if multiple BPMS detected
                                raise ValueError('Multiple BPMs detected')
                            step_dict['bpm'] = float(split('=', data_value)[-1])  # removes time to get bpm
                        elif data_name == 'STOPS' and data_value:
                            raise ValueError('Stop detected')
                        elif data_name == 'OFFSET':
                            step_dict['offset'] = float(data_value)
                        read_values = ''

            if read_notes:  # start of note processing
                if line.startswith('#NOTES:'):  # marks the beginning of each difficulty and its notes
                    measure_index = 0
                    next(f)
                    next(f)
                    current_difficulty = next(f).lstrip(' ').rstrip(':\n')  # difficulty always found 3 lines down
                elif line.startswith((',', ';')):  # marks the end of each measure
                    notes_and_timings = calculate_timing(measure, measure_index, step_dict['bpm'], step_dict['offset'])
                    step_dict['notes'][current_difficulty].extend(notes_and_timings)
                    measure.clear()
                    measure_index += 1
                elif line and not line.startswith(' '):  # individual notes
                    note = convert_note(line)
                    if note[0].isdigit():
                        note_placed = True if any((c in set('123456789')) for c in note) else False
                        if note_placed:
                            measure.append(note)  # adds note if found
                        else:
                            measure.append(None)

    return step_dict


# ===================================================================================================

def parse(input_dir, output_dir):
    for root, dirs, files in walk(input_dir):
        sm_files = [file for file in files if file.endswith('.sm')]
        ogg_files = [file for file in files if file.endswith('.ogg')]

        format_ogg_dict = dict(zip([format_file_name(ogg) for ogg in ogg_files], range(len(ogg_files))))

        for sm_file in sm_files:
            new_file = format_file_name(sm_file)
            if new_file in format_ogg_dict:
                try:
                    sm_data = parse_sm(join(root, sm_file))
                    # write sm text data to output dir
                    output_file(new_file, sm_data, output_dir)
                    # move and rename .ogg file to output dir
                    copyfile(join(root, ogg_files[format_ogg_dict[new_file]]), join(output_dir, new_file + '.ogg'))
                except Exception as ex:
                    print('Write failed for %s: %r' % (sm_file, ex))

                # ===================================================================================================


def upload_and_get_sm(dir: str, file_name: str, song_title: str, song_artist='', local: bool = True,
                      difficulty: str = "Medium"):
    target_path = os.path.join(dir, file_name.replace('.mp3', '.sm'))
    if os.path.exists(target_path):
        print('File %s.sm already exists, no need to generate' % file_name.replace('.mp3', ''))
        return

    url = 'https://ddc.chrisdonahue.com/choreograph' if not local else 'http://localhost:8080/choreograph'
    path = os.path.join(dir, file_name)
    files = {'audio_file': open(path, 'rb')}
    data = {'song_artist': song_artist, 'song_title': song_title, 'diff_coarse': difficulty}
    r = requests.post(url=url, data=data, files=files)

    zip_file_path = os.path.join('./tmp', file_name.replace('.mp3', ''))
    z = zipfile.ZipFile(io.BytesIO(r.content))
    z.extractall(zip_file_path)

    for member in tqdm(z.infolist(), desc='Extracting files for %s' % file_name):
        try:
            z.extract(member, zip_file_path)
        except zipfile.error as e:
            print(e)

    # 'tmp/qunqing.zip/DanceDanceConvolutionV1'
    tmp_path = os.path.join(zip_file_path, 'DanceDanceConvolutionV1')
    tmp_path = os.path.join(tmp_path, os.listdir(tmp_path)[0])

    sm_file_name = [name for name in os.listdir(tmp_path) if name.endswith(".sm")][0]
    sm_file_path = os.path.join(tmp_path, sm_file_name)
    os.rename(sm_file_path, target_path)


if __name__ == '__main__':
    start_time = time.time()
    dir = dirname(realpath(__file__))
    parser = argparse.ArgumentParser(description='Parser')
    parser.add_argument('--input', default='parseIn', help='Provide an input folder (default: parseIn)')
    parser.add_argument('--output', default='parseOut', help='Provide an output folder (default: parseOut)')

    args = parser.parse_args()
    input_dir = join(dir, args.input)
    output_dir = join(dir, args.output)
    if not os.path.exists("tmp"):
        os.mkdir("tmp")
    for root, _, files in os.walk(input_dir, topdown=False):
        for name in files:
            if name.endswith(".mp3"):
                upload_and_get_sm(root, name, name.replace('.mp3', ''))
                path = os.path.join(root, name)
                os.rename(path, path.replace(".mp3", ".ogg"))

    for root, dirs, files in os.walk('tmp'):
        for name in files:
            print("removing", os.path.join(root, name))
            os.remove(os.path.join(root, name))
        for name in dirs:
            print("removing", os.path.join(root, name))
            shutil.rmtree(os.path.join(root, name))
    os.rmdir('./tmp')

    if not isdir(input_dir):
        print("Invalid input directory argument.")
    else:
        if not isdir(output_dir):
            print("Output directory missing: %s\nGenerated specified output folder." % args.output)
            makedirs(output_dir)
        parse(input_dir, output_dir)

    end_time = time.time()

    print("Elapsed time was %g seconds" % (end_time - start_time))
