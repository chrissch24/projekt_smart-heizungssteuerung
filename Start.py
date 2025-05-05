#Projekt: Smart Heizungssteuerung
#Ersteller: Ch. Scheele
#Erstellungsdatum: 25.03.2025
#Letzte Änderung: 29.04.2025
#Programm Name: Start
#Aufgabe: Definieren der folgenden Netzwerkeinstellungen
#		  Wlan-SSID
#		  Wlan-Passwort
#		  MQTT-Broker-IP

#=====Bibliotheken=====#
import time
import network
import socket
#======================#

#=====Variabeln festlegen=====#
wlan_ssid = 0
wlan_passwort = 0
broker_ip = 0
params = {}
#=============================#

#===== Access Point erstellen =====#
ap = network.WLAN(network.AP_IF)
ap.active(True)
# SSID und Passwort wird für den Accesspoint erstellt
ap.config(essid="Smart-ESP32S3", authmode=network.AUTH_OPEN)

# Warteschleife bis der Accespoint ativiert ist
while not ap.active():
    pass

print('Access Point aktiv')
print(ap.ifconfig())

#==================================#

#===== HTML-Webseite =====#
html = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>WLAN und MQTT Einstellungen</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 20px;
        }
        h1 {
            font-size: 20px;
            margin-bottom: 20px;
        }
        .form-group {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }
        .form-group label {
            width: 150px;
            font-weight: bold;
        }
        .form-group input {
            flex: 1;
            padding: 5px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <h1>Hier bitte die Wlan SSID, Wlan Passwort und MQTT-Broker-IP eintragen</h1>

    <form action="/save" method="POST">
        <div class="form-group">
            <label for="ssid">WLAN-SSID:</label>
            <input type="text" id="ssid" name="ssid" required>
        </div>

        <div class="form-group">
            <label for="password">WLAN-Passwort:</label>
            <input type="password" id="password" name="password" required>
        </div>

        <div class="form-group">
            <label for="broker">MQTT-Broker-IP:</label>
            <input type="text" id="broker" name="broker" required>
        </div>

        <button type="submit">Speichern</button>
    </form>
</body>
</html>

"""

# Webserver starten
ini_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ini_server.bind(('0.0.0.0', 80))
ini_server.listen(5)

#===== Hauptschleife =====#

while True:
    # Auf eingehende Verbindung warten
    conn, addr = ini_server.accept()
    print("Verbindung von", addr)
    
    # HTTP-Request vom Client empfangen
    request = conn.recv(1024)
    request_str = request.decode('utf-8')
    
    
    # Prüfen, ob eine POST-Anfrage durch das Drücken des "Speichern"-Buttons gesendet wurde
    if 'POST /save' in request_str:
        
        # Den Dateninhalt(Body) aus der HTTP-Nachricht extrahieren
        body = request_str.split('\r\n\r\n', 1)[1]  # Nach Header kommt der Body
        print("Body:", body)
        
        # Dateninhalt in Schlüssel-Werte-Paare aufteilen und in einen Dictionary speichern
        
        for pair in body.split('&'):
            key, value = pair.split('=')
            
            # Decodierung des URL-Codes
            value = value.replace('%20', ' ')  # %20 wird zu Leerzeichen
            value = value.replace('+', ' ')     # + wird zu Leerzeichen
            value = value.replace('%2B', '+')  # %2B wird zu Pluszeichen
            value = value.replace('%3D', '=')  # %3D wird zu Gleichzeichen
            value = value.replace('%2E', '.')  # %2E wird zu Punkt
            value = value.replace('%21', '!')  # %21 wird zu Ausrufezeichen
            value = value.replace('%3F', '?')  # %3F wird zu Fragezeichenn
            value = value.replace('%23', '#')  # %23 wird zu Hash
            value = value.replace('%5F', '_')  # %5F wird zu Unterstrich
            value = value.replace('%2D', '-')  # %2D wird zu Bindestrich
            
            params[key] = value
        
        # Werte aus den Dictionary holen
        wlan_ssid = params.get('ssid', 0)
        wlan_passwort = params.get('password', 0)
        broker_ip = params.get('broker', 0)
        
        # Eine einfache Bestätigungsseite an den Server senden
        response = """\
HTTP/1.1 200 OK

Daten gespeichert. Bitte schließen Sie das Fenster.
"""
        conn.send(response.encode('utf-8'))
        conn.close()

        # Hauptschleife beenden, da die Netzwerk-Daten in der Variabeln gespeichert sind
        break

    else:
        # Sende die gespeicherte HTML-Seite als Antwort auf die GET-Anfrage
        conn.send("HTTP/1.1 200 OK\n")
        conn.send("Content-Type: text/html\n\n")
        conn.send(html)
        conn.close()

# Verlassen der Hauptschleife

# Webserver schließen
ini_server.close()
time.sleep(2)

# Access Point deaktivieren
ap.active(False)
time.sleep(2)
print("Initialisierungsprogramm beendet")