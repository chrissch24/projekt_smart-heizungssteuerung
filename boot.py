#Projekt: Smart Heizungssteuerung
#Ersteller: Ch. Scheele
#Erstellungsdatum: 25.03.2025
#Letzte Änderung: 29.04.2025
#Programm Name: boot
#Aufgabe: Ausführen der Start-Datei und der main-Datei in der richtigen Reihenfolge 

# Initialwert zur Steuerung des Startprozesses
wert = 0

# Start-Datei nur einmal ausführen, um doppelte Initialisierung zu vermeiden
if wert == 0:
    
    # Start-Datei ausführen um Netzwerkeinstellungen zu definieren
    import Start
    wert = 1

# Nach erfolgreicher Ausführung der Start-Datei, das Hauptprogramm starten
import main