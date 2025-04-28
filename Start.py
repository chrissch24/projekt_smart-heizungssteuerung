#Projekt: Smart Heizungssteuerung
#Ersteller: Ch. Scheele
#Erstellungsdatum: 25.03.2025
#Letzte Änderung: 24.04.2025

#=====Bibliotheken=====#
import time
import network
import socket
#======================#

#=====Variabeln festlegen=====#
wlan_ssid = 0
wlan_passwort = 0
broker_ip = 0
#=============================#

#===== Access Point erstellen =====#
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid='ESP32_CS', password='12345678', authmode=network.AUTH_WPA_PSK)

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

    # Website erstellen
    conn, addr = ini_server.accept()
    request = conn.recv(1024)
    conn.send("HTTP/1.1 200 OK\n")
    conn.send("Content-Type: text/html\n\n")
    conn.send(html)
    conn.close()
    
    # Hauptschleife beenden
    if wlan_ssid != 0 and wlan_passwort != 0 and broker_ ip != 0:
        print("Progamm wird beendet")
        break
    
# Schließe Webserver
ini_server
time.sleep(2)

# Deaktiviere den Acess Point
ap.active(False)
time.sleep(2)