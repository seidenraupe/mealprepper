# Mealprepper

Menüplanung für den Haushalt: Vorrat, Rezepte, Saison und ein Plan, den du von Hand setzt.
Die App läuft als Home-Assistant-Add-on und ist über Cloudflare Access unter
https://mp.giger-straehl.ch erreichbar.

Die automatische Planung über einen Jetson im Heimnetz ist der nächste Bauabschnitt.
Dieser Stand ruft keine KI auf. Der Jetson wird nicht durch den Tunnel veröffentlicht.

## Lokal

Voraussetzung: Python 3.13.

```bat
git clone https://github.com/seidenraupe/mealprepper.git
cd mealprepper
.\scripts\run-local.ps1
```

Öffnen: http://127.0.0.1:5051

Der Port ist 5051, damit die Familien-App auf 5050 daneben laufen kann.
Die Datenbank liegt unter `data/mealprepper.db`.

Prüfen: http://127.0.0.1:5051/api/health

Erwartet: `{"service":"mealprepper","ok":true,"version":"0.1.0"}`

## Was die App kann

- Vorrat buchen, mit Menge und optionalem Haltbarkeitsdatum.
- Rezepte mit Zutaten und Portionen anlegen.
- Saison: eine Zutat ohne Monate gilt als ganzjährig. Mit Monaten ist sie ausserhalb nicht saisonal.
- Ein Rezept ist jetzt kochbar, wenn jede Zutat saisonal ist oder im Vorrat liegt.
- Plan über 1 bis 14 Tage. Mittag und Abend werden von Hand belegt, inklusive Personenzahl.

Die Startliste ist ein Schweizer Haushaltssortiment. Weitere Zutaten legst du in der Oberfläche an.

## Add-on auf Home Assistant

Nach dem Kopieren vom PC im Heimnetz:

```bat
.\scripts\deploy-ha.ps1
```

`.env` im Repo-Root, siehe `.env.example`:

| Name | Bedeutung |
| --- | --- |
| `HA_URL` | Home Assistant, z. B. `http://192.168.1.200:8123` |
| `HA_TOKEN` | langlebiges Token unter Profil, Sicherheit |

Das Skript kopiert `addon/mealprepper` nach `\\homeassistant\addons\mealprepper`,
liest den Store neu ein, baut ein bestehendes Add-on neu oder installiert es beim ersten Mal
und startet es. Es deinstalliert nichts. Die Datenbank in `/data` bleibt erhalten.

Add-on-Optionen:

| Option | Bedeutung |
| --- | --- |
| `cloudflare_tunnel_token` | Token des Tunnels, der in diesem Container `cloudflared` startet |
| `default_people` | Vorgabe für die Personenzahl, 1 bis 99 |
| `default_days` | Vorgabe für die Planlänge, 1 bis 14 |

Im Add-on hört die API auf Port 5050. Ingress nutzt denselben Port.

## Cloudflare

Im Tunnel eine öffentliche Route anlegen:

| Feld | Wert |
| --- | --- |
| Hostname | `mp.giger-straehl.ch` |
| Service | `http://127.0.0.1:5050` |

`cloudflared` läuft im Add-on-Container. Der Service-Pfad ist deshalb der Port der API
im selben Container, nicht ein Port auf dem Entwicklungsrechner.
Davor eine Access-Policy wie bei der Familien-App. Die App selbst hat keine Benutzerverwaltung.

Gesundheit von aussen: https://mp.giger-straehl.ch/api/health

## Nächster Bauabschnitt

Der Jetson bleibt im LAN und bekommt später eine OpenAI-kompatible Anfrage
(`POST /v1/chat/completions`, typisch Ollama). Die App schickt Vorrat, Saison und Rezept-IDs.
Eine Antwort wird nur übernommen, wenn jede Mahlzeit eine bekannte Rezept-ID trifft.
Dafür kommen dann die Add-on-Optionen `jetson_base_url` und `jetson_model` dazu.
Der Tunnel veröffentlicht weiterhin nur Mealprepper.
