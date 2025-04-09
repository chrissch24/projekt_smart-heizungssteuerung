#Projekt: Smart Heizungssteuerung
#Ersteller: Ch. Scheele
#Erstellungsdatum: 25.03.2025
#Letzte Änderung:

#=====Bibliotheken=====#
from machine import Pin, PWM, SoftI2C
import time
import json
import network
from umqtt.simple import MQTTClient
from aht10 import AHT10  # Temperatur- und Luftfeuchtigkeitssensor
import CCS811 # Luftqualitätssensor
#======================#

#=====Pins definieren=====#
# I2C-Pins definieren:
i2c = SoftI2C(scl=Pin(1), sda=Pin(2))

#=========================#

#=====Sensor Objekte definieren=====#
sensoraht10 = AHT10(i2c)
sensorccs811 = CCS811.CCS811(i2c=i2c, addr=90)
#===================================#

#=====Variabeln festlegen=====#
raumtemperatur = 0
luftfeuchtigkeit = 0
co2_wert = 0
tvoc_wert = 0
raumtemp = []
raumluft = []
co2_list = []
tvoc_list = []

ir_keys = { 0x1a: "Aus",
            0x04: "1kW",
            0x06: "2kW",
            0x0a: "3kW"} # Addresse 0080
#=============================#

#=====Einstellungen=====#
messloops = 10  # Anzahl der durchgeführten Messungen bei einem Messzyklus
# WLAN-Daten
ssid = "FRITZ!Box 7590 BC"
password = "97792656499411616203"

#MQTT-Publish
pb_client_id = "mqttx_b1dee7e5"
pb_broker_ip = "192.168.178.56"
pb_port = 1883
pb_user = "ChSch"
pb_password = "12345678"
pb_topic = "Raum/Sensorwerte"
#=======================#

#=====Funktionen=====#
def messfilter(messwerte):
    """Filtern von Messwerten, um Ausreißer zu entfernen"""
    if len(messwerte) < 3:  # Sicherheit, um Fehler zu vermeiden
        return sum(messwerte) / len(messwerte) if messwerte else 0
    
    messwerte.sort()  # Werte sortieren
    messwerte.pop(0)  # Kleinster Wert entfernen
    messwerte.pop()   # Größter Wert entfernen
    messwerte = round(sum(messwerte) / len(messwerte), 2)
    return messwerte

#-------------------------------------------#
# Messung der Temperatur und Luftfeuchtigkeit
def messungaht10():
    """Messung der Temperatur und Luftfeuchtigkeit"""
    global raumtemperatur, luftfeuchtigkeit
    try:
        raumtemp.clear()
        raumluft.clear()
        for i in range(messloops):
            raumtemp.append(sensoraht10.temperature())
            raumluft.append(sensoraht10.humidity())
        raumtemperatur = messfilter(raumtemp)
        luftfeuchtigkeit = messfilter(raumluft)
    except Exception as e:
        print("Fehler beim Lesen des AHT10-Sensors:", e)
        raumtemperatur = "Fehler"
        luftfeuchtigkeit = "Fehler"

#-------------------------------------------#
# Messung der Luftqualität
def messungccs811():
    """Messung Luftqualität"""
    global co2_wert, tvoc_wert
    try:
        for i in range(messloops):
            co2_list.append(sensorccs811.eCO2)
            tvoc_list.append(sensorccs811.tVOC)
        #Messwerte filtern
        co2_wert = messfilter(co2_list)
        tvoc_wert = messfilter(tvoc_list)
    
    except Exception as e:
        print("Fehler beim Lesen des CCS811-Sensors:", e)
        co2_wert = "Fehler"
        tvoc_wert = "Fehler"
    
    

#====================#

#=====Einmalige Einrichtungen=====#

# WLAN-Verbindung herstellen
wlan = network.WLAN(network.STA_IF)
wlan.active(True)  
wlan.connect(ssid, password)  
print(f"Verbinde mit {ssid}...")
    
while not wlan.isconnected():
    time.sleep(1)
    print("Verbindungsversuch läuft...")
    
# Erfolgreich verbunden
print(f"Verbunden mit {ssid}")
print(f"IP-Adresse: {wlan.ifconfig()[0]}") 

# MQTT-Client einrichten und verbinden

pb_client = MQTTClient(pb_client_id, pb_broker_ip, pb_port, pb_user, pb_password)
try:
    print("Verbindungstest zum MQTT-Client")
    pb_client.connect()
    time.sleep(0.5)
    pb_client.disconnect()
    print("Verbindungstest erfolgreich")
except Exception as e:
    print("Fehler bei der MQTT-Verbindung:", e)

#=================================#

#=====Hauptschleife=====#
while True:
    # Temperatur und Luftfeuchtigkeit messen
    messungaht10()

    if sensorccs811.data_ready():
        messungccs811()
    #Sensordaten in JSON-Fomart schreiben
    daten = {"Temperatur": raumtemperatur, "Luftfeuchtigkeit": luftfeuchtigkeit, "CO2-Wert": co2_wert, "TVOC-Wert": tvoc_wert}
    json_daten = json.dumps(daten)

     # Sende JSON-Daten an den Broker
    pb_client.connect()
    pb_client.publish(pb_topic, json_daten)
    pb_client.disconnect()
    print("Daten versendet:", daten)
