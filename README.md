# KeePassXC OTP Integration for Home Assistant

[English](#english) | [Deutsch](#deutsch)

---

## English

A Home Assistant custom integration that reads OTP/TOTP entries from a KeePassXC database and creates Home Assistant sensors for easy access to your two-factor authentication codes.

### Features

- 📱 **Read TOTP codes** from KeePassXC database
- 🔄 **Automatic updates** - codes refresh every 10 seconds with countdown timer
- 🔐 **Secure authentication** - supports password and keyfile authentication
- 🧹 **Auto-cleanup** - removes old sensors before each sync
- 🌍 **Multi-language** - English and German translations
- 🎨 **Home Assistant UI** - easy configuration through the UI

### Installation

#### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/XtraLarge/keepassxc_otp`
6. Select "Integration" as the category
7. Click "Add"
8. Search for "KeePassXC OTP" and install it
9. Restart Home Assistant

#### Manual Installation

1. Copy the `custom_components/keepassxc_otp` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

### Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **KeePassXC OTP**
4. Enter your configuration:
   - **Database Path**: Full path to your KeePassXC database file (e.g., `/config/keepass.kdbx`)
   - **Master Password**: Your KeePassXC database password
   - **Keyfile Path** (optional): Path to keyfile if you use one

5. Click **Submit**

The integration will:
- Validate your credentials
- Remove any old OTP sensors from previous syncs
- Scan your database for OTP entries
- Create a sensor for each OTP entry found

### How It Works

#### Supported OTP Formats

The integration looks for OTP data in KeePassXC entries in the following locations:
1. Custom attribute named `otp`, `totp`, or `otpauth`
2. Built-in TOTP field
3. Any custom attribute containing `otpauth://` URI

#### Example KeePassXC Entry

```
Entry: "GitHub"
- Username: user@example.com
- Password: ********
- Custom Attributes:
  - otp: otpauth://totp/GitHub:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=GitHub
```

This creates sensor: `sensor.keepassxc_otp_github`

#### Sensor Attributes

Each sensor provides:
- **State**: Current 6-digit TOTP code (zero-padded)
- **Attributes**:
  - `entry_name`: Entry title from KeePassXC
  - `issuer`: Service name (e.g., "GitHub")
  - `account`: Account identifier (e.g., email)
  - `time_remaining`: Seconds until code expires
  - `period`: TOTP refresh period (usually 30 seconds)

### Usage Examples

#### Display in Lovelace

```yaml
type: entities
title: OTP Codes
entities:
  - entity: sensor.keepassxc_otp_github
    secondary_info: attribute:time_remaining
  - entity: sensor.keepassxc_otp_google
    secondary_info: attribute:time_remaining
```

#### Automation Example

```yaml
automation:
  - alias: "Notify when OTP code changes"
    trigger:
      - platform: state
        entity_id: sensor.keepassxc_otp_github
    action:
      - service: notify.mobile_app
        data:
          message: "New GitHub OTP: {{ states('sensor.keepassxc_otp_github') }}"
```

### Troubleshooting

#### Integration not showing up
- Make sure you've restarted Home Assistant after installation
- Check the logs for any errors: **Settings** → **System** → **Logs**

#### "Database not found" error
- Verify the path to your database file is correct
- Ensure Home Assistant has read permissions for the file
- Use absolute paths (e.g., `/config/keepass.kdbx`)

#### "Invalid password" error
- Double-check your master password
- If using a keyfile, ensure the path is correct
- Try opening the database in KeePassXC to verify credentials

#### No sensors created
- Ensure your KeePassXC entries have OTP configured
- Check that OTP data is stored in a supported format (otpauth:// URI)
- Look at the logs for entries that couldn't be parsed

#### Sensors not updating
- Check that the integration hasn't been disabled
- Reload the integration: **Settings** → **Devices & Services** → **KeePassXC OTP** → **⋮** → **Reload**

### Security Considerations

- 🔒 Passwords are stored encrypted in Home Assistant's secure storage
- 🚫 Passwords and secrets are never logged
- 📖 Database is opened in read-only mode
- 🛡️ Input validation prevents path traversal attacks
- ⚠️ Error handling prevents crashes that could expose sensitive data

### Requirements

- Home Assistant 2023.1 or newer
- Python 3.9 or newer
- KeePassXC database (.kdbx format)
- Required Python packages (automatically installed):
  - `pykeepass>=4.0.0`
  - `pyotp>=2.8.0`

### Limitations

- Only TOTP (Time-based OTP) is currently supported, not HOTP (Counter-based OTP)
- Database must be accessible on the local filesystem
- Large databases may take a few seconds to scan

### Support

- **Issues**: [GitHub Issues](https://github.com/XtraLarge/keepassxc_otp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/XtraLarge/keepassxc_otp/discussions)

### License

This project is licensed under the MIT License.

---

## Deutsch

Eine Home Assistant Custom Integration, die OTP/TOTP-Einträge aus einer KeePassXC-Datenbank liest und Home Assistant Sensoren für einen einfachen Zugriff auf Ihre Zwei-Faktor-Authentifizierungscodes erstellt.

### Funktionen

- 📱 **TOTP-Codes lesen** aus KeePassXC-Datenbank
- 🔄 **Automatische Updates** - Codes werden alle 10 Sekunden mit Countdown-Timer aktualisiert
- 🔐 **Sichere Authentifizierung** - unterstützt Passwort- und Schlüsseldatei-Authentifizierung
- 🧹 **Auto-Cleanup** - entfernt alte Sensoren vor jeder Synchronisierung
- 🌍 **Mehrsprachig** - Englische und deutsche Übersetzungen
- 🎨 **Home Assistant UI** - einfache Konfiguration über die Benutzeroberfläche

### Installation

#### HACS (Empfohlen)

1. Öffnen Sie HACS in Home Assistant
2. Gehen Sie zu "Integrationen"
3. Klicken Sie auf die drei Punkte in der oberen rechten Ecke
4. Wählen Sie "Benutzerdefinierte Repositories"
5. Fügen Sie diese Repository-URL hinzu: `https://github.com/XtraLarge/keepassxc_otp`
6. Wählen Sie "Integration" als Kategorie
7. Klicken Sie auf "Hinzufügen"
8. Suchen Sie nach "KeePassXC OTP" und installieren Sie es
9. Starten Sie Home Assistant neu

#### Manuelle Installation

1. Kopieren Sie den Ordner `custom_components/keepassxc_otp` in Ihr Home Assistant `custom_components` Verzeichnis
2. Starten Sie Home Assistant neu

### Konfiguration

1. Gehen Sie zu **Einstellungen** → **Geräte & Dienste**
2. Klicken Sie auf **Integration hinzufügen**
3. Suchen Sie nach **KeePassXC OTP**
4. Geben Sie Ihre Konfiguration ein:
   - **Datenbankpfad**: Vollständiger Pfad zu Ihrer KeePassXC-Datenbankdatei (z.B. `/config/keepass.kdbx`)
   - **Master-Passwort**: Ihr KeePassXC-Datenbankpasswort
   - **Schlüsseldatei-Pfad** (optional): Pfad zur Schlüsseldatei, falls Sie eine verwenden

5. Klicken Sie auf **Senden**

Die Integration wird:
- Ihre Anmeldeinformationen validieren
- Alle alten OTP-Sensoren aus vorherigen Synchronisierungen entfernen
- Ihre Datenbank nach OTP-Einträgen durchsuchen
- Einen Sensor für jeden gefundenen OTP-Eintrag erstellen

### Funktionsweise

#### Unterstützte OTP-Formate

Die Integration sucht nach OTP-Daten in KeePassXC-Einträgen an folgenden Stellen:
1. Benutzerdefiniertes Attribut mit Namen `otp`, `totp` oder `otpauth`
2. Eingebautes TOTP-Feld
3. Jedes benutzerdefinierte Attribut, das eine `otpauth://` URI enthält

#### Beispiel KeePassXC-Eintrag

```
Eintrag: "GitHub"
- Benutzername: user@example.com
- Passwort: ********
- Benutzerdefinierte Attribute:
  - otp: otpauth://totp/GitHub:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=GitHub
```

Dies erstellt Sensor: `sensor.keepassxc_otp_github`

#### Sensor-Attribute

Jeder Sensor bietet:
- **Status**: Aktueller 6-stelliger TOTP-Code (mit Nullen aufgefüllt)
- **Attribute**:
  - `entry_name`: Eintragstitel aus KeePassXC
  - `issuer`: Dienstname (z.B. "GitHub")
  - `account`: Konto-Kennung (z.B. E-Mail)
  - `time_remaining`: Sekunden bis zum Ablauf des Codes
  - `period`: TOTP-Aktualisierungsperiode (normalerweise 30 Sekunden)

### Verwendungsbeispiele

#### Anzeige in Lovelace

```yaml
type: entities
title: OTP-Codes
entities:
  - entity: sensor.keepassxc_otp_github
    secondary_info: attribute:time_remaining
  - entity: sensor.keepassxc_otp_google
    secondary_info: attribute:time_remaining
```

#### Automatisierungsbeispiel

```yaml
automation:
  - alias: "Benachrichtigen wenn OTP-Code sich ändert"
    trigger:
      - platform: state
        entity_id: sensor.keepassxc_otp_github
    action:
      - service: notify.mobile_app
        data:
          message: "Neuer GitHub OTP: {{ states('sensor.keepassxc_otp_github') }}"
```

### Fehlerbehebung

#### Integration wird nicht angezeigt
- Stellen Sie sicher, dass Sie Home Assistant nach der Installation neu gestartet haben
- Überprüfen Sie die Protokolle auf Fehler: **Einstellungen** → **System** → **Protokolle**

#### Fehler "Datenbank nicht gefunden"
- Überprüfen Sie, ob der Pfad zu Ihrer Datenbankdatei korrekt ist
- Stellen Sie sicher, dass Home Assistant Leseberechtigungen für die Datei hat
- Verwenden Sie absolute Pfade (z.B. `/config/keepass.kdbx`)

#### Fehler "Ungültiges Passwort"
- Überprüfen Sie Ihr Master-Passwort
- Wenn Sie eine Schlüsseldatei verwenden, stellen Sie sicher, dass der Pfad korrekt ist
- Versuchen Sie, die Datenbank in KeePassXC zu öffnen, um die Anmeldeinformationen zu überprüfen

#### Keine Sensoren erstellt
- Stellen Sie sicher, dass Ihre KeePassXC-Einträge OTP konfiguriert haben
- Überprüfen Sie, dass OTP-Daten in einem unterstützten Format gespeichert sind (otpauth:// URI)
- Schauen Sie sich die Protokolle nach Einträgen an, die nicht geparst werden konnten

#### Sensoren werden nicht aktualisiert
- Überprüfen Sie, dass die Integration nicht deaktiviert wurde
- Laden Sie die Integration neu: **Einstellungen** → **Geräte & Dienste** → **KeePassXC OTP** → **⋮** → **Neu laden**

### Sicherheitsüberlegungen

- 🔒 Passwörter werden verschlüsselt im sicheren Speicher von Home Assistant gespeichert
- 🚫 Passwörter und Geheimnisse werden niemals protokolliert
- 📖 Datenbank wird im Nur-Lese-Modus geöffnet
- 🛡️ Eingabevalidierung verhindert Path-Traversal-Angriffe
- ⚠️ Fehlerbehandlung verhindert Abstürze, die sensible Daten offenlegen könnten

### Anforderungen

- Home Assistant 2023.1 oder neuer
- Python 3.9 oder neuer
- KeePassXC-Datenbank (.kdbx-Format)
- Erforderliche Python-Pakete (werden automatisch installiert):
  - `pykeepass>=4.0.0`
  - `pyotp>=2.8.0`

### Einschränkungen

- Derzeit wird nur TOTP (zeitbasiertes OTP) unterstützt, nicht HOTP (zählerbasiertes OTP)
- Datenbank muss im lokalen Dateisystem zugänglich sein
- Große Datenbanken können einige Sekunden zum Scannen benötigen

### Support

- **Probleme**: [GitHub Issues](https://github.com/XtraLarge/keepassxc_otp/issues)
- **Diskussionen**: [GitHub Discussions](https://github.com/XtraLarge/keepassxc_otp/discussions)

### Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert.