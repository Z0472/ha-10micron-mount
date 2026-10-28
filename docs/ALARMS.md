# 10Micron Alarm / Zvukový alarm

This add-on is **optional**. The Python integration and its tracking watchdog run without
the browser card or any blueprint. No new mount or roof controls are introduced.

## Čeština

### A. Houkání v otevřeném prohlížeči

1. Ze složky repozitáře \`www/\` zkopíruj \`tenmicron-alarm-card.js\` do
   \`/config/www/tenmicron-alarm-card.js\` v Home Assistantu.
   Pokud složka \`www\` dosud neexistovala, restartuj HA Core.
2. Nastavení → Nástěnky → nabídka **Zdroje** → **Přidat zdroj**:
   \`/local/tenmicron-alarm-card.js?v=0.7.0\`, typ **JavaScript modul**.
3. Na nástěnku vlož ruční kartu YAML:

\`\`\`yaml
type: custom:tenmicron-alarm-card
entity: binary_sensor.10micron_mount_unexpected_tracking_stop
language: cs
volume: 0.08
\`\`\`

**Entity ID je příklad.** Skutečné ID najdeš v Nastavení → Zařízení a služby →
10Micron → Entity. Překlad viditelného jména entity nemění její identifikátor.

4. Klikni na **Povolit zvuk** a následně na **Test 1 s**.
   Prohlížeč musí mít povolený zvuk a zůstat otevřený.
5. Při nové události \`off → on\` zazní opakovaný elektronický signál,
   pokud je zvuk povolený. **Umlčet** utlumí pouze tento prohlížeč,
   nezruší stav alarmu v Home Assistantu. Nový alarm po návratu do \`off\`
   může houkat znovu.
6. Při načtení stránky s již aktivním \`on\` karta stav ukáže, ale automaticky
   **nehouká na historický alarm**. Ručním kliknutím na Povolit zvuk při
   aktivním alarmu může uživatel zvuk spustit.
7. Po F5 nebo novém otevření stránky je potřeba zvuk opět povolit.
   Zamčený telefon, vypnutý počítač nebo uspaná karta negarantují přehrávání.

### B. Siréna nebo telefon přes blueprint

Zkopíruj YAML soubory do adresáře:
\`/config/blueprints/automation/tenmicron/\`

- \`tracking_stop_alarm.yaml\`: vyber binární senzor **Neočekávané zastavení
  sledování** a ve formuláři nastav libovolné akce (notifikace, siréna, atd.).
  Výchozí akcí je pouze trvalé oznámení v HA. Spouští se při \`off → on\`.
- \`connection_lost_alarm.yaml\`: volitelný dohled nedostupnosti; vyber senzor
  **Stav montáže**, nastav dobu trvání a akce. Výchozí zpoždění 2 minuty.
  Při úmyslném vypnutí montáže vznikne také \`unavailable\`; používej proto
  jen tehdy, když má být montáž v danou dobu zapnutá.

Nastavení → Automatizace a scény → Blueprinty → **Vytvořit automatizaci**.
Po ručním kopírování souborů znovu načti automatizace, pokud se blueprinty
okamžitě neobjeví.

Pro fyzickou sirénu vyber ve volitelných akcích \`siren.turn_on\` a skutečné
zařízení \`siren.*\`. Blueprint ji sám nevypíná; připrav samostatné bezpečné
potvrzení a vypnutí. Pro push notifikaci vyber dostupnou akci svého
\`notify.mobile_app_*\` zařízení. Karta ani blueprinty nic nepohybují.

**Bezpečnost:** Monitoring závisí na dostupnosti HA, jeho napájení a spojení.
Není to bezpečnostní interlock pro střechu, mechaniku ani kolizní ochrana.
Přímý NAT portu montáže do internetu nepoužívej; vhodnější je VPN.

## English

### A. Browser audio

Copy \`www/tenmicron-alarm-card.js\` into \`/config/www/\`. If you created
\`www\` for the first time, restart HA Core. Add the dashboard JavaScript
module resource \`/local/tenmicron-alarm-card.js?v=0.7.0\` under
Settings → Dashboards → Resources.

Add a manual card:

\`\`\`yaml
type: custom:tenmicron-alarm-card
entity: binary_sensor.10micron_mount_unexpected_tracking_stop
language: en
volume: 0.08
\`\`\`

Replace the example entity ID with the binary sensor created by your installation.
Click **Enable sound**, then **Test 1 s**. The card plays only on a fresh
\`off → on\` transition, with locally armed audio, or when the operator
explicitly enables sound during an existing active alarm. It does not ring
on a historical active state after page reload. **Silence** is local only.
A browser refresh requires a new user gesture. The browser must remain
visible/open and awake; use an independent siren or phone alert for unattended use.

### B. Automation blueprints

Copy \`blueprints/automation/tenmicron/*.yaml\` into
\`/config/blueprints/automation/tenmicron/\`, reload automations, and create
automations from the blueprints in Settings → Automations & scenes → Blueprints.

- **Unexpected tracking stop**: choose the fault binary sensor, a confirmation
  delay, and arbitrary HA actions (default: persistent notification).
- **Mount connection lost**: choose the mount state sensor, a sustained outage
  delay (default: 2 minutes), and arbitrary HA actions (default: persistent
  notification). Normal deliberate power-off also causes unavailable/unknown,
  so opt in only when this is meaningful.

Choose a physical \`siren.turn_on\` action for a siren or a supported mobile
notification action for phone alerts. A physical siren is not automatically
acknowledged/turned off by the supplied blueprint; configure that separately.

These blueprints, the card, and the monitoring integration do not provide
a certified interlock, roof clearance check, or collision prevention.
