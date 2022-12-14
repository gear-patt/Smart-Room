import serial
from datetime import datetime
import pandas as pd
import pandas_gbq
import sys
import time
from paho.mqtt import client as mqtt_client
import pickle
from sklearn.preprocessing import StandardScaler
from joblib import load
import subprocess

broker = 'broker.hivemq.com'
port = 1883
topic = "esp8266/sensors"
client_id = 'pi'
username = 'pi'
password = 'okokay1234'


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
    else:
        print("Failed to connect, return code %d\n", rc)

client = mqtt_client.Client(client_id)
client.username_pw_set(username, password)
client.on_connect = on_connect
client.connect(broker, port)

def on_message(client, userdata, msg):
    print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
    temp = pd.DataFrame()
    temp['data'] = [msg.payload.decode()]
    temp.to_csv('esp_temp.csv',index=False)

client.subscribe(topic)
client.on_message = on_message
client.loop_start()

def push_db():
    data = pd.read_csv('sensors_data.csv')
    data.to_gbq(destination_table='sensor_data.sensor_db',project_id='smartroom-db',if_exists='append')
    print('pushed')

model = pickle.load(open('model.sav', 'rb'))
sc = load('scaler.joblib')
count_zero = 0

with serial.Serial('/dev/ttyACM0', 9600, timeout=1) as ser:
    counter=0
    while(True):
        line = ser.readline()
        try:
            sensor_dt = pd.read_csv('esp_temp.csv')
            sensor_dt = sensor_dt['data'][0]
            vibration = sensor_dt.split('/')[0]
            tvoc = sensor_dt.split('/')[1]
            co2 = sensor_dt.split('/')[2]
            pir = sensor_dt.split('/')[3]
            if line.decode('UTF-8').strip() != "":
                data = pd.read_csv('sensors_data.csv')
                real = pd.read_csv('real_time.csv')
                now = datetime.now()
                my_dates = pd.date_range("now", periods=1)
                current_time = now.strftime("%Y-%m-%d %H:%M:%S")
                current_date = now.strftime("%Y-%m-%d")
                counter = counter+1
                print(counter)
                if counter%60==0:
                    input_dt = []
                    input_data = []
                    temp = pd.DataFrame()
                    temp['time'] = [current_time]
                    temp['date'] =  [current_date]
                    temp['Temperature'] = [float(line.decode('UTF-8').strip().split(", ")[0])]
                    input_data.append(float(line.decode('UTF-8').strip().split(", ")[0]))
                    temp['RH'] = [float(line.decode('UTF-8').strip().split(", ")[1])]
                    input_data.append(float(line.decode('UTF-8').strip().split(", ")[1]))
                    temp['Distance'] = [float(line.decode('UTF-8').strip().split(", ")[2])]
                    input_data.append(float(line.decode('UTF-8').strip().split(", ")[2]))
                    if line.decode('UTF-8').strip().split(", ")[3] == "Obstacle detected":
                        temp['Detection'] = [1]
                        input_data.append(1)
                    elif line.decode('UTF-8').strip().split(", ")[3] == "No obstacle detected":
                        temp['Detection'] = [0]
                        input_data.append(0)
                    temp['Light'] = [float(line.decode('UTF-8').strip().split(", ")[4])]
                    input_data.append(float(line.decode('UTF-8').strip().split(", ")[4]))
                    temp['Vibration'] = [int(vibration)]
                    input_data.append(int(vibration))
                    temp['TVOC'] = [int(tvoc)]
                    input_data.append(int(tvoc))
                    temp['CO2'] = [int(co2)]
                    input_data.append(int(co2))
                    temp['PIR'] = [int(pir)]
                    input_data.append(int(pir))
                    input_dt.append(input_data)
                    input_dt = sc.transform(input_dt)
                    print(f'prediction: {model.predict(input_dt)}')
                    if int(model.predict(input_dt)[0]) == 0:
                        count_zero += 1
                        if count_zero == 5:
                            subprocess.call(["sh", "./assistant.sh"])
                            print("The lights are closed!!")
                            count_zero = 0
                    else:
                        count_zero = 0
                    data = pd.concat([data, temp])
                    real = pd.concat([real, temp])
                    data.to_csv('sensors_data.csv', index=False)
                    real.to_csv('real_time.csv', index=False)
                    print('saved!')
                    if len(data) > 1: #300
                        push_db()
                        data_temp = pd.read_csv('data_temp.csv')
                        data_temp.to_csv('sensors_data.csv', index=False)
                        print('done push')
        except Exception as e:
            print(e)
            continue