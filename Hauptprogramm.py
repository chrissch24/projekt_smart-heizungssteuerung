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

# ACS712-Stromsensor
strom_sensor = ADC(Pin(4))
strom_sensor.atten(ADC.ATTN_11DB)  # 0-3.3V Bereich
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
strom_list = []
messpannung = 230
momt_leistung = 0
ges_leistung = 0

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

# Kalibrierwerte Stromsensor
mV_per_A = 100  #100mV pro 1A aus
ACS_offset = 2500  #Spannung bei 0A (in mV)
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
        #Messwerte auslesen
        for i in range(messloops):
            raumtemp.append(sensoraht10.temperature())
            raumluft.append(sensoraht10.humidity())
            
        # Mittelwertfilter anwenden
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
        co2_list.clear()
        tvoc_list.clear()
        # Messwerte auslesen
        for i in range(messloops):
            co2_list.append(sensorccs811.eCO2)
            tvoc_list.append(sensorccs811.tVOC)
            
        # Mittelwertfilter anwenden
        co2_wert = messfilter(co2_list)
        tvoc_wert = messfilter(tvoc_list)
    
    except Exception as e:
        print("Fehler beim Lesen des CCS811-Sensors:", e)
        co2_wert = "Fehler"
        tvoc_wert = "Fehler"

def messungacs712():
    global momt_leistung, ges_leistung
    try:
        strom_list.clear()
        
        # Messwerte auslesen
        for i in range(messloops):
            strom_list.append(strom_sensor.read())

        # Mittelwertfilter anwenden
        mess_strom = messfilter(strom_list)

        # ADC-Wert in Millivolt umrechnen
        strom_in_mv = (mess_strom / 4095.0) * 3300

        # Umrechnung von mV in Ampere unter Berücksichtigung des Offset
        strom_A = (strom_in_mv - ACS_offset) / mV_per_A

    except Exception as e:
        print("Fehler beim Lesen des ACS712-Sensors:", e)
        strom_A = "Fehler"

    if strom_A != "Fehler":
        # Momentanleistung berechnen
        momt_leistung = round(messpannung * strom_A, 2)

        # Gesamtleistung aufsummieren
        ges_leistung += momt_leistung
        ges_leistung = round(ges_leistung, 2)

    else:
        momt_leistung = "Fehler"

    
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
    daten = {"Temperatur": raumtemperatur, "Luftfeuchtigkeit": luftfeuchtigkeit, "CO2-Wert": co2_wert, "TVOC-Wert": tvoc_wert, "Momentane Leistung": momt_leistung, "Gesamte Verbrauchte Leistung": ges_leistung }
    json_daten = json.dumps(daten)

     # Sende JSON-Daten an den Broker
    pb_client.connect()
    pb_client.publish(pb_topic, json_daten)
    pb_client.disconnect()
    print("Daten versendet:", daten)
