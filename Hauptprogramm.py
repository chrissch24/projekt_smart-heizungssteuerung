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
from ir_tx.nec import NEC # IR-Transmitter
#======================#

#=====Pins definieren=====#
# I2C-Pins definieren:
i2c = SoftI2C(scl=Pin(1), sda=Pin(2))

# ACS712-Stromsensor
strom_sensor = ADC(Pin(4))
strom_sensor.atten(ADC.ATTN_11DB)  # 0-3.3V Bereich

# IR-Transmitter
ir_tx = NEC(Pin(5, Pin.OUT))
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
neu_strahlersteuerung = 0
alt_strahlersteuerung = 0
strahlerfeedback = 0
ir_code = 0x1a
frostschutzfeedback = 0
#=============================#

#=====Einstellungen=====#
messloops = 10  # Anzahl der durchgeführten Messungen bei einem Messzyklus
# WLAN-Daten
ssid = "FRITZ!Box 7590 BC" #Änderung bei Netzwerkänderung
password = "97792656499411616203" #Änderung bei Netzwerkänderung

#MQTT-Publish
pb_client_id = "mqttx_b1dee7e5"
pb_broker_ip = "192.168.178.56" #Änderung bei Netzwerkänderung
pb_port = 1883
pb_user = "ChSch"
pb_password = "12345678"

# MQTT-Daten Subscribe
subscribe_MQTT_CLIENT_ID = "mqttx_b1dee8e6"
subscribe_MQTT_BROKER_IP = pb_broker_ip
subscribe_MQTT_TOPIC = "Heizstrahler/Steuerung"

# Kalibrierwerte Stromsensor
mV_per_A = 100  #100mV pro 1A aus
ACS_offset = 2500  #Spannung bei 0A (in mV)

#IR-Daten
ir_keys = { 0: 0x1a, # Aus
            1: 0x04, # 1kW
            2: 0x06, # 2kW
            3: 0x0a} # 3kW

ir_adresse = 0080
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

#-------------------------------------------#
def messungacs712():
    """Messung des Stroms des Heizstrahlers und Umrechnung in Watt """
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
#-------------------------------------------#
def callback_strahler(topic, msg):
    """Abrufen der Steuerungsdaten für den Heizstrahler """
    global neu_strahlersteuerung, alt_strahlersteuerung, ir_code
    try:
        #Aus der MQTT-Nachricht den Werte für "Strahler" extrahieren
        sub_daten = json.loads(msg)
        neu_strahlersteuerung = sub_daten.get("Strahler")
    
    except Exception as e:
        # Bei einen Fehler immer 0.
        # 0 Entspricht Heizstrahler Aus
        print("Fehler beim Auslesen der Subscribe Daten")
        neu_strahlersteuerung = 0
        
    # Nur ein IR-Code Änderung wenn es eine Änderung gibt
    if neu_strahlersteuerung != alt_strahlersteuerung:
        # IR-Code aus den Dictionary ziehen
        ir_code = ir_keys.get(neu_strahlersteuerung)
        alt_strahlersteuerung = neu_strahlersteuerung
        # Funktion zur Steuerung des Strahler aufrufen
        steuerung_strahler()

#-------------------------------------------#
def steuerung_strahler():
    """Senden der IR Daten an den Heizstrahler """
    global strahlerfeedback
    # Stufe 1
    # Kann immer eingeschaltet werden
    if neu_strahlersteuerung == 1:
        ir_tx.transmit(ir_adresse, ir_code)
        strahlerfeedback = 1
        
    # Stufe 2
    # Kann nur Bedingt eingeschaltet werden, wenn er auf Stufe 1 oder 3 ist.
    elif neu_strahlersteuerung == 2 and strahlerfeedback in [1, 3]:
        ir_tx.transmit(ir_adresse, ir_code)
        strahlerfeedback = 2
    
    # Stufe 3
    # Kann nur eingeschlatet werden wenn er in Stufe 2 ist.
    elif neu_strahlersteuerung == 3 and strahlerfeedback == 2:
        ir_tx.transmit(ir_adresse, ir_code)
        strahlerfeedback = 3
        
    else:
        ir_tx.transmit(ir_adresse, ir_code)
        strahlerfeedback = 0
#-------------------------------------------#
def frostschutz():
    """ Funktion zum Frostschutz des Raumes"""
    ir_tx.transmit(ir_adresse, ir_keys.get(1)) # Strahler wird auf Stufe 1 geschaltet
    time.sleep(5) # 5 Sekunden Wartezeit um große Einschaltströme zu verhindern
    
    ir_tx.transmit(ir_adresse, ir_keys.get(2)) # Strahler wird auf Stufe 2 geschaltet
    time.sleep(5) # 5 Sekunden Wartezeit um große Einschaltströme zu verhindern
    
    ir_tx.transmit(ir_adresse, ir_keys.get(3)) # Strahler wird auf Stufe 3 geschaltet
    
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

# Publish Client
pb_client = MQTTClient(pb_client_id, pb_broker_ip, pb_port, pb_user, pb_password)
try:
    print("Verbindungstest zum MQTT-Publish-Client")
    pb_client.connect()
    time.sleep(0.5)
    pb_client.disconnect()
    print("Verbindungstest Publish erfolgreich")
except Exception as e:
    print("Fehler bei der MQTT-Publish-Verbindung:", e)

# Subscribe Client
try:
    print("Verbinden zum Subscribe Broker")
    subscribe_client = MQTTClient(subscribe_MQTT_CLIENT_ID, subscribe_MQTT_BROKER_IP)
    subscribe_client.set_callback(callback_strahler)
    subscribe_client.connect()
    subscribe_client.subscribe(subscribe_MQTT_TOPIC)
    print("Erfolgreich Verbunden Subscribe ")
except Exception as e:
    print("Fehler bei der MQTT-Subscribe-Verbindung:", e)
#=================================#

#=====Hauptschleife=====#
while True:
    # Temperatur und Luftfeuchtigkeit messen
    messungaht10()
    
    # Luftqualität messen wenn der Sensor bereit ist
    if sensorccs811.data_ready():
        messungccs811()
    # Leistung messen sobald der Heizstrahler eingeschaltet ist    
    if neu_strahlersteuerung in [1, 2, 3]:
        messungacs712()
        
    #Sensordaten in JSON-Fomart schreiben
    sensordaten = {"Temperatur": raumtemperatur, "Luftfeuchtigkeit": luftfeuchtigkeit, "CO2-Wert": co2_wert, "TVOC-Wert": tvoc_wert, "Momentane Leistung": momt_leistung, "Gesamte Verbrauchte Leistung": ges_leistung }
    json_sensordaten = json.dumps(sensordaten)
    
    #Feedback vom Strahler in JSON-Fomart schreiben
    feedbackdaten = {"Strahlerfeedback": strahlerfeedback, "Frostschutzfeedback": frostschutzfeedback}
    json_feedbackdaten = json.dumps(feedbackdaten)
    
     # Sende JSON-Daten an den Broker
    pb_client.connect()
    pb_client.publish("Raum/Sensorwerte", json_sensordaten)
    print("Sensordaten versendet:", json_sensordaten)
    pb_client.publish("Raum/Feedback",json_feedbackdaten)
    print("Feedbackdaten versendet:", json_feedbackdaten)
    pb_client.disconnect()
    
    
    # Nach neuen Nachrichten Abfragen
    subscribe_client.check_msg()
    
    # Frostschutz Funktion
    if raumtemperatur < 5 and strahlerfeedback == 0:
        frostschutz()
        strahlerfeedback = 3
        frostschutzfeedback = 1
    elif raumtemperatur > 7 and frostschutzfeedback == 1:
        ir_tx.transmit(ir_adresse, ir_keys.get(0))
        strahlerfeedback = 0
        frostschutzfeedback = 0
        
