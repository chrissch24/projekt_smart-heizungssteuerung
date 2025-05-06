#Projekt: Smart Heizungssteuerung
#Ersteller: Ch. Scheele
#Erstellungsdatum: 25.03.2025
#Letzte Änderung: 29.04.2025
#Programm Name: main (hauptprogramm)
#Aufgabe: Messung und Auswertung der Sensordaten
#		  Kommunikation mit den MQTT-Broker
#		  Steuern des Heizstrahlers
#=====Bibliotheken=====#
from machine import Pin, PWM, SoftI2C, SoftSPI
import time
import json
import network
from umqtt.simple import MQTTClient
from Start import wlan_ssid, wlan_passwort, broker_ip # Daten aus der der Start Datei ziehen
from aht10 import AHT10  # Temperatur- und Luftfeuchtigkeitssensor
import CCS811 # Luftqualitätssensor
from ir_tx.nec import NEC # IR-Transmitter
import st7789py as st7789 #Bildschirm-Bibliothek
import vga1_8x16 as font #Bildschirm Font
#======================#

#=====Hardware Informationen=====#
#ESP32-S3

#I2C
#SCL = Pin 1
#SDA = Pin 2

#DeboSens20A
#ADC = Pin 4

#KY-005
#Signal (S) = Pin 5

#Bildschirm Belegung
#ST7789V3
#SCK = Pin 42
#MOSI = Pin 41
#MISO = Pin 0
#Reset = Pin 40
#CS = Pin 39
#dc = Pin 38
#================================#

#=====Pins definieren=====#
# I2C-Pins definieren:
i2c = SoftI2C(scl=Pin(1), sda=Pin(2))

# ACS712-Stromsensor
#strom_sensor = ADC(Pin(4))
#strom_sensor.atten(ADC.ATTN_11DB)  # 0-3.3V Bereich

# IR-Transmitter
ir_tx = NEC(Pin(5, Pin.OUT))

#SPI-Schnittstelle
spi = SoftSPI(
        baudrate = 2000000,
        polarity = 1,
        phase = 0,
        sck = Pin(42),
        mosi = Pin(41),
        miso = Pin(0))
#=========================#

#=====Sensor Objekte definieren=====#
#AHT10 definieren
sensoraht10 = AHT10(i2c)

#CCS811 definieren
sensorccs811 = CCS811.CCS811(i2c=i2c, addr=90)

#Bildschirm ST7789 definieren
txt = st7789.ST7789(
        spi,
        240,
        320,
        reset = Pin(40, Pin.OUT),
        cs = Pin(39, Pin.OUT),
        dc = Pin(38, Pin.OUT),
        backlight = Pin(0, Pin.OUT),
        rotation = 1)

#Bildschirm auf Schwarz setzen
txt.fill(st7789.BLACK)
txt.text(font, "Boot Vorgang gestartet", 72, 109, st7789.CYAN, st7789.BLACK)
bootvorgang = True
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
momt_leistung = 0
ges_verbrauch = 0
teil_verbrauch = 0
neu_strahlersteuerung = 0
alt_strahlersteuerung = 0
strahlerfeedback = 0
frostschutzfeedback = 0
mqttpb_verbunden = False
mqttsb_verbunden = False
frostschutzfeedbackstring = 0
feedbackdaten_alt = {}
feedbackdaten_neu = {}
sensordaten_alt = {}
sensordaten_neu = {}
betriebszahler = 0
#=============================#

#=====Einstellungen=====#
messloops = 10  # Anzahl der durchgeführten Messungen bei einem Messzyklus

# Voreinstellung für den Frostschutz
frostschutzschwellwert = 5 #Wert wenn er aktiviert wird
frostschutzaus = 7 #Wert wenn er wieder ausgeschaltet wird

# Zeit Intervalle Einstellungen
mess_umwelt_now = 0
mess_umwelt_last = 0
mess_strom_now = 0
mess_strom_last = 0
mess_umwelt_intervall = 30000 # in ms, entspricht 30s
mess_strom_intervall = 1000 # in ms, entspricht 1s

# WLAN-Daten
ssid = wlan_ssid # Variabel kommt von der "Start-Datei". Wert wird vom Nutzer festgelegt
password = wlan_passwort # Variabel kommt von der "Start-Datei". Wert wird vom Nutzer festgelegt
max_versuche = 60 #Wie viel fehlgeschlagene Versuche soll es geben bis er abbricht. 60 Versuche entsprichen 1 Minuten

#MQTT-Publish-Einstellungen
pb_client_id = "mqttx_b1dee7e5"
pb_broker_ip = broker_ip # Variabel kommt von der "Start-Datei". Wert wird vom Nutzer festgelegt
pb_port = 1883
pb_user = "ChSch"
pb_password = "12345678"

# MQTT-Subscribe-Einstellungen
subscribe_MQTT_CLIENT_ID = "mqttx_b1dee8e6"
subscribe_MQTT_BROKER_IP = pb_broker_ip
subscribe_MQTT_TOPIC_1 = "Steuerung/Stufen"
subscribe_MQTT_TOPIC_2 = "Steuerung/FrostEIN"
subscribe_MQTT_TOPIC_3 = "Steuerung/FrostAUS"

# Kalibrierwerte Stromsensor
mV_per_A = 100  #100mV pro 1A aus
ACS_offset = 2500  #Spannung bei 0A (in mV)
messpannung = 230 #Zur Berechnung der Leistung

# IR-Daten
# Zur Steuerung des Heizstrahlers
ir_keys = { 0: 0x1a, # Aus
            1: 0x04, # 1kW
            2: 0x06, # 2kW
            3: 0x0a} # 3kW

ir_adresse = 0080

# Variabel wird benötigt zum Senden der IR-Daten
ir_code = 0x1a # IR Code grundstellung ist immer auf Aus
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
    return int(messwerte)

#-------------------------------------------#
# Messung der Temperatur und Luftfeuchtigkeit
def messungaht10():
    """Messung der Temperatur und Luftfeuchtigkeit"""
    global raumtemperatur, luftfeuchtigkeit
    try:
        # Alle Elemente in den Listen werden gelöscht, um sicherzustellen, dass sie leer sind, bevor neue Messdaten hinzugefügt werden.
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
        # Fehlerbehandlung, Texte werden auf den Bildschirm angezeigt
        raumtemperatur = "Fehler"
        luftfeuchtigkeit = "Fehler"

#-------------------------------------------#
# Messung der Luftqualität
def messungccs811():
    """Messung Luftqualität"""
    global co2_wert, tvoc_wert
    try:
        # Alle Elemente in den Listen werden gelöscht, um sicherzustellen, dass sie leer sind, bevor neue Messdaten hinzugefügt werden.
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
        # Fehlerbehandlung, Texte werden auf den Bildschirm angezeigt
        print("Fehler beim Lesen des CCS811-Sensors:", e)
        co2_wert = "Fehler"
        tvoc_wert = "Fehler"

#-------------------------------------------#
def messungacs712():
    """Messung des Stroms des Heizstrahlers und Umrechnung in Watt """
    global momt_leistung
    try:
        strom_list.clear()
        
        # Messwerte auslesen
        for i in range(messloops):
            #strom_list.append(strom_sensor.read())
            strom_list.append(4000)

        # Mittelwertfilter anwenden
        mess_strom = messfilter(strom_list)

        # ADC-Wert in Millivolt umrechnen
        strom_in_mv = (mess_strom / 4095.0) * 3300

        # Umrechnung von mV in Ampere unter Berücksichtigung des Offset
        strom_A = (strom_in_mv - ACS_offset) / mV_per_A

    except Exception as e:
         # Fehlerbehandlung, Texte werden auf den Bildschirm angezeigt
        print("Fehler beim Lesen des ACS712-Sensors:", e)
        strom_A = "Fehler"
        
    # Berechnung wird nur ausgeführt falls kein Fehler vorliegt
    if strom_A != "Fehler":
        # Momentanleistung berechnen
        momt_leistung = messpannung * strom_A
        momt_leistung = int(momt_leistung)
        
    else:
        # Fehlerbehandlung, Texte werden auf den Bildschirm angezeigt
        momt_leistung = "Fehler"
#-------------------------------------------#
def callback_strahler(topic, msg):
    """Abrufen der Steuerungsdaten für den Heizstrahler """
    global neu_strahlersteuerung, alt_strahlersteuerung, ir_code, frostschutzschwellwert, frostschutzaus
    try:
        #Aus der MQTT-Nachricht den Werte für "Strahler" extrahieren
        sub_daten = json.loads(msg)
        print(f"Empfange Daten {sub_daten}")
        
        # Überprüfen, ob der Wert für "Strahler" in den empfangenen Daten vorhanden ist
        # Wenn der Wert existiert und nicht None ist, wird der neue Wert gesetzt
        if sub_daten.get("Strahler") is not None:
            neu_strahlersteuerung = sub_daten.get("Strahler")
        
        # Überprüfen, ob der Wert für "FrostEIN" in den empfangenen Daten vorhanden ist
        # Wenn der Wert existiert und nicht None ist, wird der neue Wert gesetzt
        if sub_daten.get("FrostEIN") is not None:
            frostschutzschwellwert = sub_daten.get("FrostEIN")
        
        # Überprüfen, ob der Wert für "FrostAUS" in den empfangenen Daten vorhanden ist
        # Wenn der Wert existiert und nicht None ist, wird der neue Wert gesetzt
        if sub_daten.get("FrostAUS") is not None:
            frostschutzaus = sub_daten.get("FrostAUS")
        
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
        strahlerfeedback = 1 # Feedback für die Node-Red-Dashboard Anzeige
        
    # Stufe 2
    # Kann nur Bedingt eingeschaltet werden, wenn er auf Stufe 1 oder 3 ist.
    elif neu_strahlersteuerung == 2 and strahlerfeedback in [1, 3]:
        ir_tx.transmit(ir_adresse, ir_code)
        strahlerfeedback = 2 # Feedback für die Node-Red-Dashboard Anzeige
    
    # Stufe 3
    # Kann nur eingeschlatet werden wenn er in Stufe 2 ist.
    elif neu_strahlersteuerung == 3 and strahlerfeedback == 2:
        ir_tx.transmit(ir_adresse, ir_code)
        strahlerfeedback = 3 # Feedback für die Node-Red-Dashboard Anzeige
    
    # Aus
    # Heizstrahler wird ausgeschaltet 
    elif neu_strahlersteuerung not in [1, 2, 3]:
        ir_tx.transmit(ir_adresse, ir_code)
        strahlerfeedback = 0

#-------------------------------------------#
def wifi_verbindung():
    """ Funktion um sich mit den Wlan Netzwerk zu Verbinden.
    Abbruch, sobald die maximal gesetzte Anzahl an Versuchen überschritten ist. """
    
    # Wenn bereits verbunden, abbrechen
    if wlan.isconnected():
        return
    
    # Verbindung mit WLAN herstellen
    print(f"Verbinde mit {ssid}...")
    wlan.connect(ssid, password) 
    versuche = 0
    
    # Versuche, so lange mit WLAN zu verbinden, bis entweder eine Verbindung hergestellt wird oder die maximale Anzahl an Versuchen erreicht ist
    while not wlan.isconnected() and versuche < max_versuche:
        try:
            time.sleep(1)
            versuche += 1
                
            print(f"Verbindungsversuch {versuche}/{max_versuche}...")
        except Exception as e:
            # Fehlerbehandlung im Falle eines Fehlers bei der Verbindung
            print("Fehler beim Verbindungsversuch:", e)
            
            # Anzeige eines Fehlertexts beim Bootvorgang
            if bootvorgang:
                txt.text(font, "Boot Vorgang abgebrochen", 72, 109, st7789.CYAN, st7789.BLACK)
                
            # Anzeige des Fehlertexts
            txt.text(font, "Fehler beim Verbindungsversuch", 45, 132, st7789.CYAN, st7789.BLACK)
            txt.text(font, "mit den Wlan Netzwerk", 80, 155, st7789.CYAN, st7789.BLACK)
            
            return 

    # Wenn Wlan verbunden ist, wird die Netzwerkonfiguration ausgegeben
    if wlan.isconnected():
        print("WLAN verbunden!")
        print("Netzwerk-Konfiguration:", wlan.ifconfig())

    else:
        # Wenn die Verbindung nicht erfolgreich war, Fehlernachricht anzeigen
        print("Verbindung fehlgeschlagen nach mehreren Versuchen.")
        # Anzeige des Fehlertexts
        txt.fill(st7789.BLACK)
        
        # Anzeige eines Fehlertexts beim Bootvorgang
        if bootvorgang:
            txt.text(font, "Boot Vorgang abgebrochen", 72, 109, st7789.CYAN, st7789.BLACK)
            
         # Anzeige des Fehlertexts
        txt.text(font, "Verbindung Wlan fehlgeschlagen", 50, 132, st7789.CYAN, st7789.BLACK)
        txt.text(font, "Zu viele Versuche", 90, 155, st7789.CYAN, st7789.BLACK)
#-------------------------------------------#

def publish_senden(topic, daten):
    """Funktion zum Verbinden mit dem MQTT-Broker und Senden der Daten."""
    global mqttpb_verbunden
    
    try:
        # Sollte die Wlan Verbindung verloren sein, wird sie wieder hergestellt
        if not wlan.isconnected():
            print("MQTT-Publish-Wlan Verbindung wiederherstellen")
            wifi_verbindung()
            
        # Verbindung zum Broker herstellen, Daten versenden und Verbindung trennen
        pb_client.connect()
        print("Verbindung MQTT Publish hergestellt")
        
        # Dictionary wird in JSON-Format umgeschrieben
        json_daten = json.dumps(daten)
            
        # Daten werden am Broker gesendet
        pb_client.publish(topic, json_daten)
        print("Daten verschickt", json_daten)
            
        # Verbindung zum Broker wird abgebrochen
        pb_client.disconnect()
            
    except Exception as e:
        # Anzeige des Fehlertexts
        print("Fehler bei MQTT-Publish", e)
        txt.fill(st7789.BLACK)
        txt.text(font, "Fehler bei der Verbindung mit", 60, 132, st7789.CYAN, st7789.BLACK)
        txt.text(font, "MQTT-Broker-Publish", 85, 155, st7789.CYAN, st7789.BLACK)
        txt.text(font, f"Fehler {e}", 30, 178, st7789.CYAN, st7789.BLACK)
        
        # Wird auf False gesetzt um die Hauptschleife zu beenden
        mqttpb_verbunden = False 

#====================#

#=====Einmalige Einrichtungen=====#

# WLAN-Verbindung herstellen
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wifi_verbindung()

# MQTT-Client einrichten und testen

# Publish Client
if wlan.isconnected():
    
    # MQTT-Publish-Client erstellen
    pb_client = MQTTClient(pb_client_id, pb_broker_ip, pb_port, pb_user, pb_password)
    # Test Verbindung zum Client herstellen
    try:
        print("Verbindungstest zum MQTT-Publish-Client")
        pb_client.connect()
        time.sleep(0.5)
        pb_client.disconnect()
        print("Verbindungstest Publish erfolgreich")
        
        # Der Wert wird auf True gesetzt, wenn der Test erfolgreich war. Nur bei einem erfolgreichen Test kann die Hauptschleife gestartet werden.
        mqttpb_verbunden = True
        
    except Exception as e:
        print("Fehler bei der MQTT-Publish-Verbindung:", e)
        
        # Anzeige des Fehlertexts
        txt.fill_rect(72, 109, 170, 15, st7789.BLACK)
        txt.text(font, "Boot Vorgang abgebrochen", 72, 86, st7789.CYAN, st7789.BLACK)
        txt.text(font, "Fehler beim Verbinden mit", 60, 109, st7789.CYAN, st7789.BLACK)
        txt.text(font, "MQTT-Broker-Publish", 85, 132, st7789.CYAN, st7789.BLACK)
        txt.text(font, f"Fehler {e}", 30, 155, st7789.CYAN, st7789.BLACK)

# Subscribe Client
if wlan.isconnected():
    try:
        # MQTT-Subscribe-Client erstellen
        subscribe_client = MQTTClient(subscribe_MQTT_CLIENT_ID, subscribe_MQTT_BROKER_IP)
        
        # Callback-Funktion wird festgelegt. Bei Empfang von Nachrichten wird die Funktion durch den Subscribe-Client aufgerufen wird.
        subscribe_client.set_callback(callback_strahler)
        
        # Verbindung zum Subscribe Broker wird hergestellt
        print("Verbinden zum Subscribe Broker")
        subscribe_client.connect()
        
        # Topics werden abonniert
        subscribe_client.subscribe(subscribe_MQTT_TOPIC_1) #Topic Steuerung/Stufen
        subscribe_client.subscribe(subscribe_MQTT_TOPIC_2) #Topic Steuerung/FrostEIN
        subscribe_client.subscribe(subscribe_MQTT_TOPIC_3) #Topic Steuerung/FrostAUS
        
        # Der Wert wird auf True gesetzt, wenn der Test erfolgreich war. Nur bei einem erfolgreichen Test kann die Hauptschleife gestartet werden.
        mqttsb_verbunden = True
        
        print("Erfolgreich Verbunden Subscribe ")
        
    except Exception as e:
        # Anzeige des Fehlertexts
        print("Fehler bei der MQTT-Subscribe-Verbindung:", e)
        txt.fill_rect(72, 109, 170, 15, st7789.BLACK)
        txt.text(font, "Boot Vorgang abgebrochen", 72, 86, st7789.CYAN, st7789.BLACK)
        txt.text(font, "Fehler beim Verbinden mit", 60, 109, st7789.CYAN, st7789.BLACK)
        
        # Falls beim MQTT-Publish bereits ein Fehler ist, wird die Nachricht darunter eingefügt
        if mqttpb_verbunden == True:
            txt.text(font, "MQTT-Broker-Subscribe", 80, 132, st7789.CYAN, st7789.BLACK)
            txt.text(font, f"Fehler {e}", 30, 1553, st7789.CYAN, st7789.BLACK)
            
        else:
            txt.text(font, "MQTT-Broker-Subscribe", 80, 178, st7789.CYAN, st7789.BLACK)
            txt.text(font, f"Fehler {e}", 30, 201, st7789.CYAN, st7789.BLACK)
#=================================#

# Bildschirmtexte einfügen nach erfolgreichen Boot Vorgang
if wlan.isconnected() and mqttpb_verbunden and mqttsb_verbunden:
    txt.fill_rect(72, 109, 170, 15, st7789.BLACK)
    txt.text(font, "Boot Vorgang erfolgreich", 72, 109, st7789.CYAN, st7789.BLACK)
    
    # Merker für Fehlertexte falls nach den Boot Vorgang Fehler Texte auf Bildschirm geschrieben werden
    bootvorgang = False
    
    # Kurze Wartezeit zum Lesen
    time.sleep(2)
    txt.fill_rect(72, 109, 195, 15, st7789.BLACK)

# Bildschirm Texte einfügen für die Sensorwerte und Einstellungen
    txt.text(font, "Temperatur: ", 30, 40, st7789.CYAN, st7789.BLACK)
    txt.text(font, "Luftfeuchtigkeit: ", 30, 63, st7789.CYAN, st7789.BLACK)
    txt.text(font, "CO2-Wert: ", 30, 86, st7789.CYAN, st7789.BLACK)
    txt.text(font, "TVOC-Wert: ", 30, 109, st7789.CYAN, st7789.BLACK)
    txt.text(font, "Aktuelle Leistung: ", 30, 132, st7789.CYAN, st7789.BLACK)
    txt.text(font, "Gesamte Leistung: ", 30, 155, st7789.CYAN, st7789.BLACK)
    txt.text(font, "Frostschutz Einschalten: ", 30, 178, st7789.CYAN, st7789.BLACK)
    

#=====Hauptschleife=====#
while mqttpb_verbunden and mqttsb_verbunden:

"""Auswertung und Messung der Sensordaten """
    # Aktuelle Zeit wird gemessen für die Messintervalle der Sensoren
    mess_umwelt_now = time.ticks_ms()
    mess_strom_now = time.ticks_ms()
    
    # Alle 30 Sekunden wird eine Messung durchgeführt
    if time.ticks_diff(mess_umwelt_now, mess_umwelt_last) >= mess_umwelt_intervall:
        mess_umwelt_last = mess_umwelt_now
        
        # Temperatur und Luftfeuchtigkeit messen
        print("Umwelt-Messung")
        messungaht10()
    
        # Luftqualität messen wenn der Sensor bereit ist
        try:
            if sensorccs811.data_ready():
                
                # Wird nur ausgeführt wenn beide Varibalen vom AHT10 ein Integer sind. Ist es ein String liegt ein Fehler vor
                if isinstance(raumtemperatur, int) and isinstance(luftfeuchtigkeit, int):
                    
                    # Umweltdaten einspeisen um Messwerte zu verbessern.
                    sensorccs811.put_envdata(luftfeuchtigkeit, raumtemperatur)
            
            # Funktion zur Messung der Luftqualität
            messungccs811()
            print("Umwelt-Messung beendet")
            
        except Exception as e:
            print("Fehler beim Lesen des CCS811-Sensors:", e)
            # Fehlerbehandlung, Texte werden auf den Bildschirm angezeigt
            co2_wert = "Fehler"
            tvoc_wert = "Fehler" 
    
    # Leistung messen sobald der Heizstrahler eingeschaltet ist    
    if neu_strahlersteuerung in [1, 2, 3]:
        
        # In einen Takt von 1 Sekunde wird gemessen
        if time.ticks_diff(mess_strom_now, mess_strom_last) >= mess_strom_intervall:
            betriebszahler += 1 # Betriebszähler vom Heizstrahler zur Berechnung des Verbrauchs
            print("Strom-Messung gestartet")
            mess_strom_last = mess_strom_now
            
            # Funktion zur Messung des Stroms und Berechnung der Leistung
            messungacs712()
            print("Strom-Messung beendet")
    
    # Wenn der Heizstrahler ist ausgeschaltet wird:
    elif strahlerfeedback == 0:
        betriebszahler = betriebszahler / 3600 # Umrechnung von Sekunden auf Stunden
        
        # Berechnung des Verbrauchs in kWh
        teil_verbrauch = (momt_leistung / 1000 ) * betriebszahler
        ges_verbrauch += teil_verbrauch
        ges_verbrauch = int(ges_verbrauch)
        
        #Leistung wird zurückgesetzt
        momt_leistung = 0

#-------------------------------------------------------------------------------------------------------------#
"""Frostschutz-Funktion
Automatisches Ein- und Ausschalten des Heizstrahlers zur Aufrechterhaltung einer konstanten Raumtemperatur """
    
    # Frostschutz wird nur ausgeführt wenn es ein Integer ist. Sollte es ein String sein hat der Sensor ein Fehler
    # Der Schwellwert muss immer kleiner sein als der Ausschaltwert
    if isinstance(raumtemperatur, int) and frostschutzschwellwert < frostschutzaus:
        
        # Heizstrahler wird eingeschaltet wenn die Temperatur unter den eingestellten Wert ist und er nicht eingeschaltet ist
        if raumtemperatur < frostschutzschwellwert  and strahlerfeedback == 0:
            ir_tx.transmit(ir_adresse, ir_keys.get(1)) # Strahler wird auf Stufe 1 geschaltet
            time.sleep(5) # 5 Sekunden Wartezeit um große Einschaltströme zu verhindern
            
            ir_tx.transmit(ir_adresse, ir_keys.get(2)) # Strahler wird auf Stufe 2 geschaltet
            time.sleep(5) # 5 Sekunden Wartezeit um große Einschaltströme zu verhindern
    
            ir_tx.transmit(ir_adresse, ir_keys.get(3)) # Strahler wird auf Stufe 3 geschaltet
            
            # Feedback an das Node-Red-Dashboard zur Anzeige des aktuellen Status des Heizstrahlers und der Frostschutzfunktion
            strahlerfeedback = 3
            frostschutzfeedback = 1
         
        # Heizstrahler wird ausgeschaltet wenn die Temperatur über den eingestellten Wert ist und die Frostschutzfunktion aktiv ist
        elif raumtemperatur > frostschutzaus and frostschutzfeedback == 1:
            ir_tx.transmit(ir_adresse, ir_keys.get(0)) # Heizstrahler wird ausgeschaltet
            
            # Feedback an das Node-Red-Dashboard zur Anzeige des aktuellen Status des Heizstrahlers und der Frostschutzfunktion
            strahlerfeedback = 0
            frostschutzfeedback = 0
            
        
        # Setzt das Frostschutzfeedback für die Anzeige im Node-Red-Dashboard, um den Status des Frostschutzmechanismus (aktiv oder inaktiv) anzuzeigen.
        if frostschutzfeedback == 0:
            frostschutzfeedbackstring = "Aus" #Bei inaktivem Frostschutz
            
        elif frostschutzfeedback == 1:
            frostschutzfeedbackstring = "Aktiv" #Bei aktivem Frostschutz

#-------------------------------------------------------------------------------------------------------------#
"""Daten an den MQTT-Broker senden"""
    #Sensordaten in JSON-Fomart schreiben
    sensordaten_neu = {
        "Temperatur": raumtemperatur,
        "Luftfeuchtigkeit": luftfeuchtigkeit,
        "CO2_Wert": co2_wert,
        "TVOC_Wert": tvoc_wert,
        "Momentane_Leistung": momt_leistung,
        "Gesamte_Leistung": ges_verbrauch
        }
    
    #Feedback vom Strahler in JSON-Fomart schreiben
    feedbackdaten_neu = {
        "Strahlerfeedback": strahlerfeedback,
        "Frostschutzfeedback": frostschutzfeedbackstring,
        "Frostschutzschwellwert": frostschutzschwellwert,
        "FrostschutzAus": frostschutzaus
        }

    # Sensordaten werden nur am Broker und zum Bildschirm gesendet wenn es eine Veränderung gibt
    if sensordaten_neu != sensordaten_alt and mqttpb_verbunden and mqttsb_verbunden:
        sensordaten_alt = sensordaten_neu.copy()
        # Daten werden zum Bildschirm gesendet
        
        # Temperatur
        txt.fill_rect(120, 40, 100, 15, st7789.BLACK)
        txt.text(font, f"{raumtemperatur} °C", 120, 40, st7789.CYAN, st7789.BLACK)
    
        # Luftfeuchtigkeit
        txt.fill_rect(168, 63, 100, 15, st7789.BLACK)
        txt.text(font, f"{luftfeuchtigkeit} %", 168, 63, st7789.CYAN, st7789.BLACK)
    
        # CO2-Wert
        txt.fill_rect(103, 86, 100, 15, st7789.BLACK)
        txt.text(font, f"{co2_wert} ppm", 103, 86, st7789.CYAN, st7789.BLACK)
    
        # TVOC-Wert
        txt.fill_rect(112, 109, 100, 15, st7789.BLACK)
        txt.text(font, f"{tvoc_wert} ppb", 112, 109, st7789.CYAN, st7789.BLACK)
    
        # Momentane Leistung
        txt.fill_rect(175, 132, 100, 15, st7789.BLACK)
        txt.text(font, f"{momt_leistung} W", 175, 132, st7789.CYAN, st7789.BLACK)
    
        # Gesamte Leistung
        txt.fill_rect(167, 155, 100, 15, st7789.BLACK)
        txt.text(font, f"{ges_verbrauch} kWh", 167, 155, st7789.CYAN, st7789.BLACK)
        
        # Daten werden zum Broker gesendet
        publish_senden("Raum/Sensorwerte", sensordaten_neu)
  
    # Feedbackdaten werden nur am Broker und zum Bildschirm gesendet wenn es eine Veränderung gibt
    if feedbackdaten_neu != feedbackdaten_alt and mqttpb_verbunden and mqttsb_verbunden:
        feedbackdaten_alt = feedbackdaten_neu.copy()
        
        # Daten werden zum Bildschirm gesendet
        
        # Frostschutzschwellwert
        txt.fill_rect(217, 178, 100, 15, st7789.BLACK)
        txt.text(font, f"{frostschutzschwellwert} °C", 223, 178, st7789.CYAN, st7789.BLACK)
        
        # Daten werden zum Broker gesendet
        publish_senden("Raum/Feedback", feedbackdaten_neu)

#-------------------------------------------------------------------------------------------------------------#
"""Daten vom Broker empfangen"""
    # Nach neuen Nachrichten Abfragen
    if wlan.isconnected() and mqttsb_verbunden:
        try:
            subscribe_client.check_msg()
        
        except OSError as e:
            # Fehlerbehandlung bei Netzwerkfehler
            print("Netzwerkfehler beim Subscribe Client")
            try:
                # Überprüfen ob eine Verbindung zum Wlan Netzwerkvorhanden ist
                if not wlan.isconnected():
                    print("Versuchen sich wieder mit den Wlan zu verbinden")
                    wifi_verbindung() # Wlan-Verbindung wieder herstellen, sollte keine da sein
                
                print("Versuchen sich wieder mit den Subscribe Broker zu verbinden")
                
                # Reconntecten und Subscriben
                subscribe_client.connect()
                subscribe_client.subscribe(subscribe_MQTT_TOPIC_1) #Topic Steuerung/Stufen
                subscribe_client.subscribe(subscribe_MQTT_TOPIC_2) #Topic Steuerung/FrostEIN
                subscribe_client.subscribe(subscribe_MQTT_TOPIC_3) #Topic Steuerung/FrostAUS
                
                # Erneut nach neuen Nachrichten Abfragen
                subscribe_client.check_msg()
            
            except Exception as e2:
                # Fehlernachricht falls das Reconnecten nicht funktioniert
                print("Unbekannter Netzwerkfehler", e2)
                
                # Anzeige des Fehler Textes
                txt.fill(st7789.BLACK)
                txt.text(font, "Fehler beim Reconnect mit", 60, 132, st7789.CYAN, st7789.BLACK)
                txt.text(font, "MQTT-Broker-Subscribe-", 85, 155, st7789.CYAN, st7789.BLACK)
                txt.text(font, f"Fehler {e2}", 30, 178, st7789.CYAN, st7789.BLACK)
                
                # Der Wert wird auf False gesetzt um die Hauptschleife kontrolliert zu beenden
                mqttsb_verbunden = False
        
        except Exception as e:
            print("Fehler beim Subscribe Client", e)
            
            # Anzeige des Fehler Textes
            txt.fill(st7789.BLACK)
            txt.text(font, "Fehler beim Verbinden mit", 60, 132, st7789.CYAN, st7789.BLACK)
            txt.text(font, "MQTT-Broker-Subscribe", 85, 155, st7789.CYAN, st7789.BLACK)
            txt.text(font, f"Fehler {e}", 30, 178, st7789.CYAN, st7789.BLACK)
            
            # Der Wert wird auf False gesetzt um die Hauptschleife kontrolliert zu beenden
            mqttsb_verbunden = False
            
# Verlassen der Hauptschleife

# Bei Beendigung der Schleife wird folgendes auf den Bildschirm angezeigt
txt.text(font, "Hauptschleife beendet", 80, 40, st7789.CYAN, st7789.BLACK)