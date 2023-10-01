import fitparse
import pytz
import gpxpy
import plotly.graph_objs as go
import datetime
from datetime import timedelta
import plotly.express as px
import pandas as pd
import os
from flask import Flask, render_template, request, redirect, url_for
from flask_caching import Cache
from werkzeug.utils import secure_filename
import json

# Create the Flask app
app = Flask(__name__)
# Configure cache
app.config['CACHE_TYPE'] = 'simple'

# Create the cache instance
cache = Cache(app)


start_time = None  # Define start_time here
LOCAL_TIMEZONE = pytz.timezone('Europe/Paris')
UTC = pytz.timezone('UTC')
AGGREGATE_BREAKS = 5  # aggregate stops within N minutes
MIN_BREAK_DURATION = 0.5  # minimum stop duration to be considered as a stop
DEFAULT_ELEVATION_GAIN = 51 #ft/mile
BREAK_DURATION_DISP_THRESHOLD = 360 #seconds
FIRST_HALF_TIME = (timedelta(hours=40, minutes=19).total_seconds() / 3600) #hours
SECOND_HALF_TIME = (timedelta(hours=49, minutes=50).total_seconds() / 3600) #hours
FIRST_HALF_DIST = 377.5 #miles
SECOND_HALF_DIST = 385 #miles
CONTROL_DIST_MARGIN_OF_ERROR = 5 #miles

# Define the folder where uploaded files will be stored
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create the uploads folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

control_stops = []
stages = []
planned = []

# stages = [0 - stage_id, 1 - start_control_id, 2 - end_control_id, 3 - stage_cutoff, 4 - stage_distance,
#           5 - elevation_gain, 6 - profile, 7 - elevation_difficulty, 8 - end_distance]
# planned = [0 - stage_id, 1 - moving_time, 2 - total_micro_breaks, 3 - control_break, 4 - elapsed_stage_time,
#           5 - elapsed_stage_time_after_control, 6 - speed, 7 - total_distance]
# actual = [0 - stage_id, 1 - moving_time, 2 - total_micro_breaks, 3 - control_break, 4 - elapsed_stage_time,
#           5 - elapsed_stage_time_after_control, 6 - speed, 7 - total_distance]
# control_stops = [0 - control_id, 1 - control_name, 2 - control_distance]
# actual_elapsed_stream = [0 - timestamp, 1 - distance, 2 - speed]
# actual_breaks = [0 - start_timestamp, 1 - end_timestamp, 2 - distance_marker, 3 - break_duration, 4 - tag]
# actual_merged_stage_breaks = [0 - start_timestamp, 1 - end_timestamp, 2 - distance_marker, 3 - break_duration, 4 - tag, 5 - stage_id]



# Define control stops and plan as a list of tuples (0 - distance, 1- control_name, 2- cutoff_time, 3- elevation,
#                                                   4 - moving_time, 5 - total_micro_breaks, 6 - control_break)
INPUT_DATA = [
    (0, 'Rambouillet', '0:00:00', 0, '0:00:00', '0:00:00', '0:00:00'),
    (74.5, 'Mortagne-Au-Perche', '7:58:00', 3780, '6:09:00', '0:00:00', '0:20:00'),
    (126, 'Villaines-La-Juhel', '13:29:00', 2172, '4:08:00', '0:00:00', '0:30:00'),
    (181.5, 'Fougeres', '19:26:00', 2490, '4:35:00', '0:00:00', '0:30:00'),
    (219.7, 'Tinteniac', '23:29:00', 1463, '3:06:00', '0:00:00', '0:30:00'),
    (235.5, 'Quedillac', '25:15:00', 804, '1:23:00', '0:00:00', '0:15:00'),
    (271.9, 'Loudeac', '29:04:00', 2028, '3:04:00', '0:00:00', '0:45:00'),
    (301, 'St Nicolas-Du-Pelem', '32:10:00', 1936, '2:45:00', '0:00:00', '4:00:00'),
    (321.5, 'Carhaix', '34:18:00', 886, '1:52:00', '0:00:00', '0:30:00'),
    (377.7, 'Brest', '40:19:00', 3002, '5:19:00', '0:00:00', '0:45:00'),
    (435.5, 'Carhaix', '48:04:00', 4298, '6:01:00', '0:00:00', '0:30:00'),
    (456, 'Gouarec', '50:47:00', 1240, '2:05:00', '0:00:00', '0:15:00'),
    (488.6, 'Loudeac', '55:10:00', 2126, '3:11:00', '0:00:00', '3:20:00'),
    (526, 'Quedillac', '59:49:00', 1909, '3:29:00', '0:00:00', '0:30:00'),
    (542, 'Tinteniac', '61:45:00', 545, '1:29:00', '0:00:00', '0:30:00'),
    (580, 'Fougeres', '66:25:00', 1598, '3:33:00', '0:00:00', '0:45:00'),
    (635.7, 'Villaines-La-Juhel', '73:21:00', 3133, '5:19:00', '0:00:00', '0:45:00'),
    (686.4, 'Mortagne-Au-Perche', '80:07:00', 2349, '4:47:00', '0:00:00', '3:30:00'),
    (734.3, 'Dreux', '86:32:00', 2100, '4:45:00', '0:00:00', '0:45:00'),
    (762.5, 'Rambouillet', '90:00:00', 1158, '2:29:00', '0:00:00', '0:00:00')
]

def calculate_stages_plan():

    elapsed_stage_time = timedelta(seconds=0)
    elapsed_stage_time_after_control = timedelta(seconds=0)

    for i in range(len(INPUT_DATA)):
        start = INPUT_DATA[i]
        control_stops.append((i, start[1], start[0]))
        if(i<len(INPUT_DATA)-1):
            end = INPUT_DATA[i + 1]
            dist = end[0]-start[0]
            elev_gain = end[3]
            profile = elev_gain/dist
            elevation_difficulty = profile / DEFAULT_ELEVATION_GAIN
            stages.append((i, i, i+1, end[2], dist, elev_gain, profile, elevation_difficulty, end[0]))

            elapsed_stage_time = elapsed_stage_time_after_control + timedelta(hours=parse_control_time(INPUT_DATA[i + 1][4])) + timedelta(hours=parse_control_time(INPUT_DATA[i + 1][5]))
            elapsed_stage_time_after_control = elapsed_stage_time + timedelta(hours=parse_control_time(INPUT_DATA[i + 1][6]))
            t = datetime.strptime(INPUT_DATA[i + 1][4], "%H:%M:%S")
            delta = timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
            speed = dist/(delta.total_seconds() / 3600.0)
            planned.append((i, INPUT_DATA[i + 1][4], INPUT_DATA[i + 1][5], INPUT_DATA[i + 1][6], elapsed_stage_time, elapsed_stage_time_after_control, speed, end[0]))


    return control_stops, stages, planned

def parse_fit_file(file_path):

    actual = []
    actual_elapsed_stream = []
    actual_breaks = []
    actual_merged_stage_breaks = []

    global start_time  # Declare start_time as a global variable
    start_time = None  # Initialize the start_time variable
    speed = None  # Initialize the speed variable
    distances = []
    elapsed_times = []
    banked_times = []
    banked_colors = []

    with open(file_path, 'rb') as fit_file:
        fitfile = fitparse.FitFile(fit_file)
        prev_timestamp = None
        stop_start_time = None
        prev_distance = 0

        for record in fitfile.get_messages('record'):
            timestamp = None
            distance = None
            banked_time = None

            for record_data in record:
                if record_data.name == 'timestamp':
                    timestamp = record_data.value
                    timestamp = UTC.localize(timestamp)
                    timestamp = timestamp.astimezone(LOCAL_TIMEZONE)
                elif record_data.name == 'distance':  # Added for distance
                    distance = record_data.value / 1609.34  # Convert meters to miles
                elif record_data.name == 'speed':
                    speed = record_data.value * 2.23694  # Convert m/s to mph

            if timestamp is not None:
                if start_time is None:
                    start_time = timestamp

                if distance is not None:  # Check if distance is not None
                    elapsed_time = (timestamp - start_time).total_seconds() / 3600.0  # Convert to hours
                    distances.append(distance)  # Store from the record
                    elapsed_times.append(elapsed_time)  # Store from the record
                    #Store banked time: time needed for 377.7 is 40 hours. for the remaining 385 is 50 hours
                    if distance <= FIRST_HALF_DIST:
                        banked_time = ((FIRST_HALF_TIME * distance) / FIRST_HALF_DIST) - elapsed_time
                        if banked_time<0:
                            banked_colors.append('red')
                        else:
                            banked_colors.append('green')
                    else:
                        banked_time = (FIRST_HALF_TIME + ((SECOND_HALF_TIME) * (distance - FIRST_HALF_DIST)) / SECOND_HALF_DIST) - elapsed_time
                        if banked_time<0:
                            banked_colors.append('red')
                        else:
                            banked_colors.append('green')

                    actual_elapsed_stream.append((elapsed_time, distance, speed, banked_time, banked_colors))  # Store in the stream array
                    banked_times.append(banked_time)


                if prev_timestamp is not None:
                    time_difference = timestamp - prev_timestamp
                    dist_difference = distance - prev_distance
                    speed = dist_difference / (time_difference.total_seconds() / 3600.0)  # Calculate speed
                    # Check for the condition (time difference > 1 minute or speed < 2 mph)
                    if ((time_difference >= timedelta(minutes=1)) or (speed is not None and speed < 2.0)):
                        if stop_start_time is None:
                            stop_start_time = prev_timestamp
                    else:
                        # If the conditions are not met, end the stop time
                        if stop_start_time is not None:
                            stop_end_time = prev_timestamp
                            stop_duration = stop_end_time - stop_start_time
                            if(stop_duration.total_seconds() >= MIN_BREAK_DURATION * 60):  # Include stops that are min_stop_duration minutes or longer
                                actual_breaks.append((stop_start_time, stop_end_time, distance, stop_duration, ''))
                                #print(f'Break: {len(actual_breaks)}, actual_stream.idx: {len(actual_elapsed_stream)}, start {stop_start_time}, end: {stop_end_time}, duration: {stop_duration}, elapsed_time {elapsed_time}, distance: {distance}, speed: {speed}, banked_time: {banked_time}')
                            stop_start_time = None

                prev_timestamp = timestamp
                prev_distance = distance

    actual_merged_stage_breaks, total_break_time = merge_breaks(actual_breaks, control_stops, stages)

    return actual_elapsed_stream, distances, elapsed_times, banked_times, banked_colors, actual_breaks, actual_merged_stage_breaks, total_break_time

def parse_control_time(control_time_str):
    hours, minutes, seconds = map(int, control_time_str.split(':'))
    total_hours = hours + minutes / 60 + seconds / 3600
    return total_hours

def format_time(time):
    hours, remainder = divmod(time.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    if time.days > 0:
        return f'{time.days * 24 + hours:02d}:{minutes:02d}'
    else:
        return f'{hours:02d}:{minutes:02d}'

def format_time_float(time):
    hours = int(time)
    minutes = int((time - hours) * 60)

    if hours > 24:
        return f'24 hours {minutes} minutes'
    elif hours > 0:
        return f'{hours} hours {minutes} minutes'
    else:
        return f'{minutes} minutes'

def merge_breaks(actual_breaks, control_stops, stages):
    merged_breaks = []
    current_start = None
    current_end = None
    total_break_time = timedelta(seconds=0)  # Initialize total stopped time
    ctrl_idx = 0
    stg_idx = 0

    for i in range(0, len(actual_breaks)):
        actual_break = actual_breaks[i]
        start, end, distance, duration, tag = actual_break

        if current_start is None:
            current_start = start
            current_end = end
        else:

            if duration.total_seconds() >= MIN_BREAK_DURATION * 60:  # Include stops that are min_stop_duration minutes or longer

                for stop in control_stops:
                    control_id, control_name, control_distance = stop
                    if distance < control_distance+CONTROL_DIST_MARGIN_OF_ERROR:
                        ctrl_idx = control_id
                        if abs(control_distance - distance) <= CONTROL_DIST_MARGIN_OF_ERROR:
                            tag = 'control'
                        else:
                            tag = 'micro'
                        break

                for stage in stages:
                    stage_id, start_control_id, end_control_id, *_ = stage
                    if ctrl_idx == end_control_id:
                        stg_idx = stage_id
                        break

                merged_breaks.append((current_start, current_end, distance, duration, tag, stg_idx))
                #print(f'merged break {len(merged_breaks)}: start {current_start}, end: {current_end}, break_duration: {duration}, distance: {distance}, tag: {tag}, stage: {stg_idx}')
                total_break_time += duration  # Add the current stop duration to total stopped time

                current_start = start
                current_end = end

    return merged_breaks, total_break_time


def calculate_stages_actual(actual_elapsed_stream, stages, control_stops, actual_merged_stage_breaks, distances, elapsed_times):
    actual = []
    elapsed_stage_time = timedelta(seconds=0)
    elapsed_stage_time_after_control = timedelta(seconds=0)

    for i in range(len(stages)):
        stage_id, start_control_id, end_control_id, stage_cutoff, stage_distance, \
            elevation_gain, profile, elevation_difficulty, end_distance = stages[i]

        start_distance = end_distance - stage_distance
        #control_stops[start_control_id][2]
        #end_distance = control_stops[end_control_id][2]
        # Find the closest recorded distances to the control points
        closest_end_distance = min(distances, key=lambda x: abs(x - (end_distance + CONTROL_DIST_MARGIN_OF_ERROR)))
        if(i == 0):
            closest_start_distance = min(distances, key=lambda x: abs(x - (start_distance)))
        else:
            closest_start_distance = min(distances, key=lambda x: abs(x - (start_distance + CONTROL_DIST_MARGIN_OF_ERROR)))

        # Find the closest elapsed times to the control points
        closest_start_time = elapsed_times[distances.index(closest_start_distance)]
        closest_end_time = elapsed_times[distances.index(closest_end_distance)]


        # Convert elapsed time to a datetime object
        closest_start_datetime = start_time + timedelta(hours=closest_start_time)
        closest_end_datetime = start_time + timedelta(hours=closest_end_time)

        total_elapsed_time = closest_end_datetime - closest_start_datetime  # Calculate total elapsed time between control stops

        # Calculate total stop time between control stops
        total_break_between_controls = timedelta(seconds=0)
        total_break_at_controls = timedelta(seconds=0)

        for actual_merged_break in actual_merged_stage_breaks:
            start, end, distance, duration, tag, brk_stage_id = actual_merged_break
            if ((stage_id == brk_stage_id) and (tag == 'micro')):
                total_break_between_controls += duration
            if ((stage_id == brk_stage_id) and (tag == 'control')):
                total_break_at_controls += duration

        total_moving_time = total_elapsed_time - (total_break_between_controls + total_break_at_controls)  # Calculate total moving time between control stops

        elapsed_stage_time = elapsed_stage_time_after_control + total_moving_time + total_break_between_controls
        elapsed_stage_time_after_control = elapsed_stage_time + total_break_at_controls

        # Calculate speed
        distance_between_controls = closest_end_distance - closest_start_distance
        if(total_moving_time.total_seconds() > 0):
            speed_between_controls = distance_between_controls / (total_moving_time.total_seconds() / 3600.0)

        print(f'stage: {stage_id}, break between controls: {total_break_between_controls}, break at control: {total_break_at_controls}, moving time: {total_moving_time}, elapsed_stage_time: {elapsed_stage_time}, elapsed_stage_time_after_control: {elapsed_stage_time_after_control}, distance_between_controls: {distance_between_controls}, speed_between_controls: {speed_between_controls}')
        #print(f'closest_start_distance: {closest_start_distance}, closest_end_distance: {closest_end_distance}, closest_start_time: {closest_start_time}, closest_end_time: {closest_end_time}')
        actual.append((stage_id, total_moving_time, total_break_between_controls, total_break_at_controls, elapsed_stage_time, elapsed_stage_time_after_control, speed_between_controls, closest_end_distance))
    return actual

from plotly.subplots import make_subplots
from datetime import datetime

def extract_from_planned_actual(planned, actual, stages):
    plan_x = [0]
    plan_y = [0]
    dist_act = []
    time_diff_act = []
    color_act = []
    labels = []
    breaks_dist = []

    # data for planned vs actual moving times and planned vs actual breaks
    planned_moving_times = [0]
    actual_moving_times = [0]

    planned_breaks = []
    actual_breaks = []
    total_planned_breaks = timedelta(seconds=0)
    total_planned_moving_time = timedelta(seconds=0)


    for c in planned:
        plan_x.append(c[7])
        plan_x.append(c[7])
        plan_y.append((c[4]).total_seconds()/3600)
        plan_y.append((c[5]).total_seconds()/3600)

    for i in range(len(actual)):
        time_diff = timedelta(hours=parse_control_time(stages[i][3])) - actual[i][4]
        if time_diff.total_seconds() > 0:
            color = 'green'
        else:
            color = 'red'
        dist_act.append(actual[i][7])
        time_diff_act.append(time_diff.total_seconds()/3600)
        color_act.append(color)
        labels.append(f'{time_diff} ({actual[i][7]:.1f} miles)')
        planned_moving_times.append(timedelta(hours=parse_control_time(planned[i][1])).total_seconds()/3600)
        actual_moving_times.append((actual[i][1]).total_seconds()/3600)
        planned_breaks.append(timedelta(hours=parse_control_time(planned[i][2])).total_seconds()/3600)
        planned_breaks.append(timedelta(hours=parse_control_time(planned[i][3])).total_seconds()/3600)
        actual_breaks.append((actual[i][2]).total_seconds()/3600)
        actual_breaks.append((actual[i][3]).total_seconds()/3600)
        total_planned_breaks += timedelta(hours=parse_control_time(planned[i][2])) + timedelta(hours=parse_control_time(planned[i][3]))
        total_planned_moving_time += timedelta(hours=parse_control_time(planned[i][1]))
        breaks_dist.append(stages[i][8] - stages[i][4]/2)
        breaks_dist.append(stages[i][8])

    return plan_x, plan_y, \
           dist_act, time_diff_act, color_act, labels, \
           planned_moving_times, actual_moving_times, \
           planned_breaks, actual_breaks, breaks_dist, \
           total_planned_breaks, total_planned_moving_time

# Function to generate hex color codes based on the condition
def get_line_color(value):
    return '#FF0000' if value < 0 else '#00FF00'

def display_graphs(fig, control_stops, stages):
    # Create a list of annotations
    annotations = []
    control_dist = []

    # Add annotations for control stops
    for i in range(len(control_stops)):
        _, control_name, control_distance = control_stops[i]
        control_time = "0:00:00"
        control_dist.append(control_distance)

        for stage in stages:
            _, _, end_control_id, stage_cutoff, *_ = stage
            if i == end_control_id:
                control_time = stage_cutoff
                break
        # Find the closest recorded distance to the control point
        control_cutoff_time = parse_control_time(control_time)

        #Row1: Control name annotations at bottom. x1y1
        annotations.append(
            go.layout.Annotation(
                x=control_distance,
                y=-3,
                text=f'{control_name}',
                showarrow=False,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor='black',
                opacity=1,
                font=dict(size=10),
                align='center',
                valign='bottom',
                xref="x1",
                yref="y1",
                textangle = -90
            )
        )
    fig.update_xaxes(showticklabels=True) # show all the xticks

    fig.update_layout(
        title={
            'text': 'Paris Brest Paris 2023 - Team Asha. Banked Time Comparison',
            'xanchor': 'center',
            'yanchor': 'top',
            'y':0.9,
            'x':0.5,
        },
        width=2400,
        height=1200,
        xaxis=dict(title='Distance (miles)'),
        yaxis=dict(title='Elapsed Time (hours)'),
        annotations=annotations,
    )

    fig.show()



def plot_line_graph(fig, name, color, distances, banked_times):

    # Row 1: x1, y1. Also using y2 for some reason.
    # Create a line chart for banked time
    trace_banked_time = go.Scatter(
        x=distances,
        y=banked_times,
        mode='lines',
        name=name,
        showlegend=True,
        line=dict(color=color, width=1.5),  # Set line color and width
    )
    # Banked time line trace
    fig.add_trace(trace_banked_time)


@app.route('/')
def upload_file():
    #uploaded_files = os.listdir(app.config['UPLOAD_FOLDER'])
    #print(f'Initial Uploaded files: {uploaded_files}')
    #uploaded_files.remove('.DS_Store')
    #print(f'After removing 0th element Uploaded files: {uploaded_files}')

    #return render_template('uploaded_files.html', uploaded_files=uploaded_files)
    return redirect('/uploaded_files')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    uploaded_files = os.listdir(app.config['UPLOAD_FOLDER'])
    print(f'Initial Uploaded files: {uploaded_files}')
    uploaded_files.remove('.DS_Store')
    print(f'After removing 0th element Uploaded files: {uploaded_files}')

    if request.method == 'POST':
        # Handle file upload if it's a POST request
        if 'file' not in request.files:
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)

        if file and file.filename != '.DS_Store':
            # Get the athlete's name from the form
            athlete_name = request.form.get('athlete_name')
            # Create a dictionary to store metadata
            metadata = {
                'athlete_name': athlete_name,
                'file_name': file.filename,
                }

            file.metadata = metadata
            filename = secure_filename(file.filename)
            metadata_filename = filename + ".json"

            # Save the metadata as a separate JSON file
            with open(os.path.join(app.config['UPLOAD_FOLDER'], metadata_filename), 'w') as metadata_file:
                json.dump(metadata, metadata_file)

            # Save the uploaded file with its original filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            print(f'Uploaded file: {file}')

        # Update the list of uploaded files after saving the new file
        uploaded_files = os.listdir(app.config['UPLOAD_FOLDER'])

    print(f'Uploaded files: {uploaded_files}')
    return render_template('upload.html', uploaded_files=uploaded_files)

@app.route('/uploaded_files', methods=['GET', 'POST'])
def uploaded_files():
    uploaded_files = os.listdir(app.config['UPLOAD_FOLDER'])
    print(f'Initial Uploaded files: {uploaded_files}')
    uploaded_files.remove('.DS_Store')
    new_uploaded_files = [dc for dc in uploaded_files if 'json' not in dc]
    print(f'After removing 0th element and json files: {new_uploaded_files}')
    # Retrieve metadata for selected files
    metadata_list = []
    for filename in new_uploaded_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        metadata_filename = filename + ".json"
        metadata_file_path = os.path.join(app.config['UPLOAD_FOLDER'], metadata_filename)
        # Check if the metadata file exists
        if os.path.exists(metadata_file_path):
            with open(metadata_file_path, 'r') as metadata_file:
                metadata = json.load(metadata_file)
                metadata_list.append(metadata)
                print(f'metadata: {metadata}')
        else:
            metadata_list.append({})  # No metadata found

    return render_template('uploaded_files.html', selected_files=new_uploaded_files, metadata_list=metadata_list)

@app.route('/show_results', methods=['POST'])
def show_results():

    selected_files = request.form.getlist('selected_files')
    # Create a dictionary to hold the data for the selected files
    data_for_selected_files = {}
    # Extract control names and distances from the control_stops array
    control_names = [control[1] for control in control_stops]
    control_distances = [control[2] for control in control_stops]

    # Check if the data is already cached
    cached_data = cache.get('data_for_selected_files')
    if cached_data:
        data_for_selected_files = cached_data
    else:
        load_data_into_cache()

    return render_template('results.html', selected_files=selected_files, data=data_for_selected_files, control_names=control_names, control_distances=control_distances)

# Function to clear cache when the server restarts
def clear_cache_on_start():
    cache.clear()
    print("Cache cleared on server start")

# Function to load data from uploaded files and store it in cache
def load_data_into_cache():
    selected_files = os.listdir(app.config['UPLOAD_FOLDER'])
    data_for_selected_files = {}
    selected_files.remove('.DS_Store')
    new_selected_files = [dc for dc in selected_files if 'json' not in dc]
    print(f'Loading data for {new_selected_files}')
    for file in new_selected_files:
        if (file != '.DS_Store'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
            if os.path.exists(file_path):
                # Load data from the file and format it as needed
                # Example: actual_elapsed_stream, distances, banked_times = parse_fit_file(file_path)
                actual_elapsed_stream, distances, elapsed_times, banked_times, _, _, actual_merged_stage_breaks, _ = parse_fit_file(file_path)
                data_for_selected_files[file] = {'distances': distances, 'banked_times': banked_times}
            else:
                data_for_selected_files[file] = {'distances': [], 'banked_times': []}  # Handle file not found
            print(f'Loaded data for {file_path}')


    # Store the data in the cache
    cache.set('data_for_selected_files', data_for_selected_files)

if __name__ == '__main__':
    # Clear the cache when the server starts
    #clear_cache_on_start()
    # Check if the cache is empty when the server starts
    if cache.get('data_for_selected_files') is None:
        load_data_into_cache()

    # Register the clear_cache_on_restart function to run before the first request
    app.run(debug=True, use_reloader=False, threaded=True, port=5000)

