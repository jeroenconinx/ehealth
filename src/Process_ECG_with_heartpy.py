import influxdb_client
import os
import time
import pandas as pd
import matplotlib.pyplot as plt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timedelta
import heartpy as hp

import Preferences

client = influxdb_client.InfluxDBClient(url=Preferences.url, token=Preferences.token, org=Preferences.org)

bucket = "ECG"

start_time = "2023-11-20T13:40:00.000Z"
stop_time = "2023-11-20T13:50:00.000Z"
counter = 0

query_api = client.query_api()

while counter < 6:
    #(start: 2023-11-19T16:00:00Z, stop:2023-11-19T16:10:00Z) (start: -5m)
    query = """from(bucket: "ECG")
      |> range(start: {}, stop: {})
      |> filter(fn: (r) =>
        r._measurement == "wifi_status" and
        r._field == "ecg_value"
      )
      |> window(every: 1m)  // Retrieve data in 10-minute intervals
      """.format(start_time,stop_time)

    tables = query_api.query(query, org="Uhasselt")

    data_points = []
    
    for table in tables:
        for record in table.records:
            # Extracting time, field, and value from the record
            data_points.append((record.get_time(), record.get_field(), record.get_value()))

    # Create a pandas DataFrame
    df = pd.DataFrame(data_points, columns=["Time", "Measurement", "Value"])

    time_format = pd.to_datetime(df['Time'], infer_datetime_format=True).dt.strftime('%Y-%m-%d %H:%M:%S.%f').iloc[0]
    df['Time'] = pd.to_datetime(df['Time'], format=time_format)

    time_diff = df['Time'].diff().mean()  # Calculate average time difference between samples
    sample_rate = int(1 / time_diff.total_seconds())

    print(f"Calculated sample rate: {sample_rate} Hz")

    plt.figure(figsize=(12, 4))
    plt.plot(df["Time"], df["Value"], marker = 'o', markersize=1)
    plt.title('Batched data')
    plt.savefig('Batched_ECG_data_to_heartpy.png')

    data = pd.to_numeric(df['Value'], errors='coerce')

    wd, m = hp.process(data, sample_rate)
    hp.plotter(wd, m, figsize=(12,4))
    plt.savefig('peak_detection.png')

    print("\npeak detection:...")
    #display computed measures
    for measure in m.keys():
        print('%s: %f' %(measure, m[measure]))

    filtered = hp.filter_signal(data, cutoff = 0.05, sample_rate = sample_rate, filtertype='notch')

    #visualize again
    plt.figure(figsize=(12,4))
    plt.plot(filtered)
    plt.title('filtered data')
    plt.savefig('filtered_data.png')

    #and zoom in a bit
    plt.figure(figsize=(12,4))
    plt.plot(data[0:2500], label = 'original signal')
    plt.plot(filtered[0:2500], alpha=0.5, label = 'filtered signal')
    plt.title('filtered data')
    plt.legend()
    plt.savefig('filtered_data_zoomed_in.png')

    #run analysis
    wd, m = hp.process(hp.scale_data(filtered), sample_rate)

    #visualise in plot of custom size
    hp.plotter(wd, m, figsize=(12,4), title="reduced the amplitude of the T-wave")
    plt.savefig('reduced_the_amplitude_of_the_T-wave.png')
    print("\nreduced the amplitude of the T-wave:...")

    #display computed measures
    for measure in m.keys():
        print('%s: %f' %(measure, m[measure]))

    from scipy.signal import resample

    #resample the data. Usually 2, 4, or 6 times is enough depending on original sampling rate
    resampled_data = resample(filtered, len(filtered) * 4)

    #And run the analysis again. Don't forget to up the sample rate as well!
    wd, m = hp.process(hp.scale_data(resampled_data), sample_rate * 4)

    #visualise in plot of custom size
    hp.plotter(wd, m, figsize=(12,4), title="upsampled signal")
    plt.savefig('upsampled_signal.png')
    print("\nupsampled signal:...")

    #display computed measures
    print('%s: %f' %('bpm', m['bpm']))
    for measure in m.keys():
        print('%s: %f' %(measure, m[measure]))

    hp.plot_poincare(wd, m, figsize=(12,4))
    plt.savefig('poincare.png')

    #print poincare measures
    poincare_measures = ['sd1', 'sd2', 's', 'sd1/sd2']
    print('\nnonlinear poincare measures:...')
    for measure in poincare_measures:
        print('%s: %f' %(measure, m[measure])) 

    write_api = client.write_api(write_options=SYNCHRONOUS)

    # Define a new data point
    point = Point("Hartslag").field("bpm", m['bpm'])

    # Write the data point to InfluxDB
    write_api.write(bucket=bucket, org="Uhasselt", record=point)
    
    # Increment the start_time and stop_time for the next iteration
    print(start_time)
    print(stop_time)
    start_time = (datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S.%fZ") + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    stop_time = (datetime.strptime(stop_time, "%Y-%m-%dT%H:%M:%S.%fZ") + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    print(start_time)
    print(stop_time)

    # Increment the counter
    counter += 1